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

REPO = Path(__file__).resolve().parent.parent
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

    def test_todo_import_db_cli(self):
        self.wb("init")
        self.wb("todo-add", "db-one", "DB one",
                "--notes", "From the fixture DB.")
        r = self.wb("todo", "import-db")
        result = json.loads(r.stdout)
        self.assertEqual(len(result["imported"]), 1)
        self.assertEqual(result["imported"][0]["db_id"],
                         "db-one")
        self.assertEqual(result["imported"][0]["status"],
                         "todo")
        r = self.wb("todo", "list")
        self.assertIn("DB one", r.stdout)
        # DB todo still listed by the legacy verb (not deleted)
        r = self.wb("todo-list")
        self.assertIn("DB one", r.stdout)


if __name__ == "__main__":
    unittest.main()
