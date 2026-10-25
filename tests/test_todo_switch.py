"""Subplan 07 read-switch tests (live-work spec §3.7):
the server's todo/board reads come from bundle todo FILES
through lib/plans/bundles.py; the registry DB is only the
fallback for a project with DB todos and no file todos;
invalid front-matter surfaces as feed errors, never a
silent skip; and the server's one todo mutation (board
drag) lands through the lib writer (lib.bundles) — the
same function `wb todo set` calls."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "server"))

from lib import bundles as bundle_mod  # noqa: E402
from lib import registry as reg  # noqa: E402
from lib.manifest import load_manifest  # noqa: E402

import server as server_mod  # noqa: E402


def make_project(root: Path, *, with_db_todos=True):
    root.mkdir(parents=True)
    (root / "workbench").mkdir()
    (root / ".plans").mkdir()
    (root / "workbench.yaml").write_text(
        "name: Fixture\nregistry: workbench/registry.db\n"
        "plans: .plans\n", encoding="utf-8")
    db = root / "workbench" / "registry.db"
    reg.init_registry(db)
    if with_db_todos:
        reg.add_todo(db, "db-one", "DB one")
        reg.add_todo(db, "db-two", "DB two")
    manifest = load_manifest(root / "workbench.yaml")
    return SimpleNamespace(slug="fixture", name="Fixture",
                           manifest=manifest)


class TodoSwitch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"

    def tearDown(self):
        self.tmp.cleanup()

    def _file_todo(self, project, title="File one", **kw):
        plans = project.manifest.plans
        if not any(plans.iterdir()):
            bundle_mod.create_bundle(plans, "work",
                                     today="2026-10-25")
        return bundle_mod.create_todo(
            plans, "work", title, **kw)

    def test_db_fallback_when_no_bundles(self):
        project = make_project(self.root)
        feed = server_mod.todos_feed(project)
        self.assertTrue(feed["available"])
        self.assertEqual(feed["source"], "db-fallback")
        self.assertEqual(
            [t["title"] for t in feed["todos"]],
            ["DB one", "DB two"])
        self.assertTrue(all(t["source"] == "db"
                            for t in feed["todos"]))

    def test_file_todos_supersede_db(self):
        project = make_project(self.root)
        self._file_todo(project)
        feed = server_mod.todos_feed(project)
        self.assertEqual(feed["source"], "files")
        self.assertEqual([t["title"] for t in feed["todos"]],
                         ["File one"])
        self.assertEqual(feed["todos"][0]["bundle"],
                         "2026-10-25-work")

    def test_no_todos_anywhere_is_empty_not_unavailable(self):
        project = make_project(self.root, with_db_todos=False)
        feed = server_mod.todos_feed(project)
        self.assertTrue(feed["available"])
        self.assertEqual(feed["todos"], [])

    def test_invalid_front_matter_surfaces_as_errors(self):
        project = make_project(self.root)
        plans = project.manifest.plans
        bundle_mod.create_bundle(plans, "work",
                                 today="2026-10-25")
        bad = (plans / "2026-10-25-work" / "todos"
               / "bad.md")
        bad.write_text("---\ntitle: Broken\nstatus: waiting\n"
                       "---\nbody\n", encoding="utf-8")
        feed = server_mod.todos_feed(project)
        self.assertEqual(feed["source"], "files")
        broken = [t for t in feed["todos"]
                  if t["title"] == "Broken"]
        self.assertEqual(len(broken), 1)  # present, not skipped
        self.assertFalse(broken[0]["valid"])
        self.assertTrue(broken[0]["errors"])
        self.assertTrue(feed["errors"])
        self.assertTrue(any("waiting" in e["error"]
                            for e in feed["errors"]))

    def test_server_mutation_calls_lib_writer(self):
        project = make_project(self.root)
        todo = self._file_todo(project)
        out = server_mod.todo_action(
            project, {"verb": "set-status", "id": todo["id"],
                      "status": "blocked",
                      "note": "Blocked on the bridge."})
        self.assertEqual(out["todo"]["status"], "blocked")
        text = Path(todo["file"]).read_text(encoding="utf-8")
        self.assertIn("status: blocked", text)
        self.assertIn("Blocked on the bridge.", text)
        feed = server_mod.todos_feed(project)
        self.assertEqual(feed["todos"][0]["status"],
                         "blocked")

    def test_server_mutation_refusals(self):
        project = make_project(self.root)
        todo = self._file_todo(project)
        with self.assertRaises(server_mod.ApiError) as cm:
            server_mod.todo_action(
                project, {"verb": "add", "id": "x",
                          "title": "retired verb"})
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(server_mod.ApiError) as cm:
            server_mod.todo_action(
                project, {"verb": "set-status",
                          "id": "t-unknown", "status": "done"})
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(server_mod.ApiError) as cm:
            server_mod.todo_action(
                project, {"verb": "set-status",
                          "id": todo["id"],
                          "status": "waiting"})
        self.assertEqual(cm.exception.status, 400)

    def test_plans_feed_carries_bundles_with_todos(self):
        project = make_project(self.root)
        self._file_todo(project)
        feed = server_mod.plans_feed(project)
        bundles = {b["id"]: b for b in feed["bundles"]}
        bundle = bundles["2026-10-25-work"]
        self.assertEqual(bundle["todo_count"], 1)
        self.assertEqual(bundle["todos"][0]["title"],
                         "File one")


if __name__ == "__main__":
    unittest.main()
