"""Repo-home spec §17: active-plan resolution.

Per-worktree, deterministic, provenance shown: declared
(active.yaml) > branch convention > unique in-progress >
recency (labeled) > honest none. Todos never vote. Each
worktree resolves from its OWN .plans/ — proven with a
real git repo + linked worktree whose .plans/ differ.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib import active as active_mod
from lib import worktrees as wt_mod


def git(cwd, *args):
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return out.stdout.strip()


def write_bundle(plans: Path, bundle_id: str, *,
                 status: str | None = "in progress",
                 plan: bool = True, mtime: float = None,
                 todo_status: str = None):
    d = plans / bundle_id
    (d / "todos").mkdir(parents=True, exist_ok=True)
    if plan:
        p = d / "plan.md"
        p.write_text(
            f"# {bundle_id}\n\nStatus: {status}\n"
            f"Created: 2026-10-25\n", encoding="utf-8")
        if mtime is not None:
            os.utime(p, (mtime, mtime))
    if todo_status is not None:
        (d / "todos" / "t-AAA-one.md").write_text(
            "---\n"
            "id: t-01K8Q0000000000000000000AA\n"
            "title: A todo\n"
            f"status: {todo_status}\n"
            "created: 2026-10-25\nupdated: 2026-10-25\n"
            "---\nBody.\n", encoding="utf-8")
    return d


class ResolutionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-active-"))
        self.plans = self.tmp / ".plans"
        self.plans.mkdir()

    def test_unique_in_progress(self):
        write_bundle(self.plans, "2026-10-25-alpha",
                     status="in progress")
        write_bundle(self.plans, "2026-10-25-beta",
                     status="draft")
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "unique")
        self.assertEqual(r["bundle"]["slug"], "alpha")
        self.assertEqual(r["plan"]["title"], "2026-10-25-alpha")
        self.assertEqual(r["also_in_progress"], [])

    def test_recency_breaks_ties_and_labels_itself(self):
        write_bundle(self.plans, "2026-10-25-alpha",
                     mtime=1000)
        write_bundle(self.plans, "2026-10-25-beta",
                     mtime=2000)
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "recency")
        self.assertEqual(r["bundle"]["slug"], "beta")
        self.assertEqual(
            [a["bundle"]["slug"]
             for a in r["also_in_progress"]], ["alpha"])

    def test_branch_convention_beats_recency(self):
        write_bundle(self.plans, "2026-10-25-alpha",
                     mtime=2000)
        write_bundle(self.plans, "2026-10-25-beta",
                     mtime=1000)
        r = active_mod.resolve_active(
            self.plans, branch="build/beta")
        self.assertEqual(r["source"], "branch")
        self.assertEqual(r["bundle"]["slug"], "beta")
        self.assertEqual(
            [a["bundle"]["slug"]
             for a in r["also_in_progress"]], ["alpha"])

    def test_declared_beats_branch_and_recency(self):
        write_bundle(self.plans, "2026-10-25-alpha",
                     mtime=1000)
        write_bundle(self.plans, "2026-10-25-beta",
                     mtime=2000)
        active_mod.set_active(self.plans, "alpha",
                              since="2026-10-25")
        r = active_mod.resolve_active(
            self.plans, branch="build/beta")
        self.assertEqual(r["source"], "declared")
        self.assertEqual(r["bundle"]["slug"], "alpha")
        self.assertEqual(r["declared"]["since"], "2026-10-25")

    def test_declared_planless_bundle(self):
        write_bundle(self.plans, "2026-10-25-chores",
                     plan=False, todo_status="doing")
        active_mod.set_active(self.plans, "chores")
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "declared")
        self.assertEqual(r["bundle"]["slug"], "chores")
        self.assertIsNone(r["plan"])

    def test_broken_declaration_falls_through_with_note(self):
        write_bundle(self.plans, "2026-10-25-alpha")
        (self.plans / "active.yaml").write_text(
            "bundle: 2026-10-25-ghost\nsince: 2026-10-25\n",
            encoding="utf-8")
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "unique")
        self.assertIn("ghost", r["note"])

    def test_malformed_declaration_falls_through(self):
        write_bundle(self.plans, "2026-10-25-alpha")
        (self.plans / "active.yaml").write_text(
            "not a key value file\n", encoding="utf-8")
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "unique")
        self.assertIn("active.yaml", r["note"])

    def test_none_is_honest(self):
        write_bundle(self.plans, "2026-10-25-alpha",
                     status="draft")
        r = active_mod.resolve_active(
            self.plans, branch="build/elsewhere")
        self.assertEqual(r["source"], "none")
        self.assertIsNone(r["bundle"])
        self.assertIsNone(r["plan"])

    def test_todos_never_vote(self):
        # A bundle whose TODOS are doing but whose plan is
        # not in progress is not an in-progress plan.
        write_bundle(self.plans, "2026-10-25-alpha",
                     status="draft", todo_status="doing")
        write_bundle(self.plans, "2026-10-25-beta",
                     plan=False, todo_status="doing")
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "none")

    def test_finished_bundles_do_not_vote(self):
        fin = self.plans / "finished"
        write_bundle(fin, "2026-10-24-old",
                     status="in progress")
        write_bundle(self.plans, "2026-10-25-alpha",
                     status="draft")
        r = active_mod.resolve_active(self.plans)
        self.assertEqual(r["source"], "none")

    def test_set_active_refusals(self):
        write_bundle(self.plans, "2026-10-25-alpha")
        with self.assertRaises(active_mod.ActiveError):
            active_mod.set_active(self.plans, "ghost")
        with self.assertRaises(active_mod.ActiveError):
            active_mod.set_active(
                self.plans, "alpha", plan="other.md")
        result = active_mod.set_active(
            self.plans, "alpha",
            plan="2026-10-25-alpha/plan.md")
        self.assertEqual(result["bundle"],
                         "2026-10-25-alpha")
        cleared = active_mod.clear_active(self.plans)
        self.assertTrue(cleared["cleared"])
        cleared = active_mod.clear_active(self.plans)
        self.assertFalse(cleared["cleared"])


class PerWorktreeCase(unittest.TestCase):
    def test_each_worktree_reads_its_own_plans(self):
        tmp = Path(tempfile.mkdtemp(prefix="wb-active-wt-"))
        root = tmp / "proj"
        root.mkdir()
        (root / "README.md").write_text("x\n")
        git(root, "init", "-b", "main")
        git(root, "add", ".")
        git(root, "commit", "-m", "base")
        main_plans = root / ".plans"
        write_bundle(main_plans, "2026-10-25-alpha")
        wt_path = tmp / "proj-beta"
        git(root, "worktree", "add", "-b", "build/beta",
            str(wt_path))
        wt_plans = wt_path / ".plans"
        write_bundle(wt_plans, "2026-10-25-beta")
        write_bundle(wt_plans, "2026-10-25-alpha",
                     status="draft")

        result = wt_mod.list_worktrees(
            root, plans_dir=main_plans)
        self.assertTrue(result["available"])
        actives = active_mod.active_by_worktree(
            root, main_plans, result["worktrees"])
        by_main = {a["is_main"]: a for a in actives}
        # Main checkout: its own .plans/ -> alpha (unique).
        self.assertEqual(
            by_main[True]["active"]["bundle"]["slug"],
            "alpha")
        self.assertEqual(by_main[True]["active"]["source"],
                         "unique")
        # Linked worktree: branch build/beta + its own
        # .plans/ -> beta by branch convention.
        self.assertEqual(
            by_main[False]["active"]["bundle"]["slug"],
            "beta")
        self.assertEqual(by_main[False]["active"]["source"],
                         "branch")


if __name__ == "__main__":
    unittest.main()
