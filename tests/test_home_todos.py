"""The lib/home.py todo seam, closed (live-work-tracking
spec §3.7): home todo counts read BUNDLE todo files; the
registry DB is only the fallback for a project with DB
todos and no file todos. Plus the §17 showcase riding on
the home row, and `wb activate` over the CLI.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lib import home as home_mod
from lib import registry as reg
from lib import sweep as sweep_mod

REPO = Path(__file__).resolve().parent.parent
WB = REPO / "wb"
PY = sys.executable


def todo_file(bundle_dir: Path, name: str, todo_id: str,
              status: str):
    todos = bundle_dir / "todos"
    todos.mkdir(parents=True, exist_ok=True)
    (todos / name).write_text(
        "---\n"
        f"id: {todo_id}\n"
        f"title: {name}\n"
        f"status: {status}\n"
        "created: 2026-10-25\nupdated: 2026-10-25\n"
        "---\nBody.\n", encoding="utf-8")


ID1 = "t-01K8Q0000000000000000000A1"
ID2 = "t-01K8Q0000000000000000000A2"
ID3 = "t-01K8Q0000000000000000000A3"


def make_project(ws: Path, *, with_bundles: bool) -> Path:
    root = ws / "alpha"
    (root / "workbench" / "entries").mkdir(parents=True)
    (root / "workbench" / "archive").mkdir()
    (root / ".plans").mkdir()
    (root / "workbench.yaml").write_text(
        "name: Alpha\nregistry: workbench/registry.db\n"
        "plans: .plans\nmockups: workbench/entries\n"
        "archive: workbench/archive\n", encoding="utf-8")
    db = root / "workbench" / "registry.db"
    reg.init_registry(db)
    reg.add_todo(db, "db-one", "DB todo one")
    reg.add_todo(db, "db-two", "DB todo two")
    if with_bundles:
        bundle = root / ".plans" / "2026-10-25-work"
        bundle.mkdir()
        (bundle / "plan.md").write_text(
            "# Work\n\nStatus: in progress\n"
            "Created: 2026-10-25\n", encoding="utf-8")
        todo_file(bundle, "t-a.md", ID1, "doing")
        todo_file(bundle, "t-b.md", ID2, "blocked")
        todo_file(bundle, "t-c.md", ID3, "done")
    return root


class HomeTodoSeamCase(unittest.TestCase):
    def row_for(self, with_bundles: bool):
        ws = Path(tempfile.mkdtemp(prefix="wb-home-todo-"))
        make_project(ws, with_bundles=with_bundles)
        result = sweep_mod.sweep([ws])
        feed = home_mod.home_feed(result.projects)
        return feed["projects"][0]

    def test_file_todos_supersede_db_counts(self):
        row = self.row_for(with_bundles=True)
        self.assertEqual(row["todos"]["source"], "files")
        self.assertEqual(row["todos"]["total"], 3)
        self.assertEqual(row["todos"]["counts"],
                         {"doing": 1, "blocked": 1,
                          "done": 1})

    def test_db_fallback_until_imported(self):
        row = self.row_for(with_bundles=False)
        self.assertEqual(row["todos"]["source"],
                         "db-fallback")
        self.assertEqual(row["todos"]["total"], 2)
        self.assertEqual(row["todos"]["counts"],
                         {"todo": 2})

    def test_showcase_rides_the_row(self):
        # The fixture is not a git repo: no worktree list,
        # but the checkout is the default worktree (§17.1)
        # and its showcase still resolves.
        row = self.row_for(with_bundles=True)
        self.assertEqual(row["worktrees"], [])
        showcase = row["showcase"]
        self.assertIsNotNone(showcase)
        self.assertEqual(showcase["source"], "unique")
        self.assertEqual(showcase["plan"]["title"], "Work")


class ActivateCliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir(parents=True)
        (self.root / "workbench.yaml").write_text(
            "name: Fixture\nplans: .plans\n")
        bundle = self.root / ".plans" / "2026-10-25-demo"
        bundle.mkdir(parents=True)
        (bundle / "plan.md").write_text(
            "# Demo\n\nStatus: draft\nCreated: 2026-10-25\n",
            encoding="utf-8")

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

    def test_activate_walk(self):
        # Show: nothing declared, plan not in progress.
        shown = json.loads(self.wb("activate").stdout)
        self.assertEqual(shown["source"], "none")
        # Set by slug.
        set_out = json.loads(
            self.wb("activate", "demo",
                    "--since", "2026-10-25").stdout)
        self.assertEqual(set_out["bundle"],
                         "2026-10-25-demo")
        declared_file = (self.root / ".plans"
                         / "active.yaml")
        self.assertTrue(declared_file.is_file())
        # Show: declared now wins.
        shown = json.loads(self.wb("activate").stdout)
        self.assertEqual(shown["source"], "declared")
        # Unknown bundle is refused with exit 2.
        r = self.wb("activate", "ghost", expect=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown bundle", r.stderr)
        # Clear, then show falls back to none.
        cleared = json.loads(
            self.wb("activate", "--clear").stdout)
        self.assertTrue(cleared["cleared"])
        self.assertFalse(declared_file.exists())
        shown = json.loads(self.wb("activate").stdout)
        self.assertEqual(shown["source"], "none")


if __name__ == "__main__":
    unittest.main()
