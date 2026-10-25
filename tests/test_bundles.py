"""Live-work-tracking spec §3 tests: the bundle parser
(lib/plans/bundles.py) and the bundle/todo writers
(lib/bundles.py) — bundle + todo creation with both
refusals, status moves, id uniqueness/ordering, invalid
front-matter surfacing as per-item errors, and the
DB-todo import (§3.7) against a temp registry fixture
(mock data only)."""

import tempfile
import unittest
from pathlib import Path

from lib import bundles as bundle_mod
from lib import registry as reg
from lib.plans import bundles as parser
from lib.plans.parser import parse_plan

TODO_A = """---
id: t-01K8Q00000000000000000000A
title: Alpha work
status: doing
feature: feat-a
plan: plan.md
plan_step: 2
worktree: build/alpha
created: 2026-10-24
updated: 2026-10-25
x-custom: preserved value
---
Alpha body.
"""

TODO_BAD_STATUS = """---
id: t-01K8Q00000000000000000000B
title: Broken status
status: waiting
created: 2026-10-24
updated: 2026-10-25
---
Broken body.
"""

TODO_NO_FM = "Just prose, no front-matter at all.\n"

PLAN = """# Bundle plan

Status: in progress
Created: 2026-10-24
Feature: feat-a

## Steps

1. **Do alpha.**
   files: a.py
   verify: tests
   done when: done
"""


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plans = Path(self.tmp.name) / ".plans"
        self.plans.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def make_bundle(self, name="2026-10-24-alpha"):
        d = self.plans / name
        write(d / "plan.md", PLAN)
        write(d / "todos" / "t-x-alpha.md", TODO_A)
        return d


class TestParser(Fixture):
    def test_bundle_with_plan_and_todos(self):
        self.make_bundle()
        bundles = parser.list_bundles(self.plans)
        self.assertEqual(len(bundles), 1)
        b = bundles[0]
        self.assertEqual(b["kind"], "bundle")
        self.assertEqual(b["id"], "2026-10-24-alpha")
        self.assertEqual(b["slug"], "alpha")
        self.assertFalse(b["archived"])
        self.assertEqual(b["feature"], "feat-a")
        self.assertEqual(b["plan"]["title"], "Bundle plan")
        self.assertEqual(b["plan"]["status_bucket"], "doing")
        self.assertEqual(b["plan"]["step_count"], 1)
        self.assertEqual(b["todo_count"], 1)
        self.assertEqual(b["open_count"], 1)
        self.assertEqual(b["errors"], [])
        todo = b["todos"][0]
        self.assertTrue(todo["valid"])
        self.assertEqual(todo["plan_step"], 2)
        self.assertEqual(todo["worktree"], "build/alpha")
        # unknown fields preserved (lossless rule)
        self.assertEqual(todo["fields"]["x-custom"],
                         "preserved value")

    def test_flat_and_finished_enumeration(self):
        write(self.plans / "2026-10-20-flat.md", PLAN)
        write(self.plans / "finished" / "2026-10-01-old.md",
              PLAN)
        done_bundle = self.plans / "finished" / "2026-10-02-done"
        write(done_bundle / "todos" / "t-x.md", TODO_A)
        self.make_bundle()
        bundles = parser.list_bundles(self.plans)
        kinds = {(b["id"], b["kind"], b["archived"])
                 for b in bundles}
        self.assertIn(("2026-10-20-flat.md", "flat-plan",
                       False), kinds)
        self.assertIn(("2026-10-01-old.md", "flat-plan",
                       True), kinds)
        self.assertIn(("2026-10-02-done", "bundle", True),
                      kinds)
        self.assertIn(("2026-10-24-alpha", "bundle", False),
                      kinds)
        # a plain working directory is NOT a bundle
        write(self.plans / "scratch" / "notes.md", PLAN)
        ids = [b["id"] for b in parser.list_bundles(
            self.plans)]
        self.assertNotIn("scratch", ids)

    def test_invalid_front_matter_surfaces_per_item(self):
        d = self.plans / "2026-10-24-mixed"
        write(d / "todos" / "t-good.md", TODO_A)
        write(d / "todos" / "t-bad.md", TODO_BAD_STATUS)
        write(d / "todos" / "t-nofm.md", TODO_NO_FM)
        bundles = parser.list_bundles(self.plans)
        self.assertEqual(len(bundles), 1)
        b = bundles[0]
        by_title = {t["path"]: t for t in b["todos"]}
        good = by_title["2026-10-24-mixed/todos/t-good.md"]
        bad = by_title["2026-10-24-mixed/todos/t-bad.md"]
        nofm = by_title["2026-10-24-mixed/todos/t-nofm.md"]
        self.assertTrue(good["valid"])
        self.assertFalse(bad["valid"])
        self.assertTrue(any("status" in e
                            for e in bad["errors"]))
        self.assertFalse(nofm["valid"])
        self.assertTrue(any("front-matter" in e
                            for e in nofm["errors"]))
        # the bundle aggregates errors; siblings unaffected
        self.assertEqual(len(b["errors"]),
                         len(bad["errors"]) + len(nofm["errors"]))
        todos = parser.list_todos(self.plans)
        self.assertEqual(len(todos), 3)
        doing = parser.list_todos(self.plans,
                                   status="doing")
        self.assertEqual([t["title"] for t in doing],
                         ["Alpha work"])

    def test_missing_plans_dir_is_empty(self):
        self.assertEqual(
            parser.list_bundles(self.plans / "nope"), [])


class TestWriters(Fixture):
    def test_bundle_new_plan_skeleton_and_refusal(self):
        result = bundle_mod.create_bundle(
            self.plans, "fresh", plan=True, feature="feat-a",
            today="2026-10-25")
        self.assertEqual(result["id"], "2026-10-25-fresh")
        bundle_dir = self.plans / "2026-10-25-fresh"
        self.assertTrue((bundle_dir / "todos").is_dir())
        skeleton = (bundle_dir / "plan.md").read_text()
        doc = parse_plan(skeleton)  # house header parses
        self.assertTrue(doc["conforming"])
        self.assertEqual(doc["fields"]["Feature"], "feat-a")
        with self.assertRaises(bundle_mod.BundleError):
            bundle_mod.create_bundle(self.plans, "fresh",
                                     today="2026-10-26")
        with self.assertRaises(bundle_mod.BundleError):
            bundle_mod.create_bundle(self.plans, "Bad Slug")

    def test_bundle_new_planless(self):
        result = bundle_mod.create_bundle(
            self.plans, "chore", today="2026-10-25")
        bundle_dir = Path(result["path"])
        self.assertTrue((bundle_dir / "todos").is_dir())
        self.assertFalse((bundle_dir / "plan.md").exists())
        self.assertFalse(result["plan"])

    def test_todo_new_complete_front_matter(self):
        bundle_mod.create_bundle(self.plans, "b1",
                                 today="2026-10-25")
        todo = bundle_mod.create_todo(
            self.plans, "b1", "Ship the shell", step=5,
            worktree="build/05", plan="plan.md",
            feature="viewer-build", body="The work.")
        self.assertTrue(todo["valid"], todo["errors"])
        self.assertEqual(todo["status"], "todo")
        self.assertEqual(todo["plan_step"], 5)
        todo_file = Path(todo["file"])
        self.assertTrue(todo_file.name.startswith(
            todo["id"] + "-ship-the-shell"))
        text = todo_file.read_text()
        for line in ("id: ", "title: Ship the shell",
                     "status: todo", "feature: viewer-build",
                     "plan: plan.md", "plan_step: 5",
                     "worktree: build/05", "created: ",
                     "updated: "):
            self.assertIn(line, text)
        self.assertIn("The work.", text)

    def test_todo_new_optionals_omitted_when_unset(self):
        bundle_mod.create_bundle(self.plans, "plain",
                                 today="2026-10-25")
        todo = bundle_mod.create_todo(self.plans, "plain",
                                      "Just a chore")
        text = Path(todo["file"]).read_text()
        for absent in ("feature:", "plan:", "plan_step:",
                       "worktree:"):
            self.assertNotIn(absent, text)
        self.assertIsNone(todo["feature"])
        self.assertIsNone(todo["plan"])

    def test_todo_new_defaults_from_bundle_plan(self):
        bundle_mod.create_bundle(self.plans, "planned",
                                 plan=True, feature="feat-z",
                                 today="2026-10-25")
        todo = bundle_mod.create_todo(self.plans, "planned",
                                      "Inherits defaults")
        self.assertEqual(todo["plan"], "plan.md")
        self.assertEqual(todo["feature"], "feat-z")

    def test_todo_new_duplicate_title_refused(self):
        bundle_mod.create_bundle(self.plans, "b1",
                                 today="2026-10-25")
        bundle_mod.create_todo(self.plans, "b1", "Same title")
        with self.assertRaises(bundle_mod.BundleError):
            bundle_mod.create_todo(self.plans, "b1",
                                   "same  TITLE")
        with self.assertRaises(bundle_mod.BundleError):
            bundle_mod.create_todo(self.plans, "nope",
                                   "Other title")

    def test_ids_unique_and_timestamp_ordered(self):
        bundle_mod.create_bundle(self.plans, "b1",
                                 today="2026-10-25")
        ids = []
        for i in range(12):
            todo = bundle_mod.create_todo(
                self.plans, "b1", f"Item {i}")
            ids.append(todo["id"])
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, sorted(ids))
        for todo_id in ids:
            self.assertRegex(
                todo_id, r"^t-[0-9A-HJKMNP-TV-Z]{26}$")
        self.assertEqual(
            parser.all_todo_ids(self.plans), set(ids))

    def test_todo_set_status_note_and_updated(self):
        bundle_mod.create_bundle(self.plans, "b1",
                                 today="2026-10-25")
        todo = bundle_mod.create_todo(self.plans, "b1",
                                      "Move me",
                                      body="Original body.")
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "blocked",
            note="Waiting on X.", today="2026-10-26")
        self.assertEqual(moved["status"], "blocked")
        self.assertEqual(moved["updated"], "2026-10-26")
        text = Path(todo["file"]).read_text()
        self.assertIn("Original body.", text)
        self.assertIn("Waiting on X.", text)
        done = bundle_mod.set_todo_status(
            self.plans, todo["id"], "done",
            note="Deployed 2026-10-26.")
        self.assertEqual(done["status"], "done")
        self.assertTrue(done["valid"], done["errors"])

    def test_todo_set_invalid_status_and_unknown_id(self):
        bundle_mod.create_bundle(self.plans, "b1",
                                 today="2026-10-25")
        todo = bundle_mod.create_todo(self.plans, "b1",
                                      "Stay put")
        with self.assertRaises(bundle_mod.BundleError):
            bundle_mod.set_todo_status(self.plans,
                                       todo["id"], "waiting")
        with self.assertRaises(bundle_mod.BundleError):
            bundle_mod.set_todo_status(
                self.plans, "t-01K8Q00000000000000000000Z",
                "done")
        after = parser.list_todos(self.plans)
        self.assertEqual(after[0]["status"], "todo")

    def test_todo_set_preserves_unknown_fields(self):
        d = self.plans / "2026-10-25-keep"
        write(d / "todos" / "t-a.md", TODO_A)
        todo_id = "t-01K8Q00000000000000000000A"
        bundle_mod.set_todo_status(self.plans, todo_id,
                                   "done")
        kept = parser.list_todos(self.plans)[0]
        self.assertEqual(kept["fields"]["x-custom"],
                         "preserved value")
        self.assertEqual(kept["status"], "done")
        self.assertIn("Alpha body.", kept["body"])


class TestImport(Fixture):
    def setUp(self):
        super().setUp()
        self.db = Path(self.tmp.name) / "workbench" \
            / "registry.db"
        reg.init_registry(self.db)
        reg.add_todo(self.db, "mock-done", "Mock done item",
                     notes="Finished in the fixture.")
        reg.set_todo_status(self.db, "mock-done", "done")
        reg.add_todo(self.db, "mock-open", "Mock open item",
                     notes="Still open in the fixture.")
        reg.add_todo(self.db, "mock-doing",
                     "Mock doing item")
        reg.set_todo_status(self.db, "mock-doing", "doing")

    def test_import_mirrors_db_todos_db_untouched(self):
        before = reg.list_todos(self.db)
        result = bundle_mod.import_db_todos(
            self.plans, self.db, today="2026-10-25")
        self.assertEqual(result["bundle"],
                         "2026-10-25-project-zero-starter")
        self.assertTrue(result["bundle_created"])
        imported = {t["db_id"]: t
                    for t in result["imported"]}
        self.assertEqual(set(imported),
                         {"mock-done", "mock-open",
                          "mock-doing"})
        self.assertEqual(imported["mock-done"]["status"],
                         "done")
        self.assertEqual(imported["mock-open"]["status"],
                         "todo")
        self.assertEqual(imported["mock-doing"]["status"],
                         "doing")
        todos = parser.list_todos(
            self.plans, bundle=result["bundle"])
        self.assertEqual(len(todos), 3)
        for t in todos:
            self.assertTrue(t["valid"], t["errors"])
        done = [t for t in todos
                if t["title"] == "Mock done item"][0]
        self.assertIn("Finished in the fixture.",
                      done["body"])
        # DB rows are NOT deleted or altered
        self.assertEqual(reg.list_todos(self.db), before)
        # a re-run imports nothing twice
        again = bundle_mod.import_db_todos(
            self.plans, self.db, today="2026-10-25")
        self.assertEqual(again["imported"], [])
        self.assertEqual(sorted(again["skipped"]),
                         ["mock-doing", "mock-done",
                          "mock-open"])
        self.assertEqual(len(parser.list_todos(self.plans)),
                         3)


if __name__ == "__main__":
    unittest.main()
