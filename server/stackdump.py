"""Wedge stack-dump instrumentation (stackdump-contract: v1).

The canonical contract lives in the starter SPEC
(`stackdump-contract: v1`); this module is the workbench
viewer's conformance. An in-process watchdog thread checks
the server's own health computation on a cadence; when a
check lags past the threshold, the watchdog writes every
Python thread's stack (faulthandler form — thread names and
frames, never locals or request data) to the dump file, so
the next wedge names its own root cause before the external
repair ladder's restart destroys the evidence.

Shape rules (the contract's bounded-by-construction clause):

- The health check runs on a worker thread the watchdog
  supervises by deadline; the watchdog never calls the check
  inline, so a parked check cannot park the watchdog.
- The internal check calls the health computation directly
  (the same get_sweep() the /api/health handler serves) —
  never an HTTP self-call, which would measure the acceptor
  instead of the handlers.
- Dumps write through a handle opened at startup, under no
  lock shared with request handling; the size cap is
  enforced by close-and-truncate on the watchdog's own
  schedule, never with a lock a handler could hold.
- Diagnostic only: this module never restarts, kills, or
  mutates anything outside its own dump file.
"""

import faulthandler
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# One live watchdog per process; the module-level handle is
# how the HTTP layer reads the last dump's timestamp without
# importing the server module (no cycles).
_ACTIVE = None


class StackDumpWatchdog:
    """Supervises `check` (a zero-arg callable) by deadline.

    Every `cadence_s`, a fresh worker thread runs the check;
    the watchdog waits `threshold_s` for it. A check still
    running at the deadline is a lag event: the watchdog
    dumps all thread stacks, then abandons the worker (a
    daemon thread; its late result is discarded). While the
    lag persists, dumps repeat at most once per `repeat_s`;
    the first completed check ends the event.
    """

    def __init__(self, check, dump_path, *, server_name,
                 cadence_s=5.0, threshold_s=15.0,
                 repeat_s=60.0, max_bytes=16 * 1024 * 1024,
                 now=None):
        self._check = check
        self._path = Path(dump_path)
        self._server_name = server_name
        self._cadence_s = float(cadence_s)
        self._threshold_s = float(threshold_s)
        self._repeat_s = float(repeat_s)
        self._max_bytes = int(max_bytes)
        self._now = now or time.monotonic
        # Wall-clock source for the dump timestamps (ISO);
        # kept separate from the decision clock above —
        # dump headers record real time even when _now is a
        # test double.
        self._wall = time.time
        self._fh = None
        self._size = 0
        self._last_dump_at = None   # ISO string, for health
        self._last_dump_mono = None
        self._lag_since = None
        self._stop = threading.Event()
        self._thread = None

    # -- lifecycle ------------------------------------------

    def start(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a", encoding="utf-8")
        self._size = self._path.stat().st_size
        self._thread = threading.Thread(
            target=self._run, name="stackdump-watchdog",
            daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._cadence_s + 1)
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def last_dump_at(self):
        """ISO timestamp of the most recent dump, or None."""
        return self._last_dump_at

    # -- the supervision loop -------------------------------

    def _run(self):
        # The cadence wait comes FIRST: step() itself blocks
        # up to the threshold supervising its check, so a
        # loop that steps before waiting has no idle gap at
        # startup — and a test that widens the cadence after
        # start() parks this loop before its first step,
        # which is what makes manual step() driving exact.
        while not self._stop.is_set():
            self._stop.wait(self._cadence_s)
            if self._stop.is_set():
                break
            self.step()

    def step(self):
        """One supervise cycle: run the check under its
        deadline; dump on lag (repeat-capped); a completed
        check clears the lag event. Public so tests can drive
        the loop deterministically without real cadences."""
        done = threading.Event()
        box = {}

        def _work():
            try:
                box["result"] = self._check()
            except Exception as e:  # a failed check is a
                box["error"] = e  # completed check: the
            finally:              # server answered, badly
                done.set()

        started = self._now()
        worker = threading.Thread(target=_work,
                                  name="stackdump-check",
                                  daemon=True)
        worker.start()
        if done.wait(self._threshold_s):
            self._lag_since = None
            return True
        if self._lag_since is None:
            self._lag_since = started
        lag_s = self._now() - self._lag_since
        # The repeat window is measured on the monotonic
        # clock at full precision — never on the wall clock:
        # whole-second resolution here would read a 0.3 s
        # gap as a full second at a boundary and defeat a
        # sub-second window outright (pinned by the repeat
        # test's deterministic clock).
        if self._last_dump_mono is None \
                or self._now() - self._last_dump_mono \
                >= self._repeat_s:
            self._dump(lag_s)
        return False

    # -- the dump -------------------------------------------

    def _dump(self, lag_s):
        self._enforce_cap()
        stamp = datetime.fromtimestamp(
            self._wall(), timezone.utc).isoformat()
        header = (
            f"=== stackdump {stamp} server={self._server_name} "
            f"contract=stackdump-contract: v1 "
            f"lag_s={lag_s:.1f} ===\n")
        self._fh.write(header)
        self._fh.flush()
        # faulthandler writes the traceback of every thread,
        # the calling (watchdog) thread included; its output
        # is frame files/lines/functions only.
        faulthandler.dump_traceback(file=self._fh,
                                    all_threads=True)
        self._fh.flush()
        self._size = self._path.stat().st_size
        self._last_dump_at = stamp
        self._last_dump_mono = self._now()

    def _enforce_cap(self):
        """Aggregate size cap: a file at/over the cap is
        truncated (with a marker) before the next dump, so a
        long wedge cannot fill the disk the recovery ladder
        needs. Close/write/reopen on the watchdog thread —
        no lock is taken, so nothing here can park behind a
        wedged handler."""
        if self._size < self._max_bytes:
            return
        stamp = datetime.fromtimestamp(
            self._wall(), timezone.utc).isoformat()
        self._fh.close()
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(f"=== stackdump {stamp} "
                    f"server={self._server_name} "
                    f"note=file truncated at cap "
                    f"{self._max_bytes} bytes ===\n")
        self._fh = open(self._path, "a", encoding="utf-8")
        self._size = self._path.stat().st_size


def start_stackdump(check, dump_path, *, server_name, cfg):
    """Build, start, and register the process watchdog from
    the loaded config's stackdump_* keys."""
    global _ACTIVE
    wd = StackDumpWatchdog(
        check, dump_path, server_name=server_name,
        cadence_s=cfg["stackdump_cadence_s"],
        threshold_s=cfg["stackdump_threshold_s"],
        repeat_s=cfg["stackdump_repeat_s"],
        max_bytes=cfg["stackdump_max_bytes"])
    wd.start()
    _ACTIVE = wd
    return wd


def last_dump_at():
    """The active watchdog's last dump timestamp (ISO) or
    None — the health payload's clause-6 field."""
    return _ACTIVE.last_dump_at() if _ACTIVE else None
