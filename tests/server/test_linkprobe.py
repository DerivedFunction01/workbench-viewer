"""Link probe tests (vm-restart auto-recovery, Step 2).

The classification is pure over probed facts, so the tests
feed it production-shaped facts: a real /api/health payload
shape, the lock file's PID, and `systemctl show` output in
its key=value form. No live server or systemd is touched.
"""

import importlib.util
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


linkprobe = _load("linkprobe", REPO / "server" / "linkprobe.py")

HEALTH_OK = {"ok": True, "version": "1.0.0",
             "commit": "bf66b4d", "uptime_s": 15.3,
             "projects_count": 10}

SHOW_ACTIVE = ("MainPID=78358\n"
               "ActiveState=active\n"
               "LoadState=loaded\n")


def sd(**over):
    base = {"unit_file": True, "active_state": "active",
            "load_state": "loaded", "main_pid": 78358,
            "error": None}
    base.update(over)
    return base


class ClassifyCase(unittest.TestCase):
    def test_healthy_and_supervised(self):
        klass, reasons = linkprobe.classify(True, 78358, sd())
        self.assertEqual(klass, linkprobe.UP_SUPERVISED)
        self.assertEqual(reasons, [])

    def test_health_failure_is_down(self):
        klass, reasons = linkprobe.classify(False, None, sd())
        self.assertEqual(klass, linkprobe.DOWN)
        self.assertEqual(reasons, ["health_not_ok"])

    def test_unit_file_wiped_is_unsupervised(self):
        # The VM-replacement shape: /etc lost the unit, a
        # process still answers the port.
        klass, reasons = linkprobe.classify(
            True, 78358, sd(unit_file=False))
        self.assertEqual(klass, linkprobe.UP_UNSUPERVISED)
        self.assertIn("unit_file_missing", reasons)

    def test_stray_process_answering_is_unsupervised(self):
        # The fallback-start shape: health ok, but the
        # answering PID is not the unit's MainPID.
        klass, reasons = linkprobe.classify(True, 4242, sd())
        self.assertEqual(klass, linkprobe.UP_UNSUPERVISED)
        self.assertIn("main_pid_mismatch", reasons)

    def test_service_inactive_is_unsupervised(self):
        klass, reasons = linkprobe.classify(
            True, 78358, sd(active_state="inactive",
                            main_pid=None))
        self.assertEqual(klass, linkprobe.UP_UNSUPERVISED)
        self.assertIn("service_not_active", reasons)
        self.assertIn("no_main_pid", reasons)

    def test_missing_lock_pid_is_unsupervised(self):
        klass, reasons = linkprobe.classify(True, None, sd())
        self.assertEqual(klass, linkprobe.UP_UNSUPERVISED)
        self.assertIn("lock_pid_missing", reasons)

    def test_stale_unit_is_unsupervised(self):
        # Rung 4 (render-when-invalid): the unit file is
        # present but not byte-equal to the current
        # render — unsupervised, with its own reason, so
        # the ladder re-renders instead of starting
        # against a stale unit.
        klass, reasons = linkprobe.classify(
            True, 78358, sd(unit_stale=True))
        self.assertEqual(klass, linkprobe.UP_UNSUPERVISED)
        self.assertIn("unit_stale", reasons)


class UnitStaleCase(unittest.TestCase):
    """The byte-equality check itself, against a scratch
    unit dir: the module's UNIT_DIR is pointed at a temp
    dir; the render expectation comes from the real
    tracked template."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.unit_dir = Path(self.tmp.name)
        self._saved = linkprobe.UNIT_DIR
        linkprobe.UNIT_DIR = self.unit_dir
        self.addCleanup(
            setattr, linkprobe, "UNIT_DIR", self._saved)

    def test_current_render_is_not_stale(self):
        expected = linkprobe.render_unit()
        self.assertIsNotNone(expected)
        (self.unit_dir
         / "workbench-viewer-server.service").write_text(
            expected, encoding="utf-8")
        self.assertFalse(linkprobe.unit_stale(
            "workbench-viewer-server"))

    def test_different_bytes_are_stale(self):
        (self.unit_dir
         / "workbench-viewer-server.service").write_text(
            "[Unit]\nDescription=old render\n",
            encoding="utf-8")
        self.assertTrue(linkprobe.unit_stale(
            "workbench-viewer-server"))

    def test_missing_file_is_not_stale(self):
        # Absence is the ladder's install case, not the
        # re-render case.
        self.assertFalse(linkprobe.unit_stale(
            "workbench-viewer-server"))


class ParseShowCase(unittest.TestCase):
    def test_parses_production_shape(self):
        parsed = linkprobe.parse_systemd_show(SHOW_ACTIVE)
        self.assertEqual(parsed["main_pid"], 78358)
        self.assertEqual(parsed["active_state"], "active")
        self.assertEqual(parsed["load_state"], "loaded")

    def test_zero_main_pid_reads_as_none(self):
        parsed = linkprobe.parse_systemd_show(
            "MainPID=0\nActiveState=inactive\n"
            "LoadState=loaded\n")
        self.assertIsNone(parsed["main_pid"])

    def test_not_found_unit(self):
        parsed = linkprobe.parse_systemd_show(
            "MainPID=0\nActiveState=inactive\n"
            "LoadState=not-found\n")
        self.assertEqual(parsed["load_state"], "not-found")
        self.assertIsNone(parsed["main_pid"])


class FetchBoundedCase(unittest.TestCase):
    def test_fast_fetch_returns_its_value(self):
        got = linkprobe.fetch_bounded(
            fetch=lambda: HEALTH_OK, budget_s=2.0)
        self.assertEqual(got, HEALTH_OK)

    def test_hanging_fetch_is_abandoned_at_the_budget(self):
        # The 2026-11-08 wedge shape: the fetch never
        # returns because the read inside it never ends.
        # The caller must stop waiting at the budget and
        # read the missing answer as down, so the watchdog
        # reaches the repair ladder.
        never = threading.Event()

        def hang():
            never.wait(30)
            return HEALTH_OK

        start = time.monotonic()
        got = linkprobe.fetch_bounded(fetch=hang,
                                      budget_s=0.3)
        elapsed = time.monotonic() - start
        self.assertIsNone(got)
        self.assertLess(elapsed, 5)

    def test_raising_fetch_reads_as_none(self):
        def boom():
            raise RuntimeError("wedged")

        got = linkprobe.fetch_bounded(fetch=boom,
                                      budget_s=2.0)
        self.assertIsNone(got)


class ProbeCase(unittest.TestCase):
    def _probe(self, health, lock_pid, state):
        return linkprobe.probe(
            fetch=lambda: health,
            lock_pid_of=lambda: lock_pid,
            systemd_of=lambda unit: state)

    def test_probe_reports_supervised(self):
        result = self._probe(HEALTH_OK, 78358, sd())
        self.assertEqual(result["class"],
                         linkprobe.UP_SUPERVISED)
        self.assertTrue(result["ok"])
        self.assertEqual(result["server_pid"], 78358)
        self.assertEqual(result["commit"], "bf66b4d")
        self.assertEqual(result["systemd"]["main_pid"], 78358)
        # The script never claims the space-side leg.
        self.assertEqual(result["link"],
                         "not_checked_by_script")
        self.assertEqual(
            linkprobe.EXIT_CODES[result["class"]], 0)

    def test_probe_reports_down(self):
        result = self._probe(None, None, sd())
        self.assertEqual(result["class"], linkprobe.DOWN)
        self.assertFalse(result["ok"])
        self.assertEqual(
            linkprobe.EXIT_CODES[result["class"]], 1)

    def test_probe_reports_unsupervised(self):
        result = self._probe(HEALTH_OK, 4242, sd())
        self.assertEqual(result["class"],
                         linkprobe.UP_UNSUPERVISED)
        self.assertEqual(
            linkprobe.EXIT_CODES[result["class"]], 2)


if __name__ == "__main__":
    unittest.main()
