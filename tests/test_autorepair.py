"""Auto-repair tests (vm-restart auto-recovery, Step 3).

The orchestrator runs against scripted probe results in
the probe's own production shape, with the command
runner, the pid stopper and the fallback starter faked —
no systemctl, no signals, no live server. What is pinned:
the ladder order, the attempt cap, that only this repo's
run.py is ever stopped, and that an unsupervised end
state exits non-zero even when a fallback start restores
availability (recovery is supervised or it is surfaced).
"""

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


linkprobe = _load("linkprobe", REPO / "server" / "linkprobe.py")
autorepair = _load("autorepair",
                   REPO / "server" / "autorepair.py")


def result(klass, unit_file=True, main_pid=78358,
           server_pid=78358):
    return {"class": klass, "ok": klass == "up_supervised",
            "server_pid": server_pid,
            "systemd": {"unit_file": unit_file,
                        "main_pid": main_pid,
                        "active_state": "active",
                        "load_state": "loaded",
                        "error": None}}


class ScriptedProbe:
    """Returns the queued results, then repeats the last
    one (a state the system settles into)."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


class CountedProbe:
    """Returns the bad result for the first `bad_calls`
    calls — long enough to outlast the settle window and
    one repair round's wait — then the good result."""

    def __init__(self, bad, good, bad_calls=15):
        self.bad = bad
        self.good = good
        self.bad_calls = bad_calls
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.bad_calls:
            return self.bad
        return self.good


class Recorder:
    def __init__(self):
        self.commands = []
        self.stopped = []
        self.starts = 0
        self.sleeps = []
        self.records = []
        self.now = 0.0

    def runner(self, argv):
        self.commands.append(list(argv))
        return 0, ""

    def stopper(self, pid):
        self.stopped.append(pid)
        return True

    def starter(self):
        self.starts += 1
        return ["direct_start"]

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now

    def record(self, outcome, result, rounds, actions):
        self.records.append(outcome)


def run_repair(rec, probe, our_server=lambda pid: False):
    return autorepair.repair(
        probe_fn=probe, runner=rec.runner,
        stopper=rec.stopper, our_server=our_server,
        starter=rec.starter, record_fn=rec.record,
        sleep=rec.sleep, clock=rec.clock)


class RepairCase(unittest.TestCase):
    def test_already_supervised_is_a_noop(self):
        rec = Recorder()
        rc = run_repair(rec, ScriptedProbe(
            result("up_supervised")))
        self.assertEqual(rc, 0)
        self.assertEqual(rec.commands, [])
        self.assertEqual(rec.stopped, [])
        self.assertEqual(rec.records, ["already_supervised"])

    def test_transient_failure_never_touches_the_ladder(self):
        # A healthy server missing a few fetches under
        # load settles inside the window: no install, no
        # restart, exit 0.
        rec = Recorder()
        probe = CountedProbe(
            result("down", main_pid=None, server_pid=None),
            result("up_supervised"), bad_calls=3)
        rc = run_repair(rec, probe)
        self.assertEqual(rc, 0)
        self.assertEqual(rec.commands, [])
        self.assertEqual(rec.records, ["already_supervised"])

    def test_wiped_unit_is_reinstalled_then_restarted(self):
        # The VM-replacement shape: unit file gone, server
        # down; one round restores supervised service.
        rec = Recorder()
        probe = CountedProbe(
            result("down", unit_file=False, main_pid=None,
                   server_pid=None),
            result("up_supervised"))
        rc = run_repair(rec, probe)
        self.assertEqual(rc, 0)
        verbs = [c[1] if c[0] == "bash" else c[1]
                 for c in rec.commands]
        self.assertIn("restart", verbs)
        self.assertTrue(any("install-unit.sh" in part
                            for c in rec.commands
                            for part in c))

    def test_stray_fallback_process_is_stopped(self):
        # Health ok but the answering process is a stray
        # run.py (fallback start), not the unit's MainPID.
        rec = Recorder()
        probe = CountedProbe(
            result("up_unsupervised", main_pid=None,
                   server_pid=4242),
            result("up_supervised"))
        rc = run_repair(rec, probe,
                        our_server=lambda pid: True)
        self.assertEqual(rc, 0)
        self.assertEqual(rec.stopped, [4242])

    def test_foreign_process_is_never_stopped(self):
        rec = Recorder()
        probe = ScriptedProbe(
            result("up_unsupervised", main_pid=None,
                   server_pid=4242))
        rc = run_repair(rec, probe,
                        our_server=lambda pid: False)
        self.assertEqual(rc, 1)
        self.assertEqual(rec.stopped, [])
        # Port held by someone else: no fallback start.
        self.assertEqual(rec.starts, 0)

    def test_cap_exhausted_down_falls_back_but_surfaces(self):
        rec = Recorder()

        def probe():
            # Down through every repair round; the
            # fallback start brings up an unsupervised
            # copy (the state the cap exists to surface).
            if rec.starts:
                return result("up_unsupervised",
                              main_pid=None, server_pid=9999)
            return result("down", main_pid=None,
                          server_pid=None)

        rc = run_repair(rec, probe)
        # Availability restored by the fallback start, but
        # unsupervised service surfaces: exit 1.
        self.assertEqual(rec.starts, 1)
        self.assertEqual(rc, 1)
        self.assertEqual(rec.records, ["surfaced"])
        restarts = [c for c in rec.commands
                    if c[:2] == ["systemctl", "restart"]]
        self.assertEqual(len(restarts),
                         autorepair.MAX_ROUNDS)
        # Backoff ran between rounds, not after the last.
        self.assertEqual(rec.sleeps.count(5), 1)
        self.assertEqual(rec.sleeps.count(20), 1)

    def test_repair_round_skips_install_when_unit_present(self):
        rec = Recorder()
        actions = autorepair.repair_round(
            result("down", main_pid=None, server_pid=None),
            runner=rec.runner, stopper=rec.stopper,
            our_server=lambda pid: False)
        self.assertFalse(any("install-unit" in a
                             for a in actions))
        self.assertTrue(any("systemctl_restart" in a
                            for a in actions))


class OurServerCase(unittest.TestCase):
    def test_own_pid_cmdline_matches_run_py(self):
        self.assertTrue(autorepair.is_our_server(1)
                        is False)  # pid 1 is never run.py

    def test_absolute_start_matches(self):
        # The watchdog fallback's shape: absolute paths.
        cmdline = ("/repo/.venv/bin/python "
                   f"{REPO}/run.py")
        self.assertTrue(autorepair.cmdline_is_our_server(
            cmdline, Path("/elsewhere")))

    def test_relative_start_matches_via_cwd(self):
        # The drill's shape (2026-11-03): a hand start
        # with relative paths — the first matcher missed
        # exactly this and left the stray serving.
        cmdline = ".venv/bin/python run.py"
        self.assertTrue(autorepair.cmdline_is_our_server(
            cmdline, REPO))

    def test_other_repos_run_py_never_matches(self):
        cmdline = ".venv/bin/python run.py"
        self.assertFalse(autorepair.cmdline_is_our_server(
            cmdline, REPO.parent / "another-repo"))

    def test_unrelated_script_never_matches(self):
        cmdline = "python3 /usr/bin/other.py"
        self.assertFalse(autorepair.cmdline_is_our_server(
            cmdline, REPO))


if __name__ == "__main__":
    unittest.main()
