"""Watchdog healthcheck-leg bound tests.

ops/watchdog.sh runs three legs in order: the plain
healthcheck (freshens state/health.json), the link probe,
and — only when the probe is not green — the repair ladder.
The healthcheck's own read deadlines hold only while the
box schedules the checker, so an unbounded leg can overrun
the scheduler job's timeout and get the job killed mid-leg:
the probe and the ladder then never run, exactly when the
box is loaded enough to wedge the server (the 2026-11-09
19:19Z episode: the previous instance sat hard-wedged
through eight watchdog cycles that all exited 0 without one
repair attempt). The leg therefore runs under a hard bound
(`timeout -s KILL`, survival-contract rung 5) whose kill or
failure never skips the probe.

These tests drive the real script against a fixture repo
in a temp dir: the fixture's server/ legs are stand-ins (a
hanging healthcheck that appends a marker per second, a
probe that greens or not per its marker file, a repair
that appends its own marker), so what is pinned is the
script's control flow, not the legs' internals. WB_STATE
redirects the healthcheck stand-in's state write into the
fixture tree — the suite never touches the live state dir.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
WATCHDOG = REPO / "ops" / "watchdog.sh"

HEALTHCHECK = '''\
import os, sys, time
from pathlib import Path
state = Path(os.environ["WB_STATE"])
(state / "hc_started").write_text("1")
for _ in range(60):
    with open(state / "hc_ticks", "a") as f:
        f.write("x")
    time.sleep(1)
'''

PROBE = '''\
import os, sys
from pathlib import Path
state = Path(os.environ["WB_STATE"])
(state / "probe_ran").write_text("1")
sys.exit(0 if (state / "probe_green").exists() else 1)
'''

REPAIR = '''\
import os
from pathlib import Path
Path(os.environ["WB_STATE"], "repair_ran").write_text("1")
'''


class WatchdogCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(
            prefix="wb-watchdog-"))
        self.addCleanup(shutil.rmtree, self.tmp,
                        ignore_errors=True)
        self.state = self.tmp / "state"
        self.state.mkdir()
        server = self.tmp / "server"
        server.mkdir()
        (server / "healthcheck.py").write_text(HEALTHCHECK)
        (server / "linkprobe.py").write_text(PROBE)
        (server / "autorepair.py").write_text(REPAIR)
        ops = self.tmp / "ops"
        ops.mkdir()
        shutil.copy(WATCHDOG, ops / "watchdog.sh")

    def _run(self, timeout_s="2"):
        env = dict(os.environ)
        env["WB_STATE"] = str(self.state)
        env["WB_HEALTHCHECK_TIMEOUT_S"] = timeout_s
        started = time.monotonic()
        proc = subprocess.run(
            ["bash", str(self.tmp / "ops" / "watchdog.sh")],
            capture_output=True, text=True, timeout=60,
            env=env)
        return proc, time.monotonic() - started

    def test_hung_healthcheck_leg_is_killed_and_probe_runs(
            self):
        # The defect's shape: the healthcheck leg hangs.
        # The bound must kill the leg alone (a handful of
        # 1s ticks, not the fixture's full 60), the probe
        # must still run, and its not-green verdict must
        # reach the repair leg.
        proc, elapsed = self._run()
        ticks = (self.state / "hc_ticks").read_text()
        self.assertLess(len(ticks), 10)
        self.assertTrue((self.state / "probe_ran").exists())
        self.assertTrue((self.state / "repair_ran").exists())
        self.assertIn("auto-repair", proc.stderr)
        self.assertLess(elapsed, 30)

    def test_green_probe_skips_repair(self):
        (self.state / "probe_green").write_text("1")
        proc, _elapsed = self._run()
        self.assertEqual(proc.returncode, 0)
        self.assertTrue((self.state / "probe_ran").exists())
        self.assertFalse((self.state / "repair_ran").exists())


if __name__ == "__main__":
    unittest.main()
