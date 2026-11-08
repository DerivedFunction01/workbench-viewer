"""Vanished references + commit-less repos (the
Changes-panel failure the owner hit on example-project,
2026-10-25): a zero-commit repo diffs against the empty
tree, a deleted worktree path returns a typed `gone`
payload, and a plan anchor whose document or declared
files vanished degrades to the un-narrowed diff /
a narrower set — never a 500, and raw git stderr
never appears in a payload or error message.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib import diffs

PAST = "2026-10-20T12:00:00+00:00"


def git(cwd, *args, date=None, check=True):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True, env=env)
    if check and out.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)}: {out.stderr}")
    return out.stdout.strip()


def by_path(result):
    return {f["path"]: f for f in result["files"]}


class TestZeroCommitDiff(unittest.TestCase):
    """main has NO commits: one file staged, one loose.
    The working diff runs against the empty tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-dz-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "staged.txt").write_text("s0\ns1\n")
        git(self.repo, "add", "staged.txt")
        (self.repo / "loose.txt").write_text("loose\n")

    def test_working_diff_against_empty_tree(self):
        result = diffs.get_diff(self.repo)
        self.assertTrue(result["no_commits"])
        self.assertFalse(result["gone"])
        self.assertIsNone(result["head"])
        self.assertEqual(result["base_kind"], "empty-tree")
        self.assertEqual(result["base"], "empty tree")
        self.assertIn("No commits yet", result["note"])
        files = by_path(result)
        self.assertEqual(set(files), {"staged.txt"})
        staged = files["staged.txt"]
        self.assertEqual(staged["status"], "added")
        self.assertEqual(staged["legs"], ["staged"])
        self.assertEqual(staged["additions"], 2)
        self.assertEqual(staged["deletions"], 0)
        # Untracked files keep their own group.
        self.assertEqual(
            [u["path"] for u in result["untracked"]],
            ["loose.txt"])
        # No raw git text anywhere in the payload.
        self.assertNotIn("fatal", json.dumps(result))

    def test_uncommitted_mode_same_empty_tree(self):
        result = diffs.get_diff(self.repo,
                                mode="uncommitted")
        self.assertEqual(result["base_kind"], "empty-tree")
        self.assertEqual(set(by_path(result)),
                         {"staged.txt"})

    def test_committed_mode_is_a_labelled_refusal(self):
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, mode="committed")
        self.assertEqual(cm.exception.status, 400)
        self.assertIn("no commits yet",
                      cm.exception.message)
        self.assertNotIn("fatal", cm.exception.message)


class TestMissingWorktreePath(unittest.TestCase):
    """A linked worktree whose directory was deleted
    without `git worktree remove`."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-dg-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base", date=PAST)
        self.wt = self.tmp / "wt-x"
        git(self.repo, "worktree", "add", "-b", "build/x",
            str(self.wt))
        shutil.rmtree(self.wt)

    def test_diff_returns_typed_gone_payload(self):
        result = diffs.get_diff(self.repo,
                                worktree="build/x")
        self.assertTrue(result["gone"])
        self.assertEqual(result["note"],
                         "worktree path missing")
        self.assertEqual(result["files"], [])
        self.assertTrue(result["empty"])
        self.assertEqual(result["anchor"]["branch"],
                         "build/x")
        self.assertNotIn("fatal", json.dumps(result))

    def test_main_diff_unaffected(self):
        result = diffs.get_diff(self.repo)
        self.assertFalse(result["gone"])
        self.assertFalse(result["no_commits"])


class TestVanishedPlanFiles(unittest.TestCase):
    """A plan declares a.txt (changed), doomed.txt
    (tracked, deleted in the worktree by later work)
    and ghost.txt (never existed)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-dp-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "a.txt").write_text("one\n")
        (self.repo / "doomed.txt").write_text("doomed\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base", date=PAST)
        (self.repo / "a.txt").write_text("one\ntwo\n")
        (self.repo / "doomed.txt").unlink()
        plans = self.repo / ".plans"
        plans.mkdir()
        (plans / "2026-10-25-thing.md").write_text(
            "# Thing\n\nStatus: in progress\n\n"
            "## Steps\n\n"
            "1. **Change things.** Do it.\n"
            "   files: `a.txt`, `doomed.txt`, "
            "`ghost.txt`\n"
            "   verify: tests\n"
            "   done when: done\n", encoding="utf-8")
        self.plans = plans

    def test_vanished_declared_paths_contribute_nothing(
            self):
        result = diffs.get_diff(
            self.repo, bundle="2026-10-25-thing",
            plans_dir=self.plans)
        self.assertTrue(result["narrowed"])
        files = by_path(result)
        # The changed file and the tracked deletion are
        # normal legs; the never-existent path is simply
        # absent — no error anywhere.
        self.assertEqual(set(files),
                         {"a.txt", "doomed.txt"})
        self.assertEqual(files["doomed.txt"]["status"],
                         "deleted")
        self.assertNotIn("fatal", json.dumps(result))

    def test_plan_document_gone_falls_back_unnarrowed(
            self):
        with mock.patch.object(
                diffs.plan_parser, "load_plan",
                side_effect=FileNotFoundError("gone")):
            result = diffs.get_diff(
                self.repo, bundle="2026-10-25-thing",
                plans_dir=self.plans)
        self.assertFalse(result["narrowed"])
        self.assertEqual(result["declared_files"], [])
        self.assertIn("no longer exists", result["note"])
        # The worktree's changes are still real.
        self.assertEqual(set(by_path(result)),
                         {"a.txt", "doomed.txt"})


if __name__ == "__main__":
    unittest.main()
