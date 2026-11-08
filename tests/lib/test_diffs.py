"""Repo-home spec §18 (B2 step 1): the diff engine over
real git fixtures. Proves the §18.3 modes (working
default, uncommitted, committed, range, single commit),
the §18.2 legs, plan narrowing via bundle `files:` lists
(§18.3), the per-file caps, and rename/binary handling.
Refusals: unknown anchor/mode/revision → DiffError 4xx.
(The §18.4 untracked/ignored groups: test_diffs_groups.)
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

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


class RepoCase(unittest.TestCase):
    """main: a.txt + bin.dat + old.txt committed in the
    past. build/x worktree: a committed change to a.txt,
    a staged change to staged.txt, an unstaged change to
    unstaged.txt, a rename, a binary change."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-diff-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / ".gitignore").write_text(
            "ignored.log\n.env\n")
        (self.repo / "a.txt").write_text("one\ntwo\nthree\n")
        (self.repo / "staged.txt").write_text("s0\n")
        (self.repo / "unstaged.txt").write_text("u0\n")
        (self.repo / "old.txt").write_text("old\n")
        (self.repo / "bin.dat").write_bytes(b"\x00\x01\x02")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base", date=PAST)
        self.base_sha = git(self.repo, "rev-parse", "HEAD")
        self.wt = self.tmp / "wt-x"
        git(self.repo, "worktree", "add", "-b", "build/x",
            str(self.wt))
        # committed leg
        (self.wt / "a.txt").write_text("one\nTWO\nthree\n")
        git(self.wt, "add", "a.txt")
        git(self.wt, "commit", "-m", "committed work")
        self.work_sha = git(self.wt, "rev-parse", "HEAD")
        # rename + binary (committed) — before the staged
        # leg exists, so this commit cannot sweep it in.
        git(self.wt, "mv", "old.txt", "new.txt")
        (self.wt / "bin.dat").write_bytes(b"\x00\x03\x04\x05")
        git(self.wt, "add", "bin.dat")
        git(self.wt, "commit", "-m", "rename + binary")
        self.head_sha = git(self.wt, "rev-parse", "HEAD")
        # staged leg
        (self.wt / "staged.txt").write_text("s1\n")
        git(self.wt, "add", "staged.txt")
        # unstaged leg
        (self.wt / "unstaged.txt").write_text("u1\n")

    def by_path(self, result):
        return {f["path"]: f for f in result["files"]}


class TestModes(RepoCase):
    def test_working_default_dirty_worktree(self):
        result = diffs.get_diff(self.repo, worktree="build/x")
        self.assertEqual(result["mode"], "working")
        self.assertEqual(result["anchor"]["branch"], "build/x")
        files = self.by_path(result)
        self.assertEqual(
            set(files), {"a.txt", "staged.txt", "unstaged.txt",
                         "new.txt", "bin.dat"})
        self.assertIn("committed", files["a.txt"]["legs"])
        self.assertEqual(files["staged.txt"]["legs"],
                         ["staged"])
        self.assertEqual(files["unstaged.txt"]["legs"],
                         ["unstaged"])
        a = files["a.txt"]
        kinds = [ln["kind"] for h in a["hunks"]
                 for ln in h["lines"]]
        self.assertIn("add", kinds)
        self.assertIn("del", kinds)
        add = next(ln for h in a["hunks"] for ln in h["lines"]
                   if ln["kind"] == "add")
        self.assertEqual(add["text"], "TWO")
        self.assertEqual(add["new_no"], 2)
        self.assertIsNone(add["old_no"])
        self.assertFalse(result["empty"])
        self.assertEqual(result["totals"]["files"], 5)

    def test_working_clean_main_is_honestly_empty(self):
        result = diffs.get_diff(self.repo)
        self.assertEqual(result["anchor"]["branch"], "main")
        self.assertTrue(result["empty"])
        self.assertEqual(result["files"], [])
        self.assertEqual(result["base"], "HEAD")

    def test_uncommitted_only(self):
        result = diffs.get_diff(
            self.repo, worktree="build/x", mode="uncommitted")
        self.assertEqual(set(self.by_path(result)),
                         {"staged.txt", "unstaged.txt"})

    def test_committed_only(self):
        result = diffs.get_diff(
            self.repo, worktree="build/x", mode="committed")
        self.assertEqual(set(self.by_path(result)),
                         {"a.txt", "new.txt", "bin.dat"})

    def test_committed_on_base_branch_refused(self):
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, mode="committed")
        self.assertEqual(cm.exception.status, 400)

    def test_range_mode(self):
        result = diffs.get_diff(
            self.repo, worktree="build/x", mode="range",
            base=self.base_sha, target=self.work_sha)
        self.assertEqual(set(self.by_path(result)), {"a.txt"})
        self.assertEqual(result["anchor"]["kind"], "commit")

    def test_single_commit_mode(self):
        result = diffs.get_diff(
            self.repo, worktree="build/x", mode="commit",
            base=self.work_sha)
        self.assertEqual(set(self.by_path(result)), {"a.txt"})

    def test_root_commit_mode(self):
        result = diffs.get_diff(
            self.repo, mode="commit", base=self.base_sha)
        paths = set(self.by_path(result))
        self.assertIn("a.txt", paths)
        self.assertIn(".gitignore", paths)

    def test_rename_and_binary(self):
        result = diffs.get_diff(self.repo, worktree="build/x")
        files = self.by_path(result)
        renamed = files["new.txt"]
        self.assertEqual(renamed["status"], "renamed")
        self.assertEqual(renamed["old_path"], "old.txt")
        binary = files["bin.dat"]
        self.assertTrue(binary["binary"])
        self.assertEqual(binary["hunks"], [])
        self.assertEqual(binary["additions"], 0)

    def test_unknowns_are_4xx(self):
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, worktree="nope")
        self.assertEqual(cm.exception.status, 404)
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, mode="sideways")
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, mode="range",
                           base=self.base_sha)
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, mode="range",
                           base="--upload-pack=x",
                           target=self.base_sha)
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, mode="commit",
                           base="deadbeef" * 5)
        self.assertEqual(cm.exception.status, 400)


class TestCaps(RepoCase):
    def test_line_cap_truncates(self):
        big = self.tmp / "wt-big"
        git(self.repo, "worktree", "add", "-b", "build/big",
            str(big))
        lines = [f"line {i}" for i in range(3000)]
        (big / "a.txt").write_text("\n".join(lines) + "\n")
        result = diffs.get_diff(self.repo,
                                worktree="build/big")
        entry = self.by_path(result)["a.txt"]
        self.assertTrue(entry["truncated"])
        shown = sum(len(h["lines"]) for h in entry["hunks"])
        self.assertLessEqual(shown, diffs.MAX_LINES)


class TestBundleAnchor(RepoCase):
    def setUp(self):
        super().setUp()
        plans = self.repo / ".plans"
        plans.mkdir()
        (plans / "2026-10-25-thing.md").write_text(
            "# Thing\n\nStatus: in progress\n"
            "Worktree: build/x\n\n## Steps\n\n"
            "1. **Change a.** Do it.\n"
            "   files: `a.txt`, `ignored.log`, "
            "`staged.txt`\n"
            "   verify: tests\n"
            "   done when: done\n", encoding="utf-8")
        self.plans = plans

    def test_bundle_narrows_to_declared_files(self):
        result = diffs.get_diff(
            self.repo, bundle="2026-10-25-thing.md",
            plans_dir=self.plans)
        self.assertEqual(result["anchor"]["kind"], "bundle")
        # The bundle's Worktree: header selected build/x.
        self.assertEqual(result["anchor"]["branch"], "build/x")
        self.assertTrue(result["narrowed"])
        self.assertEqual(set(self.by_path(result)),
                         {"a.txt", "staged.txt"})
        self.assertEqual(
            set(result["declared_files"]),
            {"a.txt", "ignored.log", "staged.txt"})

    def test_bundle_all_files_widens(self):
        result = diffs.get_diff(
            self.repo, bundle="2026-10-25-thing",
            plans_dir=self.plans, all_files=True)
        self.assertFalse(result["narrowed"])
        self.assertIn("unstaged.txt", self.by_path(result))

    def test_unknown_bundle_404(self):
        with self.assertRaises(diffs.DiffError) as cm:
            diffs.get_diff(self.repo, bundle="nope",
                           plans_dir=self.plans)
        self.assertEqual(cm.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
