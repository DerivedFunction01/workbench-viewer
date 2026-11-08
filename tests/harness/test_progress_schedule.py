"""Auto-created progress schedules (the owner's
2026-10-31 commission): arming a todo writes its
scheduler-registry entry in the same writer call,
disarming deletes it, `wb progress-check` renders the
stall verdict as an exit code, and the doctor flags
entry drift both ways. lib/progress/schedule.py is the
mechanism; the todo file stays the record of truth.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lib import bundles as bundle_mod  # noqa: E402
from lib import doctor  # noqa: E402
from lib.progress import schedule as ps  # noqa: E402
from lib.manifest import Manifest  # noqa: E402
from lib.sweep import Project  # noqa: E402

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
TODO_ID = "t-01K8Q00000000000000000000A"
ENTRY_ID = ps.entry_id("fixture-proj", TODO_ID)


def armed_todo(**over):
    todo = {
        "id": TODO_ID,
        "title": "Long work",
        "status": "doing",
        "bundle": "2026-11-01-work",
        "archived": False,
        "path": "2026-11-01-work/todos/t-a.md",
        "progress_check": "30m",
        "progress_armed": "2026-11-01T11:30:00+00:00",
        "body": "",
    }
    todo.update(over)
    return todo


class SeamCase(unittest.TestCase):
    """A tmp workspace + tmp jobs dir under the env
    seams (WB_WORKSPACE_ROOT / WB_SCHEDULER_JOBS_DIR),
    with one fixture project inside the workspace."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.ws = base / "ws"
        self.jobs = base / "jobs"
        self.jobs.mkdir(parents=True)
        self.proj = self.ws / "fixture-proj"
        self.plans = self.proj / ".plans"
        self.plans.mkdir(parents=True)
        (self.proj / "workbench.yaml").write_text(
            "name: Fixture Proj\nslug: fixture-proj\n"
            "plans: .plans\n", encoding="utf-8")
        (self.ws / "workbench-viewer").mkdir()
        patcher = mock.patch.dict(os.environ, {
            "WB_SCHEDULER_JOBS_DIR": str(self.jobs),
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

    def entry_path(self, eid=ENTRY_ID):
        return self.jobs / f"{eid}.yaml"

    def make_armed(self, **kw):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        return bundle_mod.create_todo(
            self.plans, "work", "Long task",
            status="doing", progress="30m", **kw)


class TestRender(unittest.TestCase):
    def test_entry_shape(self):
        text = ps.render_entry("fixture-proj",
                               "fixture-proj",
                               "workbench-viewer",
                               armed_todo())
        lines = text.splitlines()
        self.assertEqual(lines[0], f"id: {ENTRY_ID}")
        for needle in ("kind: scripted", "status: active",
                       "  type: interval", "  every: 30m",
                       "owner: none", "timeout_secs: 120",
                       "  when: on_failure",
                       "lifetime: until_complete",
                       "migrated: true",
                       "migrated_at: 2026-11-01",
                       "- ${WS}/workbench-viewer/wb",
                       "- --root",
                       "- ${WS}/fixture-proj",
                       "- progress-check",
                       f"- {TODO_ID}"):
            self.assertIn(needle, text)
        # No cwd field: the scheduler never expands
        # anchors in cwd, so one would reach the spawn
        # literally and fail (2026-11-08 diagnosis).
        self.assertNotIn("cwd:", text)

    def test_title_is_sanitized_and_quoted(self):
        text = ps.render_entry(
            "fixture-proj", "fixture-proj",
            "workbench-viewer",
            armed_todo(title="A: b #c 'quoted' @x"))
        title_line = next(
            line for line in text.splitlines()
            if line.startswith("title:"))
        self.assertTrue(title_line.startswith("title: '"))
        self.assertTrue(title_line.endswith("'"))
        self.assertNotIn("#", title_line)
        self.assertNotIn("@", title_line)

    def test_parse_entry_todo_id_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / f"{ENTRY_ID}.yaml"
            path.write_text(ps.render_entry(
                "fixture-proj", "fixture-proj",
                "workbench-viewer", armed_todo()),
                encoding="utf-8")
            self.assertEqual(
                ps.parse_entry_todo_id(path), TODO_ID)

    def test_parse_entry_todo_id_rejects_other_files(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "other.yaml"
            path.write_text("id: other\ntitle: 'x'\n",
                            encoding="utf-8")
            self.assertIsNone(ps.parse_entry_todo_id(path))


class TestSync(SeamCase):
    def test_arm_writes_then_unchanged_then_disarm(self):
        out = ps.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "written")
        self.assertTrue(self.entry_path().is_file())
        out = ps.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "unchanged")
        out = ps.sync_todo(
            self.plans, armed_todo(status="done"))
        self.assertEqual(out["action"], "removed")
        self.assertFalse(self.entry_path().exists())

    def test_blocked_and_archived_carry_no_entry(self):
        for over in ({"status": "blocked"},
                     {"archived": True}):
            out = ps.sync_todo(
                self.plans, armed_todo(**over))
            self.assertEqual(out["action"], "unchanged")
            self.assertFalse(self.entry_path().exists())

    def test_cadence_change_rewrites(self):
        ps.sync_todo(self.plans, armed_todo())
        before = self.entry_path().read_text(
            encoding="utf-8")
        admitted_line = next(
            line for line in before.splitlines()
            if line.startswith("migrated_at:"))
        out = ps.sync_todo(
            self.plans, armed_todo(progress_check="2h"))
        self.assertEqual(out["action"], "written")
        after = self.entry_path().read_text(
            encoding="utf-8")
        self.assertIn("every: 2h", after)
        # The rewrite follows the todo's new state but
        # carries the admission record: the migrated_at
        # of the first render survives it.
        self.assertIn(admitted_line, after)

    def test_no_jobs_dir_skips(self):
        with mock.patch.dict(
                os.environ,
                {"WB_SCHEDULER_JOBS_DIR": "/nonexistent/x"}):
            self.assertIsNone(ps.jobs_dir())
            out = ps.sync_todo(self.plans, armed_todo())
        self.assertEqual(out["action"], "skipped")

    def test_project_outside_workspace_skips(self):
        outside = Path(self.tmp.name) / "elsewhere"
        (outside / ".plans").mkdir(parents=True)
        (outside / "workbench.yaml").write_text(
            "name: X\n", encoding="utf-8")
        out = ps.sync_todo(outside / ".plans", armed_todo())
        self.assertEqual(out["action"], "skipped")


class TestWriters(SeamCase):
    def test_create_and_terminal_moves_sync_the_entry(self):
        todo = self.make_armed()
        self.assertEqual(
            todo["progress_entry"]["action"], "written")
        eid = ps.entry_id("fixture-proj", todo["id"])
        self.assertTrue(self.entry_path(eid).is_file())
        out = bundle_mod.set_todo_status(
            self.plans, todo["id"], "done")
        self.assertEqual(
            out["progress_entry"]["action"], "removed")
        self.assertFalse(self.entry_path(eid).exists())

    def test_blocked_move_removes_the_entry(self):
        todo = self.make_armed()
        bundle_mod.set_todo_status(
            self.plans, todo["id"], "blocked")
        eid = ps.entry_id("fixture-proj", todo["id"])
        self.assertFalse(self.entry_path(eid).exists())

    def test_unarmed_todo_writes_no_entry(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        todo = bundle_mod.create_todo(
            self.plans, "work", "Plain task")
        self.assertEqual(
            todo["progress_entry"]["action"], "unchanged")
        self.assertEqual(list(self.jobs.glob("*.yaml")),
                         [])

    def test_doing_move_without_flag_writes_entry(self):
        # End to end through the writer (2026-11-03): no
        # --progress anywhere, and the doing move still
        # produces the scheduler entry; the terminal
        # move still removes it.
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        todo = bundle_mod.create_todo(
            self.plans, "work", "Long task")
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing")
        self.assertEqual(moved["progress_check"], "15m")
        self.assertEqual(
            moved["progress_entry"]["action"], "written")
        eid = ps.entry_id("fixture-proj", todo["id"])
        self.assertTrue(self.entry_path(eid).is_file())
        out = bundle_mod.set_todo_status(
            self.plans, todo["id"], "done")
        self.assertEqual(
            out["progress_entry"]["action"], "removed")
        self.assertFalse(self.entry_path(eid).exists())

    def test_opt_out_todo_never_writes_entry(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        todo = bundle_mod.create_todo(
            self.plans, "work", "Unwatched task",
            no_progress=True)
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing")
        self.assertEqual(moved["progress_check"], "off")
        self.assertFalse(ps.is_armed(moved))
        self.assertEqual(list(self.jobs.glob("*.yaml")),
                         [])


class TestCheck(SeamCase):
    def test_fresh_armed_is_on_track(self):
        todo = self.make_armed(
            armed_at="2026-11-01T11:30:00+00:00")
        code, line = ps.check_todo(
            self.plans, todo["id"], now=NOW)
        self.assertEqual(code, 0)
        self.assertIn("on track", line)

    def test_stale_armed_exits_3_with_stall_line(self):
        todo = self.make_armed(
            armed_at="2026-11-01T08:00:00+00:00")
        code, line = ps.check_todo(
            self.plans, todo["id"], now=NOW)
        self.assertEqual(code, 3)
        self.assertIn("STALLED", line)
        self.assertIn(todo["id"], line)

    def test_unknown_and_disarmed_are_quiet_zero(self):
        code, line = ps.check_todo(
            self.plans, TODO_ID, now=NOW)
        self.assertEqual(code, 0)
        self.assertIn("not found", line)
        todo = self.make_armed()
        bundle_mod.set_todo_status(
            self.plans, todo["id"], "done")
        code, line = ps.check_todo(
            self.plans, todo["id"], now=NOW)
        self.assertEqual(code, 0)
        self.assertIn("not armed", line)


class TestSyncAll(SeamCase):
    def test_reconciles_both_directions(self):
        todo = self.make_armed()
        eid = ps.entry_id("fixture-proj", todo["id"])
        self.entry_path(eid).unlink()  # drift: missing
        ghost_id = ps.entry_id(
            "fixture-proj", "t-01GHOST000000000000000000")
        self.entry_path(ghost_id).write_text(
            ps.render_entry(
                "fixture-proj", "fixture-proj",
                "workbench-viewer",
                armed_todo(
                    id="t-01GHOST000000000000000000")),
            encoding="utf-8")
        out = ps.sync_all([self.project()])
        self.assertIn(eid, out["written"])
        self.assertIn(ghost_id, out["removed"])
        self.assertTrue(self.entry_path(eid).is_file())
        self.assertFalse(self.entry_path(ghost_id)
                         .exists())

    def test_admitted_entry_survives_reconcile(self):
        # The migrated_at on disk is the admission
        # record, not harness-derived state: a reconcile
        # must never rewrite an admitted entry to the
        # fresh render (that would falsify the date the
        # schedule went live).
        todo = self.make_armed()
        eid = ps.entry_id("fixture-proj", todo["id"])
        path = self.entry_path(eid)
        lines = path.read_text(
            encoding="utf-8").splitlines()
        path.write_text("\n".join(
            "migrated_at: 2026-11-02"
            if line.startswith("migrated_at:") else line
            for line in lines) + "\n", encoding="utf-8")
        out = ps.sync_all([self.project()])
        self.assertNotIn(eid, out["written"])
        self.assertIn("migrated_at: 2026-11-02",
                      path.read_text(encoding="utf-8"))


class TestDoctor(SeamCase):
    def findings(self):
        return doctor.progress_entry_findings(
            [self.project()])

    def test_missing_entry_is_flagged(self):
        todo = self.make_armed()
        self.entry_path(ps.entry_id(
            "fixture-proj", todo["id"])).unlink()
        found = self.findings()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["check"],
                         "todo-progress-entry-missing")

    def test_orphan_entry_is_flagged(self):
        ghost_id = ps.entry_id(
            "fixture-proj", "t-01GHOST000000000000000000")
        self.entry_path(ghost_id).write_text(
            ps.render_entry(
                "fixture-proj", "fixture-proj",
                "workbench-viewer",
                armed_todo(
                    id="t-01GHOST000000000000000000")),
            encoding="utf-8")
        found = self.findings()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["check"],
                         "todo-progress-entry-orphan")
        self.assertEqual(found[0]["project"],
                         "fixture-proj")

    def test_other_projects_entries_are_out_of_scope(self):
        # A partial sweep must not call another project's
        # entries orphaned (regression: the first doctor
        # wiring flagged every unswept project's live
        # entries, breaking the clean-fixture doctor
        # tests).
        other_id = ps.entry_id(
            "other-proj", "t-01OTHER00000000000000000")
        self.entry_path(other_id).write_text(
            ps.render_entry(
                "other-proj", "other-proj",
                "workbench-viewer",
                armed_todo(
                    id="t-01OTHER00000000000000000")),
            encoding="utf-8")
        self.assertEqual(self.findings(), [])

    def admit(self, eid=ENTRY_ID, schedule=True):
        """Model the scheduled state: the entry is born
        admitted (the owner's 2026-11-08 ruling), and
        the server's next-due table (state/ beside
        jobs/) carries the id."""
        if schedule:
            state = self.jobs.parent / "state"
            state.mkdir(exist_ok=True)
            (state / "next_due.json").write_text(
                json.dumps({eid: "2026-11-01T12:15:00Z"}),
                encoding="utf-8")

    def test_in_sync_is_silent(self):
        todo = self.make_armed()
        self.admit(ps.entry_id("fixture-proj", todo["id"]))
        self.assertEqual(self.findings(), [])

    def test_unadmitted_entry_is_flagged_unscheduled(self):
        # A pre-ruling render (migrated: false, no
        # migrated_at) that was never re-rendered: the
        # engine fires only migrated entries — existence
        # alone never meant watched (the 2026-11-08
        # diagnosis: 11 live entries, none ever fired).
        todo = self.make_armed()
        path = self.entry_path(ps.entry_id(
            "fixture-proj", todo["id"]))
        lines = path.read_text(
            encoding="utf-8").splitlines()
        path.write_text("\n".join(
            "migrated: false"
            if line.startswith("migrated:") else line
            for line in lines
            if not line.startswith("migrated_at:")) + "\n",
            encoding="utf-8")
        found = self.findings()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["check"],
                         "todo-progress-entry-unscheduled")
        self.assertIn("never admitted",
                      found[0]["detail"])

    def test_admitted_but_not_in_next_due_is_flagged(self):
        todo = self.make_armed()
        self.admit(ps.entry_id("fixture-proj", todo["id"]),
                   schedule=False)
        state = self.jobs.parent / "state"
        state.mkdir(exist_ok=True)
        (state / "next_due.json").write_text(
            json.dumps({"someone-else": "2026-11-01"}),
            encoding="utf-8")
        found = self.findings()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["check"],
                         "todo-progress-entry-unscheduled")
        self.assertIn("next-due", found[0]["detail"])

    def test_admitted_without_server_state_is_silent(self):
        # No readable next-due table: no verdict — the
        # migrated flag alone does not convict.
        todo = self.make_armed()
        self.admit(ps.entry_id("fixture-proj", todo["id"]),
                   schedule=False)
        self.assertEqual(self.findings(), [])

    def test_no_registry_is_silent(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-01")
        bundle_mod.create_todo(
            self.plans, "work", "Armed elsewhere",
            status="doing", progress="30m")
        with mock.patch.dict(
                os.environ,
                {"WB_SCHEDULER_JOBS_DIR":
                 str(self.ws / "no-scheduler-here")}):
            # A bogus override dir reads as no registry.
            self.assertIsNone(ps.jobs_dir())
            self.assertEqual(self.findings(), [])


@unittest.skipUnless(
    (REPO.parent / "scheduler" / "server").is_dir(),
    "sibling scheduler repo not present")
class TestSchedulerSchema(SeamCase):
    def test_rendered_entry_passes_the_real_validator(self):
        spec = importlib.util.spec_from_file_location(
            "scheduler_registry",
            REPO.parent / "scheduler" / "server"
            / "registry.py")
        registry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(registry)
        home = str(REPO.parent / "scheduler")
        anchors = registry.derive_anchors(
            home, str(self.ws))
        path = self.entry_path()
        path.write_text(ps.render_entry(
            "fixture-proj", "fixture-proj",
            "workbench-viewer", armed_todo()),
            encoding="utf-8")
        entries, errors = registry.load_dir(
            str(self.jobs), home, anchors=anchors)
        self.assertEqual(errors, [])
        self.assertIn(ENTRY_ID, entries)
        argv = entries[ENTRY_ID].data["run"]["argv"]
        self.assertEqual(argv[2], "--root")
        self.assertTrue(argv[3].endswith("fixture-proj"))
        self.assertEqual(argv[4], "progress-check")
        self.assertEqual(argv[5], TODO_ID)
        self.assertTrue(argv[0].endswith(
            "workbench-viewer/.venv/bin/python"))


if __name__ == "__main__":
    unittest.main()
