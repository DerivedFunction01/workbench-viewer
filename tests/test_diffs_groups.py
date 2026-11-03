"""Repo-home spec §18.4 (B2 step 2): the untracked and
ignored groups over real git fixtures. Untracked files
render per-file as all-additions diffs under the peek
caps + secret policy and never enter the diff; ignored
files are listed when recently changed (mtime > HEAD
commit time), peekable, withheld when secret-shaped, and
NEVER diffed at any mode; a plan-declared file that is
git-ignored earns the warning.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from lib import diffs

PAST = "2026-10-20T12:00:00+00:00"


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


class GroupsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-diffg-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / ".gitignore").write_text(
            "ignored.log\n.env\n")
        (self.repo / "a.txt").write_text("one\ntwo\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base", date=PAST)
        self.wt = self.tmp / "wt-x"
        git(self.repo, "worktree", "add", "-b", "build/x",
            str(self.wt))
        (self.wt / "a.txt").write_text("one\nTWO\n")
        git(self.wt, "add", "a.txt")
        git(self.wt, "commit", "-m", "work")
        # Untracked: text, secret-shaped (not in
        # .gitignore), binary.
        (self.wt / "fresh.txt").write_text("hello\nworld\n")
        (self.wt / "credentials.txt").write_text("TOKEN=x\n")
        (self.wt / "raw.bin").write_bytes(b"\x00\x09\x08")
        # Ignored, edited after HEAD: a plain log + an
        # ignored .env. mtimes bumped past the HEAD commit
        # second so the derivation is clock-safe.
        (self.wt / "ignored.log").write_text("log line\n")
        (self.wt / ".env").write_text("TOKEN=x\n")
        bump = time.time() + 5
        os.utime(self.wt / "ignored.log", (bump, bump))
        os.utime(self.wt / ".env", (bump, bump))

    def by_path(self, result):
        return {f["path"]: f for f in result["files"]}


class TestUntracked(GroupsCase):
    def test_untracked_group(self):
        result = diffs.get_diff(self.repo, worktree="build/x")
        group = {u["path"]: u for u in result["untracked"]}
        self.assertEqual(
            set(group),
            {"fresh.txt", "credentials.txt", "raw.bin"})
        fresh = group["fresh.txt"]
        self.assertIsNone(fresh["withheld"])
        kinds = [ln["kind"] for h in fresh["hunks"]
                 for ln in h["lines"]]
        self.assertEqual(kinds, ["add", "add"])
        self.assertEqual(
            group["credentials.txt"]["withheld"], "secret")
        self.assertEqual(group["credentials.txt"]["hunks"],
                         [])
        self.assertTrue(group["raw.bin"]["is_binary"])
        # Untracked files are never in the diff itself.
        self.assertNotIn("fresh.txt", self.by_path(result))

    def test_untracked_absent_in_committed_mode(self):
        result = diffs.get_diff(
            self.repo, worktree="build/x", mode="committed")
        self.assertEqual(result["untracked"], [])


class TestIgnored(GroupsCase):
    def test_recently_changed_listed_not_diffed(self):
        result = diffs.get_diff(self.repo, worktree="build/x")
        group = {i["path"]: i
                 for i in result["ignored_changed"]}
        self.assertIn("ignored.log", group)
        self.assertIsNone(group["ignored.log"]["withheld"])
        # The ignored secret is listed but withheld.
        self.assertIn(".env", group)
        self.assertEqual(group[".env"]["withheld"], "secret")
        # Ignored files appear in NO diff, at any mode.
        for mode in ("working", "committed", "uncommitted"):
            r = diffs.get_diff(self.repo, worktree="build/x",
                               mode=mode)
            self.assertNotIn("ignored.log", self.by_path(r))
            self.assertNotIn(".env", self.by_path(r))

    def test_ignored_peek(self):
        peek = diffs.peek_file(
            self.repo, worktree="build/x", path="ignored.log")
        self.assertIsNone(peek["withheld"])
        self.assertEqual(
            peek["hunks"][0]["lines"][0]["text"], "log line")
        secret = diffs.peek_file(
            self.repo, worktree="build/x", path=".env")
        self.assertEqual(secret["withheld"], "secret")
        self.assertEqual(secret["hunks"], [])

    def test_old_ignored_file_not_listed(self):
        # An ignored file untouched since before HEAD is
        # not "recently changed".
        old = self.wt / "ignored.log"
        past = 1700000000
        os.utime(old, (past, past))
        result = diffs.get_diff(self.repo, worktree="build/x")
        paths = {i["path"] for i in result["ignored_changed"]}
        self.assertNotIn("ignored.log", paths)


class TestPlanIgnoredWarning(GroupsCase):
    def setUp(self):
        super().setUp()
        plans = self.repo / ".plans"
        plans.mkdir()
        (plans / "2026-10-25-thing.md").write_text(
            "# Thing\n\nStatus: in progress\n"
            "Worktree: build/x\n\n## Steps\n\n"
            "1. **Change a.** Do it.\n"
            "   files: `a.txt`, `ignored.log`\n"
            "   verify: tests\n"
            "   done when: done\n", encoding="utf-8")
        self.plans = plans

    def test_plan_file_ignored_warning(self):
        result = diffs.get_diff(
            self.repo, bundle="2026-10-25-thing",
            plans_dir=self.plans)
        kinds = {(w["kind"], w["path"])
                 for w in result["warnings"]}
        self.assertIn(("plan-file-ignored", "ignored.log"),
                      kinds)
        warning = next(w for w in result["warnings"]
                       if w["path"] == "ignored.log")
        self.assertIn("will not be committed",
                      warning["message"])


if __name__ == "__main__":
    unittest.main()
