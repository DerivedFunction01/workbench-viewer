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


class ProgressCheckContext(unittest.TestCase):
    """`wb progress-check` reads a verdict from a pinned
    context only: the harness's scheduler entries pin
    --root, where a missing id is the quiet orphan zero.
    An unpinned (cwd-resolved) invocation whose id is
    absent from the ambient project fails loud — the id
    may live in any other project's store, so the
    ambient miss is no verdict (the phantom-stall
    shape: a done todo in one project read as orphaned
    from another project's directory)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.proj_a = base / "proj-a"
        self.proj_b = base / "proj-b"
        for root in (self.proj_a, self.proj_b):
            root.mkdir(parents=True)
            (root / "workbench.yaml").write_text(
                "name: Fixture\n"
                "registry: workbench/registry.db\n"
                "plans: .plans\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_wb(self, *argv, cwd=None, pin=None):
        cmd = [PY, str(WB)]
        if pin is not None:
            cmd += ["--root", str(pin)]
        cmd += list(argv)
        return subprocess.run(cmd, capture_output=True,
                              text=True, cwd=cwd)

    def make_done_todo(self, root):
        r = self.run_wb("bundle", "new", "work",
                        pin=root)
        bundle = json.loads(r.stdout)["id"]
        r = self.run_wb("todo", "new", bundle, "Task",
                        pin=root)
        todo = json.loads(r.stdout)
        self.run_wb("todo", "set", todo["id"], "done",
                    pin=root)
        return todo["id"]

    def test_pinned_miss_is_the_quiet_orphan_zero(self):
        r = self.run_wb("progress-check",
                        "t-01MISSING0000000000000000",
                        pin=self.proj_a)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("orphaned", r.stdout)

    def test_ambient_miss_fails_loud(self):
        todo_id = self.make_done_todo(self.proj_b)
        r = self.run_wb("progress-check", todo_id,
                        cwd=self.proj_a)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("proj-a", r.stdout)
        self.assertIn("pin the programme context",
                      r.stdout)

    def test_ambient_hit_verdicts_normally(self):
        todo_id = self.make_done_todo(self.proj_b)
        r = self.run_wb("progress-check", todo_id,
                        cwd=self.proj_b)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("not armed", r.stdout)


if __name__ == "__main__":
    unittest.main()
