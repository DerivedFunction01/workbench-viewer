"""CLI tests for the bundle/file-todo verbs (spec §3.4):
`wb bundle new`, `wb todo new`, `wb todo set`,
`wb todo list`, `wb todo import-db` — including both
refusals (existing bundle slug, duplicate todo title)
and the invalid-status refusal, all with exit codes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
WB = REPO / "wb"
PY = sys.executable


class BundleCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir(parents=True)
        (self.root / "workbench.yaml").write_text(
            "name: Fixture\nregistry: workbench/registry.db\n"
            "plans: .plans\n")

    def tearDown(self):
        self.tmp.cleanup()

    def wb(self, *argv, expect=0):
        r = subprocess.run(
            [PY, str(WB), "--root", str(self.root), *argv],
            capture_output=True, text=True)
        if expect is not None:
            self.assertEqual(
                r.returncode, expect,
                f"wb {argv} -> {r.returncode}\n{r.stdout}\n"
                f"{r.stderr}")
        return r

    def test_bundle_todo_walk_and_refusals(self):
        r = self.wb("bundle", "new", "demo", "--plan",
                    "--feature", "feat-a")
        created = json.loads(r.stdout)
        self.assertTrue(created["plan"])
        bundle = created["id"]
        # refusal: existing slug
        r = self.wb("bundle", "new", "demo", expect=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("already exists", r.stderr)
        r = self.wb("todo", "new", bundle, "Ship the shell",
                    "--step", "5", "--worktree", "build/05")
        todo = json.loads(r.stdout)
        self.assertEqual(todo["status"], "todo")
        self.assertEqual(todo["plan"], "plan.md")
        self.assertEqual(todo["feature"], "feat-a")
        # refusal: duplicate title in the bundle
        r = self.wb("todo", "new", bundle, "Ship the shell",
                    expect=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("duplicate", r.stderr)
        # refusal: invalid status (argparse choices, exit 2)
        r = self.wb("todo", "set", todo["id"], "waiting",
                    expect=None)
        self.assertEqual(r.returncode, 2)
        # status moves + note lands in the body
        r = self.wb("todo", "set", todo["id"], "blocked",
                    "--note", "Blocked on the bridge.")
        moved = json.loads(r.stdout)
        self.assertEqual(moved["status"], "blocked")
        body = Path(todo["file"]).read_text()
        self.assertIn("Blocked on the bridge.", body)
        # list reads through the parser
        r = self.wb("todo", "list", "--bundle", bundle)
        self.assertIn(todo["id"], r.stdout)
        self.assertIn("blocked", r.stdout)
        r = self.wb("todo", "list", "--status", "blocked")
        self.assertIn("Ship the shell", r.stdout)
        r = self.wb("todo", "list", "--status", "done")
        self.assertIn("no file todos", r.stdout)

    def test_todo_progress_arm_and_disarm_walk(self):
        r = self.wb("bundle", "new", "watched")
        bundle = json.loads(r.stdout)["id"]
        # refusal: a cadence that is not a cadence
        r = self.wb("todo", "new", bundle, "Bad cadence",
                    "--progress", "soon", expect=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("cadence", r.stderr)
        r = self.wb("todo", "new", bundle, "Long work",
                    "--progress", "30m")
        todo = json.loads(r.stdout)
        self.assertEqual(todo["progress_check"], "30m")
        self.assertTrue(todo["progress_armed"])
        # a plain status move keeps the arming
        r = self.wb("todo", "set", todo["id"], "doing")
        moved = json.loads(r.stdout)
        self.assertEqual(moved["progress_check"], "30m")
        # the terminal move disarms in the same write
        r = self.wb("todo", "set", todo["id"], "done")
        moved = json.loads(r.stdout)
        self.assertIsNone(moved["progress_check"])
        self.assertIsNone(moved["progress_armed"])
        self.assertNotIn("progress_",
                         Path(todo["file"]).read_text())

    def test_todo_doing_move_auto_arms_cli(self):
        r = self.wb("bundle", "new", "auto")
        bundle = json.loads(r.stdout)["id"]
        r = self.wb("todo", "new", bundle, "Plain long work")
        todo = json.loads(r.stdout)
        self.assertIsNone(todo["progress_check"])
        # no --progress flag: the doing move arms at the
        # default cadence on its own
        r = self.wb("todo", "set", todo["id"], "doing")
        moved = json.loads(r.stdout)
        self.assertEqual(moved["progress_check"], "15m")
        self.assertTrue(moved["progress_armed"])
        # the opt-out replaces the arm
        r = self.wb("todo", "set", todo["id"], "doing",
                    "--no-progress")
        moved = json.loads(r.stdout)
        self.assertEqual(moved["progress_check"], "off")
        self.assertIsNone(moved["progress_armed"])
        # cadence + opt-out together are refused
        r = self.wb("todo", "set", todo["id"], "doing",
                    "--progress", "15m", "--no-progress",
                    expect=None)
        self.assertEqual(r.returncode, 2)

    def test_todo_import_db_cli(self):
        self.wb("init")
        # seed the DB directly through lib (the legacy wb
        # todo verbs are retired, §3.7 — the table stays)
        from lib import registry as reg
        db = self.root / "workbench" / "registry.db"
        reg.add_todo(db, "db-one", "DB one",
                     notes="From the fixture DB.")
        r = self.wb("todo", "import-db")
        result = json.loads(r.stdout)
        self.assertEqual(len(result["imported"]), 1)
        self.assertEqual(result["imported"][0]["db_id"],
                         "db-one")
        self.assertEqual(result["imported"][0]["status"],
                         "todo")
        r = self.wb("todo", "list")
        self.assertIn("DB one", r.stdout)
        # the DB row itself is untouched by the import
        rows = reg.list_todos(db)
        self.assertEqual([row["id"] for row in rows],
                         ["db-one"])
        # the retired legacy verb no longer exists
        r = self.wb("todo-list", expect=None)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
