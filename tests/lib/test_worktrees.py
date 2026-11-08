"""Repo-home spec §6: worktree derivations over real git
fixtures (temp dirs). Proves: porcelain parsing, ahead/
behind vs base, dirty counts, merged-branch and untouched
staleness (derived "likely done"), plan `worktree:` header
attribution overriding convention, and per-worktree
degradation — a missing path and a mid-rebase worktree
degrade their own entries only.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import worktrees as wt

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
OLD = (NOW - timedelta(days=30)).strftime(
    "%Y-%m-%dT%H:%M:%S+00:00")
FRESH = (NOW - timedelta(days=1)).strftime(
    "%Y-%m-%dT%H:%M:%S+00:00")


def git(cwd, *args, date=None):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)}: {out.stderr}")
    return out.stdout.strip()


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-wt-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base", date=FRESH)

    def commit_file(self, where, name, text, message,
                    date=FRESH):
        (where / name).write_text(text)
        git(where, "add", ".")
        git(where, "commit", "-m", message, date=date)

    def by_branch(self, result):
        return {w["branch"]: w for w in result["worktrees"]}


class TestDerivations(RepoCase):
    def test_main_and_feature_worktree(self):
        wt_path = self.tmp / "wt-thing"
        git(self.repo, "worktree", "add", "-b", "build/thing",
            str(wt_path))
        self.commit_file(wt_path, "b.txt", "b\n", "work")
        result = wt.list_worktrees(self.repo, now=NOW)
        self.assertTrue(result["available"])
        entries = self.by_branch(result)
        main = entries["main"]
        self.assertTrue(main["is_main"])
        self.assertEqual(main["ahead"], 0)
        self.assertEqual(main["behind"], 0)
        self.assertFalse(main["dirty"])
        self.assertFalse(main["likely_done"])
        feat = entries["build/thing"]
        self.assertFalse(feat["is_main"])
        self.assertEqual(feat["base"], "main")
        self.assertEqual(feat["ahead"], 1)
        self.assertEqual(feat["behind"], 0)
        self.assertEqual(feat["untouched_days"], 1)
        self.assertFalse(feat["likely_done"])
        self.assertEqual(feat["attribution"]["source"],
                         "convention")
        # Dirt is counted, never written by the derivation.
        (wt_path / "c.txt").write_text("c\n")
        result = wt.list_worktrees(self.repo, now=NOW)
        feat = self.by_branch(result)["build/thing"]
        self.assertTrue(feat["dirty"])
        self.assertEqual(feat["changed_count"], 1)

    def test_merged_branch_is_likely_done(self):
        wt_path = self.tmp / "wt-old"
        git(self.repo, "worktree", "add", "-b", "old-feature",
            str(wt_path))
        self.commit_file(wt_path, "b.txt", "b\n", "work")
        git(self.repo, "merge", "--no-ff", "old-feature",
            "-m", "merge it")
        result = wt.list_worktrees(self.repo, now=NOW)
        feat = self.by_branch(result)["old-feature"]
        self.assertTrue(feat["merged"])
        self.assertTrue(feat["likely_done"])

    def test_untouched_branch_is_likely_done(self):
        wt_path = self.tmp / "wt-stale"
        git(self.repo, "worktree", "add", "-b", "stale-one",
            str(wt_path))
        self.commit_file(wt_path, "b.txt", "b\n", "old work",
                         date=OLD)
        result = wt.list_worktrees(self.repo, now=NOW)
        feat = self.by_branch(result)["stale-one"]
        self.assertFalse(feat["merged"])
        self.assertEqual(feat["untouched_days"], 30)
        self.assertTrue(feat["likely_done"])

    def test_plan_worktree_header_overrides(self):
        plans = self.repo / ".plans"
        plans.mkdir()
        (plans / "2026-10-25-thing.md").write_text(
            "# Thing\n\nStatus: in progress\n"
            "Worktree: build/thing\n\n## Steps\n",
            encoding="utf-8")
        wt_path = self.tmp / "wt-thing"
        git(self.repo, "worktree", "add", "-b", "build/thing",
            str(wt_path))
        result = wt.list_worktrees(self.repo, plans_dir=plans,
                                   now=NOW)
        feat = self.by_branch(result)["build/thing"]
        self.assertEqual(feat["attribution"]["source"],
                         "plan")
        self.assertEqual(feat["attribution"]["plan"],
                         "2026-10-25-thing.md")


class TestDegradation(RepoCase):
    def test_missing_worktree_path_degrades_alone(self):
        wt_path = self.tmp / "wt-gone"
        git(self.repo, "worktree", "add", "-b", "gone",
            str(wt_path))
        shutil.rmtree(wt_path)
        result = wt.list_worktrees(self.repo, now=NOW)
        entries = self.by_branch(result)
        self.assertTrue(entries["gone"]["degraded"])
        self.assertIn("missing",
                      entries["gone"]["reason"])
        self.assertFalse(entries["main"]["degraded"])
        self.assertEqual(entries["main"]["changed_count"], 0)

    def test_rebase_in_progress_degrades_alone(self):
        wt_path = self.tmp / "wt-rebase"
        git(self.repo, "worktree", "add", "-b", "rebasing",
            str(wt_path))
        gitdir = git(wt_path, "rev-parse",
                     "--absolute-git-dir")
        (Path(gitdir) / "rebase-merge").mkdir()
        result = wt.list_worktrees(self.repo, now=NOW)
        entries = self.by_branch(result)
        feat = entries["rebasing"]
        self.assertTrue(feat["rebase_in_progress"])
        self.assertTrue(feat["degraded"])
        self.assertIn("rebase", feat["reason"])
        self.assertFalse(entries["main"]["degraded"])

    def test_non_git_root_unavailable(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        result = wt.list_worktrees(plain, now=NOW)
        self.assertFalse(result["available"])
        self.assertEqual(result["worktrees"], [])
        self.assertTrue(result["reason"])

    def test_non_git_reason_is_a_label_not_stderr(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        result = wt.list_worktrees(plain, now=NOW)
        self.assertEqual(result["reason"],
                         "not a git repository")
        self.assertNotIn("fatal", result["reason"])


class TestZeroCommits(unittest.TestCase):
    """A repo whose branch has no commits yet (unborn
    HEAD) is a first-class state: head null + the
    no_commits marker, never degraded, never raw git
    error text as a reason."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-wt0-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "a.txt").write_text("a\n")
        (self.repo / "b.txt").write_text("b\n")

    def test_zero_commit_main_is_a_state(self):
        result = wt.list_worktrees(self.repo, now=NOW)
        self.assertTrue(result["available"])
        (entry,) = result["worktrees"]
        self.assertTrue(entry["is_main"])
        self.assertTrue(entry["no_commits"])
        self.assertIsNone(entry["head"])
        self.assertIsNone(entry["head_short"])
        self.assertIsNone(entry["last_commit_at"])
        self.assertIsNone(entry["untouched_days"])
        self.assertEqual(entry["ahead"], 0)
        self.assertEqual(entry["behind"], 0)
        self.assertFalse(entry["degraded"])
        self.assertIsNone(entry["reason"])
        self.assertFalse(entry["likely_done"])
        # The untracked files are still counted as dirt.
        self.assertTrue(entry["dirty"])
        self.assertEqual(entry["changed_count"], 2)

    def test_first_commit_clears_the_marker(self):
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "first", date=FRESH)
        result = wt.list_worktrees(self.repo, now=NOW)
        (entry,) = result["worktrees"]
        self.assertFalse(entry["no_commits"])
        self.assertIsNotNone(entry["head"])
        self.assertFalse(entry["degraded"])


if __name__ == "__main__":
    unittest.main()
