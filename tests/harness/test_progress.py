"""Progress derivation tests (progress-schedules plan,
step 2): lib/progress.py reads the arming fields the
writers plant (lib/bundles.py) and the checkpoint lines
in todo bodies, and derives missed checks + the stall
verdict at read time — plus the `wb progress` JSON the
platform driver consumes."""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lib import bundles as bundle_mod  # noqa: E402
from lib import progress  # noqa: E402

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def armed_todo(**over):
    todo = {
        "id": "t-01K8Q00000000000000000000A",
        "title": "Long work",
        "status": "doing",
        "bundle": "2026-10-30-work",
        "archived": False,
        "path": "2026-10-30-work/todos/t-a.md",
        "progress_check": "30m",
        "progress_armed": "2026-10-30T11:30:00+00:00",
        "body": "",
    }
    todo.update(over)
    return todo


class TestTodoProgress(unittest.TestCase):
    def test_unarmed_todo_has_no_block(self):
        todo = armed_todo(progress_check=None,
                          progress_armed=None)
        self.assertIsNone(progress.todo_progress(
            todo, now=NOW))

    def test_freshly_armed_is_not_stalled(self):
        block = progress.todo_progress(armed_todo(),
                                       now=NOW)
        self.assertEqual(block["missed_checks"], 1)
        self.assertFalse(block["stalled"])
        self.assertEqual(block["interval_seconds"], 1800.0)
        self.assertEqual(block["last_activity"],
                         "2026-10-30T11:30:00+00:00")
        self.assertIsNone(block["last_checkpoint"])

    def test_two_missed_checks_is_stalled(self):
        block = progress.todo_progress(
            armed_todo(
                progress_armed="2026-10-30T10:00:00+00:00"),
            now=NOW)
        self.assertEqual(block["missed_checks"], 4)
        self.assertTrue(block["stalled"])

    def test_exactly_two_intervals_is_stalled(self):
        block = progress.todo_progress(
            armed_todo(
                progress_armed="2026-10-30T11:00:00+00:00"),
            now=NOW)
        self.assertEqual(block["missed_checks"], 2)
        self.assertTrue(block["stalled"])

    def test_checkpoint_resets_activity(self):
        body = ("Working.\n\n"
                "progress-checkpoint: "
                "2026-10-30T11:50:00+00:00 — halfway.\n")
        block = progress.todo_progress(
            armed_todo(
                progress_armed="2026-10-30T08:00:00+00:00",
                body=body),
            now=NOW)
        self.assertEqual(block["last_checkpoint"],
                         "2026-10-30T11:50:00+00:00")
        self.assertEqual(block["last_activity"],
                         "2026-10-30T11:50:00+00:00")
        self.assertEqual(block["missed_checks"], 0)
        self.assertFalse(block["stalled"])

    def test_newest_checkpoint_wins_and_bad_lines_skip(self):
        body = ("progress-checkpoint: "
                "2026-10-30T11:10:00+00:00 — first.\n"
                "progress-checkpoint: not-a-time — junk.\n"
                "progress-checkpoint: "
                "2026-10-30T11:40:00+00:00 — second.\n")
        block = progress.todo_progress(
            armed_todo(body=body), now=NOW)
        self.assertEqual(block["last_checkpoint"],
                         "2026-10-30T11:40:00+00:00")

    def test_hour_cadence_interval(self):
        block = progress.todo_progress(
            armed_todo(progress_check="2h",
                       progress_armed=
                       "2026-10-30T09:00:00+00:00"),
            now=NOW)
        self.assertEqual(block["interval_seconds"], 7200.0)
        self.assertEqual(block["missed_checks"], 1)
        self.assertFalse(block["stalled"])

    def test_invalid_cadence_never_stalls(self):
        block = progress.todo_progress(
            armed_todo(progress_check="whenever"), now=NOW)
        self.assertIsNone(block["interval_seconds"])
        self.assertIsNone(block["missed_checks"])
        self.assertFalse(block["stalled"])


class TestProjectProgress(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plans = Path(self.tmp.name) / ".plans"
        self.plans.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_report_lists_only_armed_across_bundles(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-10-30")
        bundle_mod.create_todo(
            self.plans, "work", "Armed one", status="doing",
            progress="30m",
            armed_at="2026-10-30T09:00:00+00:00",
            created="2026-10-30", updated="2026-10-30")
        bundle_mod.create_todo(
            self.plans, "work", "Quiet one",
            created="2026-10-30", updated="2026-10-30")
        report = progress.project_progress(self.plans,
                                           now=NOW)
        self.assertEqual(report["summary"],
                         {"armed": 1, "stalled": 1})
        self.assertEqual(
            [b["title"] for b in report["armed"]],
            ["Armed one"])
        self.assertEqual(report["armed"][0]["bundle"],
                         "2026-10-30-work")


class TestProgressCli(unittest.TestCase):
    def test_wb_progress_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            proj = ws / "proj"
            (proj / ".plans").mkdir(parents=True)
            (proj / "workbench.yaml").write_text(
                "name: Proj\nslug: proj\n"
                "registry: workbench/registry.db\n"
                "plans: .plans\n", encoding="utf-8")
            bundle_mod.create_bundle(proj / ".plans",
                                     "work",
                                     today="2026-10-30")
            armed_at = datetime.now(
                timezone.utc).isoformat()
            todo = bundle_mod.create_todo(
                proj / ".plans", "work", "Armed one",
                status="doing", progress="30m",
                armed_at=armed_at)
            r = subprocess.run(
                [sys.executable, str(REPO / "wb"),
                 "progress", "--root", str(ws)],
                capture_output=True, text=True, cwd=REPO)
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertEqual(len(payload["projects"]), 1)
            project = payload["projects"][0]
            self.assertEqual(project["slug"], "proj")
            self.assertEqual(project["summary"]["armed"], 1)
            self.assertEqual(project["armed"][0]["id"],
                             todo["id"])
            self.assertFalse(project["armed"][0]["stalled"])


if __name__ == "__main__":
    unittest.main()
