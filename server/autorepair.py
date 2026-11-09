#!/usr/bin/env python3
"""Capped auto-repair for the workbench-viewer companion.

Invoked by ops/watchdog.sh when the link probe does not
report up_supervised. The repair ladder, per round:

    1. unit file missing from /etc (a VM replacement
       wipes it), or present but stale — not byte-equal
       to the current template render (render-when-
       invalid, survival-contract rung 4) -> bash
       ops/install-unit.sh, which renders the tracked
       template back into place — the "copy over
       missing files" restore.
    2. an unsupervised copy of this repo's run.py holds
       the port (the lock PID is alive, is our server,
       and is not the unit's MainPID — the fallback-start
       shape) -> stop it, so systemd can bind the port.
       A process that is not this repo's run.py is never
       signalled; that case surfaces instead.
    3. systemctl restart the unit (start when systemd
       has not loaded it, rung 6).
    4. poll the probe for up_supervised.

A single not-green probe is not yet an incident — under
load a healthy server can miss one fetch — so the state
must stay not-green through a short settle window before
the ladder touches anything. At most MAX_ROUNDS rounds
run, with backoff between them; the end state must be
up_supervised. Recovery is
not "a port answers" — a fallback process dies with
whatever session started it (the 2026-10-31 lesson), so
the ladder's last rung (rung 8) is the pre-systemd
fallback start: when the cap is exhausted with the
server still down, one direct start restores
availability but the run still exits non-zero —
unsupervised service is surfaced through the scheduler
escalation, never silent success.

    python3 autorepair.py   # exit 0 repaired (or already
                            # supervised), 1 cap exhausted

The link_broken class (companion up_supervised while the
published artifact's actions fail) has no script-side
repair — its fix is a republish pass — and never reaches
this module: the watchdog only invokes repair when the
probe itself is not green. Every run records its outcome
in state/repair.json (bookkeeping; a denied write never
changes the exit verdict).
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfgmod  # noqa: E402
import linkprobe  # noqa: E402

CFG = cfgmod.load()
STATE = cfgmod.state_dir(CFG)
REPO_ROOT = cfgmod.REPO_ROOT
UNIT = CFG["systemd_unit"]

MAX_ROUNDS = 3
BACKOFF_S = (5, 20)
SETTLE_S = 10
WAIT_S = 30
KILL_WAIT_S = 5
# The down-and-unit-absent shape gets its own confirmation
# window: a freshly installed unit's first start runs the
# startup sweep synchronously before the port binds, and
# under load that has taken minutes (the 2026-11-08
# post-replacement cycle burned all three restart rounds
# polling a starting instance that then stood healthy).
# One install + one start + this window is the first-
# attempt restore the ladder owes that shape.
RESTORE_WINDOW_S = 180


def run_cmd(argv: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.run(argv, capture_output=True,
                             text=True, timeout=120)
        return out.returncode, (out.stdout + out.stderr).strip()
    except Exception as e:
        return 1, f"{argv[0]}: {e}"


def proc_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return raw.replace(b"\0", b" ").decode("utf-8",
                                               "replace")
    except OSError:
        return ""


def cmdline_is_our_server(cmdline: str, cwd: Path) -> bool:
    """True when a /proc cmdline names this repo's run.py.
    The script token may be absolute (the watchdog's
    fallback start) or relative to the process's cwd
    (a hand start) — resolve it against the cwd either
    way. Another repo's run.py resolves to its own root
    and never matches."""
    target = (REPO_ROOT / "run.py").resolve()
    for token in cmdline.split():
        if not token.endswith("run.py"):
            continue
        path = Path(token)
        if not path.is_absolute():
            path = cwd / path
        if path.resolve() == target:
            return True
    return False


def is_our_server(pid: int) -> bool:
    """True only for this repo's own run.py — the one
    process the repair may stop to free the port."""
    try:
        cwd = Path(f"/proc/{pid}/cwd").resolve()
    except OSError:
        return False
    return cmdline_is_our_server(proc_cmdline(pid), cwd)


def stop_pid(pid: int, killer=os.kill,
             sleep=time.sleep) -> bool:
    """SIGTERM, wait, SIGKILL. True when the pid is gone
    (or was never ours to stop)."""
    try:
        killer(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    for _ in range(KILL_WAIT_S):
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        sleep(1)
    try:
        killer(pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        os.kill(pid, 0)
        return False
    except OSError:
        return True


def repair_round(result: dict, runner=run_cmd,
                 stopper=stop_pid,
                 our_server=is_our_server) -> list[str]:
    """One pass down the ladder; returns the actions
    taken (for the record), never raises.

    The verb follows the unit's state: a unit systemd has
    not loaded needs `start` (a restart of an unloaded
    unit is spent motion), a loaded unit gets `restart`."""
    actions = []
    sd = result["systemd"]
    if not sd.get("unit_file") or sd.get("unit_stale"):
        # Missing -> install; present-but-stale ->
        # re-render (rung 4: a stale unit is never merely
        # started against).
        rc, _ = runner(["bash",
                        str(REPO_ROOT / "ops" /
                            "install-unit.sh")])
        actions.append(f"install_unit rc={rc}")
    lock_pid = result.get("server_pid")
    main_pid = sd.get("main_pid")
    if (lock_pid and main_pid != lock_pid
            and our_server(lock_pid)):
        stopped = stopper(lock_pid)
        actions.append(f"stop_stray pid={lock_pid} "
                       f"ok={stopped}")
    verb = "restart" if sd.get("load_state") == "loaded" \
        else "start"
    rc, _ = runner(["systemctl", verb, UNIT])
    actions.append(f"systemctl_{verb} rc={rc}")
    return actions


def wait_for(probe_fn, want: set[str], timeout_s: int,
             sleep=time.sleep,
             clock=time.monotonic) -> dict:
    """Poll the probe until its class is in `want` or the
    wall-clock window closes; returns the last result
    seen. The window is a deadline, not a poll count: one
    probe can itself take seconds under load."""
    deadline = clock() + timeout_s
    result = probe_fn()
    while (result["class"] not in want
           and clock() < deadline):
        sleep(1)
        result = probe_fn()
    return result


def direct_start() -> list[str]:
    """The ladder's last rung (rung 8, the pre-systemd
    fallback start): start run.py detached when the
    capped ladder could not restore supervision. The
    run still surfaces — this state is unsupervised by
    definition."""
    py = REPO_ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.is_file() else sys.executable
    try:
        log = open(STATE / "server.log", "ab")
        subprocess.Popen([exe, str(REPO_ROOT / "run.py")],
                         stdout=log, stderr=log,
                         start_new_session=True)
        return ["direct_start"]
    except Exception as e:
        return [f"direct_start_failed: {e}"]


def record(outcome: str, result: dict, rounds: int,
           actions: list[str]) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "class": result["class"],
        "rounds": rounds,
        "actions": actions[-20:],
    }
    try:
        path = cfgmod.state_file(CFG, "repair_file")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        print(f"autorepair: could not write state: {e}",
              file=sys.stderr)


def repair(probe_fn=linkprobe.probe, runner=run_cmd,
           stopper=stop_pid, our_server=is_our_server,
           starter=direct_start, record_fn=record,
           sleep=time.sleep,
           clock=time.monotonic) -> int:
    result = probe_fn()
    if result["class"] != linkprobe.UP_SUPERVISED:
        result = wait_for(probe_fn,
                          {linkprobe.UP_SUPERVISED},
                          SETTLE_S, sleep, clock)
    if result["class"] == linkprobe.UP_SUPERVISED:
        record_fn("already_supervised", result, 0, [])
        return 0
    actions: list[str] = []
    for round_no in range(1, MAX_ROUNDS + 1):
        fresh_restore = (
            result["class"] == linkprobe.DOWN
            and not result["systemd"].get("unit_file"))
        actions += repair_round(result, runner, stopper,
                                our_server)
        # The fresh-restore shape confirms over the long
        # window (see RESTORE_WINDOW_S); every other round
        # keeps the short one, so a genuinely stuck ladder
        # still exhausts in minutes, not tens of minutes.
        window = RESTORE_WINDOW_S if fresh_restore \
            else WAIT_S
        result = wait_for(probe_fn,
                          {linkprobe.UP_SUPERVISED},
                          window, sleep, clock)
        if result["class"] == linkprobe.UP_SUPERVISED:
            record_fn("repaired", result, round_no, actions)
            print(f"autorepair: repaired in round "
                  f"{round_no}: {actions}",
                  file=sys.stderr)
            return 0
        if round_no < MAX_ROUNDS:
            sleep(BACKOFF_S[round_no - 1])
    # Cap exhausted. Restore availability when the server
    # is fully down, but surface either way.
    if result["class"] == linkprobe.DOWN:
        actions += starter()
        result = wait_for(
            probe_fn,
            {linkprobe.UP_SUPERVISED,
             linkprobe.UP_UNSUPERVISED},
            WAIT_S, sleep, clock)
        if result["class"] == linkprobe.UP_SUPERVISED:
            record_fn("repaired", result, MAX_ROUNDS,
                      actions)
            return 0
    record_fn("surfaced", result, MAX_ROUNDS, actions)
    print(f"autorepair: repair cap exhausted, class="
          f"{result['class']}: {actions}", file=sys.stderr)
    return 1


def main() -> int:
    return repair()


if __name__ == "__main__":
    sys.exit(main())
