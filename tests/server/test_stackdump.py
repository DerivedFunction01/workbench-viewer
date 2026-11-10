"""Stack-dump watchdog tests (stackdump-contract: v1).

The contract's three suite obligations, driven against the
real module with fixture checks in a temp dir (the suite
never touches the live state dir):

(a) a check parked past the threshold produces a dump
    naming the parked frame — and the watchdog is never
    blocked by the parked check: it neither holds nor waits
    on any lock of the check's (the check here parks while
    HOLDING a lock, the wedge shape), and step() returns at
    the threshold rather than at the check's release;
(b) a healthy check produces no dump over several cycles;
(c) the aggregate size cap truncates the dump file (with
    its marker) instead of letting a long lag fill it.

The watchdog is driven by step() calls with short
thresholds — no real cadences, no sleeps past the small
budgets the assertions name.
"""

import importlib.util
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stackdump = _load("stackdump", REPO / "server" / "stackdump.py")


class StackDumpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dump_path = Path(self.tmp.name) / "stackdumps.log"

    def watchdog(self, check, clock=None, **over):
        kw = {"cadence_s": 0.05, "threshold_s": 0.25,
              "repeat_s": 0.3, "max_bytes": 16 * 1024 * 1024}
        kw.update(over)
        if clock is not None:
            # Deterministic decision clock (the constructor's
            # `now` seam): the repeat tests advance it by
            # hand, so no assertion rides on real elapsed
            # time. The parked worker threads still park on
            # real events; only the watchdog's arithmetic is
            # pinned.
            kw["now"] = clock
        wd = stackdump.StackDumpWatchdog(
            check, self.dump_path, server_name="fixture",
            **kw)
        wd.start()
        self.addCleanup(wd.stop)
        return wd

    def test_parked_check_dumps_its_frame(self):
        release = threading.Event()
        park_lock = threading.Lock()

        def parked_check():
            # The wedge shape: the check parks while HOLDING
            # a lock (the sweep's single-flight lock in the
            # real server). The dump path takes no lock, so
            # the watchdog must still fire at its threshold.
            with park_lock:
                release.wait(30)

        wd = self.watchdog(parked_check)
        t0 = time.monotonic()
        ok = wd.step()
        elapsed = time.monotonic() - t0
        self.assertFalse(ok)
        # step() returned at the threshold (~0.25 s), not
        # when the check is released below — the watchdog
        # was not blocked by the parked check or its lock.
        self.assertLess(elapsed, 5)
        text = self.dump_path.read_text(encoding="utf-8")
        self.assertIn("stackdump-contract: v1", text)
        self.assertIn("server=fixture", text)
        # The parked check's own frame is named in the dump.
        self.assertIn("parked_check", text)
        self.assertIsNotNone(wd.last_dump_at())
        release.set()

    def test_healthy_check_never_dumps(self):
        wd = self.watchdog(lambda: {"projects": 0})
        for _ in range(5):
            self.assertTrue(wd.step())
        self.assertEqual(
            self.dump_path.read_text(encoding="utf-8"), "")
        self.assertIsNone(wd.last_dump_at())

    def test_failed_check_is_a_completed_check(self):
        def boom():
            raise RuntimeError("sweep failed")

        wd = self.watchdog(boom)
        self.assertTrue(wd.step())
        self.assertEqual(
            self.dump_path.read_text(encoding="utf-8"), "")

    def test_repeat_cap_spaces_dumps(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def parked_check():
            release.wait(30)

        clock = [1000.0]
        wd = self.watchdog(parked_check,
                            clock=lambda: clock[0],
                            threshold_s=10.0, repeat_s=60.0)
        # The background loop would race the pinned clock at
        # the real threshold and dump on its own schedule;
        # freeze its cadence (its next wait is a year) so
        # these assertions drive step() by hand. (stop() is
        # not usable here: it closes the dump handle step()
        # writes through.)
        wd._cadence_s = 365 * 24 * 3600.0
        self.assertFalse(wd.step())
        clock[0] += 30.0  # still inside the repeat window
        self.assertFalse(wd.step())
        text = self.dump_path.read_text(encoding="utf-8")
        # Two lagging cycles inside the repeat window yield
        # exactly one dump.
        self.assertEqual(text.count("=== stackdump"), 1)
        clock[0] += 31.0  # past the window: a second dump
        self.assertFalse(wd.step())
        text = self.dump_path.read_text(encoding="utf-8")
        self.assertEqual(text.count("=== stackdump"), 2)

    def test_size_cap_truncates_with_marker(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def parked_check():
            release.wait(30)

        clock = [1000.0]
        wd = self.watchdog(parked_check,
                            clock=lambda: clock[0],
                            threshold_s=10.0,
                            repeat_s=0.0, max_bytes=200)
        wd._cadence_s = 365 * 24 * 3600.0  # manual step()
        # driving, as in the repeat test — no background dumps
        self.assertFalse(wd.step())
        self.assertFalse(wd.step())
        text = self.dump_path.read_text(encoding="utf-8")
        # The second cycle found the file at/over the cap:
        # it was truncated (marker line present) and the new
        # dump appended after it — total stays bounded by
        # the cap plus one dump, not two full dumps.
        self.assertIn("note=file truncated at cap", text)
        # Bounded by the cap plus one dump (a full all-thread
        # dump is a few KB), never two full dumps.
        self.assertLess(len(text.encode("utf-8")), 200 + 8192)


if __name__ == "__main__":
    unittest.main()
