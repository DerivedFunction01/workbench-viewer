"""Repo-home spec §4: the workspace home feed.

Fixture workspace with three projects: alpha (git repo,
in-progress plan, registry todos, an unexplored entry to
triage), beta (manifest only — sections unavailable, not
degraded), gamma (corrupt registry file — its own row
degrades, the feed survives). Proves row shape, counts,
in-progress showcase selection (D1), sort order, and
per-project containment.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib import home as home_mod
from lib import registry as reg
from lib import sweep as sweep_mod


def git(cwd, *args):
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if out.returncode != 0:
        raise AssertionError(out.stderr)


def make_alpha(ws) -> Path:
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
    layout = (root / "workbench" / "entries",
              root / "workbench" / "archive")
    reg.add_entry(db, layout, "tile-a", title="Tile A")
    reg.add_todo(db, "do-thing", "Do the thing")
    t2 = reg.add_todo(db, "doing-thing", "Doing the thing")
    reg.set_todo_status(db, t2["id"], "doing", actor="cli")
    (root / ".plans" / "2026-10-25-alpha-plan.md").write_text(
        "# Alpha plan\n\nStatus: in progress\n"
        "Created: 2026-10-25\n\n## Steps\n\n"
        "1. **Only step.** Do it.\n", encoding="utf-8")
    (root / ".plans" / "2026-10-24-old-plan.md").write_text(
        "# Old plan\n\nStatus: done\nCreated: 2026-10-24\n",
        encoding="utf-8")
    git(root, "init", "-b", "main")
    # Alpha is the fixture's ordinary headed repo: one
    # commit, so `git.head` is a real sha. (Before the
    # zero-commit fix this passed vacuously — head was
    # the truthy zero hash of an unborn HEAD.)
    git(root, "add", ".")
    git(root, "commit", "-m", "alpha base")
    return root


def make_beta(ws) -> Path:
    root = ws / "beta"
    root.mkdir()
    (root / "workbench.yaml").write_text(
        "name: Beta\n", encoding="utf-8")
    return root


def make_gamma(ws) -> Path:
    root = ws / "gamma"
    (root / "workbench").mkdir(parents=True)
    (root / "workbench.yaml").write_text(
        "name: Gamma\nregistry: workbench/registry.db\n",
        encoding="utf-8")
    (root / "workbench" / "registry.db").write_bytes(
        b"this is not sqlite")
    return root


class TestHomeFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-home-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        make_alpha(ws)
        make_beta(ws)
        make_gamma(ws)
        result = sweep_mod.sweep([ws])
        assert len(result.projects) == 3, result.errors
        cls.feed = home_mod.home_feed(result.projects)
        cls.rows = {r["slug"]: r
                    for r in cls.feed["projects"]}

    def test_alpha_row(self):
        row = self.rows["alpha"]
        self.assertFalse(row["degraded"], row["reasons"])
        self.assertEqual(row["git"]["branch"], "main")
        self.assertTrue(row["git"]["head"])
        self.assertEqual(row["plans"]["counts"]["doing"], 1)
        self.assertEqual(row["plans"]["counts"]["done"], 1)
        self.assertEqual(
            row["plans"]["in_progress"]["title"],
            "Alpha plan")
        self.assertEqual(row["todos"]["counts"]["todo"], 1)
        self.assertEqual(row["todos"]["counts"]["doing"], 1)
        self.assertGreaterEqual(
            row["review"]["triage_count"], 1)
        self.assertFalse(row["has_extra_worktrees"])
        self.assertTrue(row["last_activity"])

    def test_beta_row_unavailable_not_degraded(self):
        row = self.rows["beta"]
        self.assertFalse(row["plans"]["available"])
        self.assertFalse(row["todos"]["available"])
        self.assertFalse(row["review"]["available"])
        self.assertIsNone(row["git"])  # not a git repo
        self.assertFalse(row["degraded"])

    def test_gamma_row_degrades_alone(self):
        row = self.rows["gamma"]
        self.assertTrue(row["degraded"])
        self.assertTrue(row["reasons"])
        self.assertEqual(row["todos"]["total"], 0)
        # The feed itself is intact.
        self.assertEqual(len(self.feed["projects"]), 3)

    def test_sort_in_progress_first(self):
        order = [r["slug"] for r in self.feed["projects"]]
        self.assertEqual(order[0], "alpha")


if __name__ == "__main__":
    unittest.main()
