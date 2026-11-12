"""Owner-attention armed rows (staffing-absorption
plan 2026-11-11, Arming; commission from main
2026-11-11): the todo `doing` transition that arms a
progress schedule also writes the work item's row for
the attention evaluator, a terminal move retires it,
and the declared opt-out writes no row.
lib/progress/attention.py is the mechanism; the todo
file stays the record of truth and the row is derived
state, exactly like the scheduler entry it rides
beside.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lib import bundles as bundle_mod  # noqa: E402
from lib.progress import attention as att  # noqa: E402
from lib.manifest import Manifest  # noqa: E402
from lib.sweep import Project  # noqa: E402

TODO_ID = "t-01K8Q00000000000000000000A"
ROW_ID = att.row_id("fixture-proj", TODO_ID)


def armed_todo(**over):
    todo = {
        "id": TODO_ID,
        "title": "Long work",
        "status": "doing",
        "bundle": "2026-11-01-work",
        "archived": False,
        "progress_check": "30m",
        "progress_armed": "2026-11-01T11:30:00+00:00",
        "body": "",
    }
    todo.update(over)
    return todo


class SeamCase(unittest.TestCase):
    """A tmp workspace + tmp armed dir under the env
    seams, with one fixture project inside the
    workspace (the progress-schedule suite's shape)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.ws = base / "ws"
        self.jobs = base / "jobs"
        self.jobs.mkdir(parents=True)
        self.armed = base / "armed"
        self.proj = self.ws / "fixture-proj"
        self.plans = self.proj / ".plans"
        self.plans.mkdir(parents=True)
        (self.proj / "workbench.yaml").write_text(
            "name: Fixture Proj\nslug: fixture-proj\n"
            "plans: .plans\n", encoding="utf-8")
        (self.ws / "workbench-viewer").mkdir()
        patcher = mock.patch.dict(os.environ, {
            "WB_SCHEDULER_JOBS_DIR": str(self.jobs),
            "WB_ATTENTION_ARMED_DIR": str(self.armed),
            "WB_WORKSPACE_ROOT": str(self.ws),
            "WB_VIEWER_ROOT": str(self.ws
                                  / "workbench-viewer")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def project(self):
        manifest = Manifest(
            root=self.proj, name="Fixture Proj",
            slug="fixture-proj", registry=None,
            plans=self.plans, mockups=None, archive=None,
            declared={})
        return Project(manifest)

    def row_path(self, rid=ROW_ID):
        return self.armed / f"{rid}.json"

    def make_armed(self, **kw):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        return bundle_mod.create_todo(
            self.plans, "work", "Long task",
            status="doing", progress="30m", **kw)


class TestRender(unittest.TestCase):
    def test_row_shape(self):
        row = att.render_row("fixture-proj", armed_todo())
        self.assertEqual(row["handle"], TODO_ID)
        self.assertEqual(row["todo"], TODO_ID)
        self.assertEqual(row["programme"], "fixture-proj")
        self.assertEqual(row["project"], "fixture-proj")
        self.assertEqual(row["cadence"], "30m")
        self.assertEqual(row["cadence_minutes"], 30)
        self.assertEqual(row["armed_at"],
                         "2026-11-01T11:30:00+00:00")
        self.assertEqual(row["status"], "doing")
        self.assertEqual(row["source"]["writer"],
                         "workbench-harness")
        self.assertEqual(row["source"]["source_class"],
                         "project")


class TestSync(SeamCase):
    def test_arm_writes_then_unchanged_then_disarm(self):
        out = att.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "written")
        self.assertTrue(self.row_path().is_file())
        row = json.loads(self.row_path().read_text(
            encoding="utf-8"))
        self.assertEqual(row["programme"], "fixture-proj")
        self.assertEqual(row["cadence"], "30m")
        # A fixture project declares its class, like the
        # scheduler entry's stamp.
        self.assertEqual(row["source"]["source_class"],
                         "fixture")
        out = att.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "unchanged")
        out = att.sync_todo(
            self.plans, armed_todo(status="done"))
        self.assertEqual(out["action"], "removed")
        self.assertFalse(self.row_path().exists())

    def test_blocked_archived_and_opt_out_carry_no_row(self):
        for over in ({"status": "blocked"},
                     {"archived": True},
                     {"progress_check": "off"}):
            out = att.sync_todo(
                self.plans, armed_todo(**over))
            self.assertEqual(out["action"], "unchanged")
            self.assertFalse(self.row_path().exists())

    def test_cadence_change_rewrites(self):
        att.sync_todo(self.plans, armed_todo())
        out = att.sync_todo(
            self.plans, armed_todo(progress_check="2h"))
        self.assertEqual(out["action"], "written")
        row = json.loads(self.row_path().read_text(
            encoding="utf-8"))
        self.assertEqual(row["cadence"], "2h")
        self.assertEqual(row["cadence_minutes"], 120)

    def test_no_attention_repo_skips(self):
        env = dict(os.environ)
        env.pop("WB_ATTENTION_ARMED_DIR", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(att.armed_dir())
            out = att.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "skipped")

    def test_sync_into_live_armed_dir_is_refused(self):
        # The leak guard, mirrored from the scheduler
        # seam: a temp fixture's sync never writes into
        # this machine's real armed dir.
        live = att._live_armed_dir()
        before = set(live.glob("*.json")) \
            if live.is_dir() else set()
        with mock.patch.dict(
                os.environ,
                {"WB_ATTENTION_ARMED_DIR": str(live)}):
            out = att.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "skipped")
        after = set(live.glob("*.json")) \
            if live.is_dir() else set()
        self.assertEqual(after, before)


class TestWriters(SeamCase):
    def test_create_and_terminal_moves_sync_the_row(self):
        todo = self.make_armed()
        self.assertEqual(
            todo["attention_row"]["action"], "written")
        rid = att.row_id("fixture-proj", todo["id"])
        self.assertTrue(self.row_path(rid).is_file())
        out = bundle_mod.set_todo_status(
            self.plans, todo["id"], "done")
        self.assertEqual(
            out["attention_row"]["action"], "removed")
        self.assertFalse(self.row_path(rid).exists())

    def test_doing_move_without_flag_writes_row(self):
        # The commission's proof shape, end to end: no
        # --progress anywhere — the doing move arms at
        # the 15-minute default and writes the row with
        # that cadence; the done move retires it.
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        todo = bundle_mod.create_todo(
            self.plans, "work", "Long task")
        self.assertFalse(self.row_path(
            att.row_id("fixture-proj", todo["id"]))
            .exists())
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing")
        self.assertEqual(moved["progress_check"], "15m")
        self.assertEqual(
            moved["attention_row"]["action"], "written")
        rid = att.row_id("fixture-proj", todo["id"])
        row = json.loads(self.row_path(rid).read_text(
            encoding="utf-8"))
        self.assertEqual(row["cadence"], "15m")
        self.assertEqual(row["cadence_minutes"], 15)
        self.assertEqual(row["handle"], todo["id"])
        out = bundle_mod.set_todo_status(
            self.plans, todo["id"], "done")
        self.assertEqual(
            out["attention_row"]["action"], "removed")
        self.assertFalse(self.row_path(rid).exists())

    def test_blocked_move_retires_the_row(self):
        todo = self.make_armed()
        bundle_mod.set_todo_status(
            self.plans, todo["id"], "blocked")
        rid = att.row_id("fixture-proj", todo["id"])
        self.assertFalse(self.row_path(rid).exists())

    def test_opt_out_todo_never_writes_row(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        todo = bundle_mod.create_todo(
            self.plans, "work", "Unwatched task",
            no_progress=True)
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing")
        self.assertEqual(moved["progress_check"], "off")
        self.assertEqual(
            list(self.armed.glob("*.json"))
            if self.armed.is_dir() else [], [])


class TestSyncAll(SeamCase):
    def test_reconciles_both_directions(self):
        todo = self.make_armed()
        rid = att.row_id("fixture-proj", todo["id"])
        self.row_path(rid).unlink()  # drift: missing
        ghost = att.row_id(
            "fixture-proj", "t-01GHOST000000000000000000")
        self.armed.mkdir(parents=True, exist_ok=True)
        (self.armed / f"{ghost}.json").write_text(
            "{}\n", encoding="utf-8")
        out = att.sync_all([self.project()])
        self.assertIn(rid, out["written"])
        self.assertIn(ghost, out["removed"])
        self.assertTrue(self.row_path(rid).is_file())
        self.assertFalse(
            (self.armed / f"{ghost}.json").exists())


if __name__ == "__main__":
    unittest.main()
