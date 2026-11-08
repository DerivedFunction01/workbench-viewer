"""lib/repos: the repo census and the status /
publication / exposure derivations (absorption plan,
steps 2-3). Fixtures are real git repos built in temp
dirs — the derivations shell out to git, so nothing less
than a real repo exercises them honestly."""

import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from lib import repos as repos_mod

_GIT_ENV = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}


def git(cwd, *args):
    out = subprocess.run(
        ["git", "-C", str(cwd),
         "-c", "user.name=Fixture",
         "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, env=_GIT_ENV)
    if out.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: {out.stderr}")
    return out.stdout


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_repo(path, *, commits=1):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    for i in range(commits):
        write(path / "file.txt", f"content {i}\n")
        git(path, "add", "file.txt")
        git(path, "commit", "-m", f"commit {i}")
    return path


def make_tracked_pair(base):
    """(origin, clone): a bare origin with one commit and
    a clone tracking it, in sync."""
    origin = base / "origin.git"
    origin.mkdir(parents=True)
    git(origin, "init", "--bare", "-b", "main")
    seed = base / "seed"
    make_repo(seed)
    git(seed, "remote", "add", "origin", str(origin))
    git(seed, "push", "-u", "origin", "main")
    clone = base / "clone"
    subprocess.run(
        ["git", "clone", str(origin), str(clone)],
        capture_output=True, text=True, env=_GIT_ENV,
        check=True)
    return origin, clone


def record_for(root, repo_id):
    for rec in repos_mod.discover_repos(root):
        if rec["id"] == repo_id:
            return rec
    raise AssertionError(f"repo {repo_id} not discovered")


class TestCensus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ws"
        self.root.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_repos_and_skips_plain_dirs(self):
        make_repo(self.root / "alpha")
        make_repo(self.root / "group" / "beta")
        (self.root / "plain").mkdir()
        write(self.root / "plain" / "note.txt", "hi\n")
        found = repos_mod.discover_repos(self.root)
        self.assertEqual([r["id"] for r in found],
                         ["alpha", "group/beta"])
        alpha = found[0]
        self.assertEqual(alpha["name"], "alpha")
        self.assertFalse(alpha["is_worktree"])
        self.assertIsNone(alpha["parent_id"])
        self.assertEqual(alpha["root"],
                         str((self.root / "alpha").resolve()))

    def test_pruned_directories_are_never_entered(self):
        make_repo(self.root / "node_modules" / "dep")
        make_repo(self.root / ".venv-tools" / "hidden")
        make_repo(self.root / ".artifacts" / "snap")
        make_repo(self.root / "visible")
        found = repos_mod.discover_repos(self.root)
        self.assertEqual([r["id"] for r in found], ["visible"])

    def test_nested_repo_inside_repo_is_not_separate(self):
        make_repo(self.root / "outer")
        make_repo(self.root / "outer" / "inner")
        found = repos_mod.discover_repos(self.root)
        self.assertEqual([r["id"] for r in found], ["outer"])

    def test_depth_limit(self):
        make_repo(self.root / "a" / "b" / "c" / "deep")
        found = repos_mod.discover_repos(self.root, max_depth=3)
        self.assertEqual(found, [])
        found = repos_mod.discover_repos(self.root, max_depth=4)
        self.assertEqual([r["id"] for r in found],
                         ["a/b/c/deep"])

    def test_linked_worktree_attributed_to_parent(self):
        main = make_repo(self.root / "main-repo")
        wt = self.root / "main-repo-wt"
        git(main, "worktree", "add", str(wt), "-b", "side")
        found = {r["id"]: r
                 for r in repos_mod.discover_repos(self.root)}
        self.assertEqual(set(found),
                         {"main-repo", "main-repo-wt"})
        self.assertTrue(found["main-repo-wt"]["is_worktree"])
        self.assertEqual(found["main-repo-wt"]["parent_id"],
                         "main-repo")
        self.assertFalse(found["main-repo"]["is_worktree"])


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ws"
        self.root.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def summary(self, repo_id):
        return repos_mod.repo_summary(record_for(self.root,
                                                 repo_id))

    def test_clean_local_only_repo(self):
        make_repo(self.root / "solo", commits=2)
        s = self.summary("solo")
        self.assertIsNone(s["error"])
        self.assertEqual(s["branch"], "main")
        self.assertEqual(len(s["head"]), 40)
        self.assertEqual(s["head_full"], s["head"])
        self.assertEqual(s["head_short"], s["head"][:7])
        self.assertEqual(s["head_subject"], "commit 1")
        self.assertIsNone(s["upstream"])
        self.assertIsNone(s["ahead"])
        self.assertIsNone(s["behind"])
        self.assertEqual(s["dirty_counts"],
                         {"staged": 0, "unstaged": 0,
                          "untracked": 0})
        self.assertTrue(s["is_clean"])
        self.assertEqual(s["remotes"], [])
        self.assertEqual(s["publication"], "local_only")
        self.assertEqual(s["sync"]["state"], "local_only")
        # With no remote refs at all, every commit counts
        # as unpushed (the reference model counts the same
        # way); the state, not the count, carries the
        # local-only verdict.
        self.assertEqual(s["sync"]["unpushed_count"], 2)
        self.assertIsNotNone(s["sync"]["oldest_unpushed_at"])
        # Every commit is exposed: nothing is backed up.
        self.assertEqual(s["exposure"],
                         {"level": "local_only", "commits": 2,
                          "files": 0})
        self.assertIsNone(s["remote_view_as_of"])
        self.assertFalse(s["remote_stale"])

    def test_dirty_repo_counts_and_exposure(self):
        repo = make_repo(self.root / "dirty")
        write(repo / "staged.txt", "new\n")
        git(repo, "add", "staged.txt")
        write(repo / "file.txt", "changed\n")
        write(repo / "loose.txt", "untracked\n")
        s = self.summary("dirty")
        self.assertEqual(s["dirty_counts"],
                         {"staged": 1, "unstaged": 1,
                          "untracked": 1})
        self.assertFalse(s["is_clean"])
        # Local-only but dirty: the whole history still
        # outranks the uncommitted work in the reference
        # model; files counts the dirty total.
        self.assertEqual(s["exposure"]["level"], "local_only")
        self.assertEqual(s["exposure"]["files"], 3)

    def test_tracking_repo_in_sync_is_backed_up(self):
        _origin, _clone = make_tracked_pair(self.root)
        s = self.summary("clone")
        self.assertIsNone(s["error"])
        self.assertEqual(s["upstream"], "origin/main")
        self.assertEqual(s["ahead"], 0)
        self.assertEqual(s["behind"], 0)
        self.assertEqual(s["publication"], "tracking")
        self.assertEqual(s["sync"]["state"], "synced")
        self.assertEqual(s["sync"]["unpushed_count"], 0)
        self.assertEqual(s["exposure"]["level"], "backed_up")
        self.assertEqual(s["remotes"][0]["name"], "origin")
        self.assertIsNotNone(s["remote_view_as_of"])
        self.assertFalse(s["remote_stale"])

    def test_ahead_of_upstream(self):
        _origin, clone = make_tracked_pair(self.root)
        write(clone / "file.txt", "more\n")
        git(clone, "add", "file.txt")
        git(clone, "commit", "-m", "local work")
        s = self.summary("clone")
        self.assertEqual(s["ahead"], 1)
        self.assertEqual(s["behind"], 0)
        self.assertEqual(s["sync"]["state"], "ahead")
        self.assertEqual(s["sync"]["unpushed_count"], 1)
        self.assertIsNotNone(s["sync"]["oldest_unpushed_at"])
        self.assertEqual(s["exposure"],
                         {"level": "unbacked_commits",
                          "commits": 1, "files": 0})

    def test_remote_without_upstream(self):
        origin = self.root / "origin.git"
        origin.mkdir(parents=True)
        git(origin, "init", "--bare", "-b", "main")
        repo = make_repo(self.root / "no-up")
        git(repo, "remote", "add", "origin", str(origin))
        s = self.summary("no-up")
        self.assertEqual(s["publication"],
                         "remote_no_upstream")
        self.assertEqual(s["sync"]["state"], "no_upstream")
        self.assertIsNone(s["upstream"])

    def test_broken_repo_degrades_in_place(self):
        bad = self.root / "broken"
        (bad / ".git").mkdir(parents=True)
        s = self.summary("broken")
        self.assertEqual(s["id"], "broken")
        self.assertIsNotNone(s["error"])
        self.assertIsNone(s["branch"])
        self.assertIsNone(s["publication"])
        self.assertIsNone(s["exposure"])
        self.assertEqual(s["remotes"], [])


class TestFullStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ws"
        self.root.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def status(self, repo_id):
        return repos_mod.repo_status(record_for(self.root,
                                                repo_id))

    def test_groups_carry_numstat(self):
        repo = make_repo(self.root / "full")
        write(repo / "added.txt", "one\ntwo\n")
        git(repo, "add", "added.txt")
        write(repo / "file.txt", "content 0\nextra\n")
        write(repo / "loose.txt", "x\n")
        s = self.status("full")
        self.assertEqual([e["path"] for e in s["staged"]],
                         ["added.txt"])
        self.assertEqual(s["staged"][0]["insertions"], 2)
        self.assertEqual(s["staged"][0]["deletions"], 0)
        self.assertFalse(s["staged"][0]["is_binary"])
        self.assertEqual([e["path"] for e in s["unstaged"]],
                         ["file.txt"])
        self.assertEqual(s["unstaged"][0]["insertions"], 1)
        self.assertEqual([e["path"] for e in s["untracked"]],
                         ["loose.txt"])
        self.assertEqual(len(s["commits"]), 1)
        self.assertEqual(s["commits"][0]["subject"],
                         "commit 0")
        self.assertEqual(s["branches"], ["main"])
        self.assertEqual(s["default_branch"], "main")
        detail = s["branch_details"][0]
        self.assertEqual(detail["name"], "main")
        self.assertIsNone(detail["contained_in_default"])
        self.assertEqual(len(s["worktrees"]), 1)
        self.assertEqual(s["worktrees"][0]["branch"], "main")
        self.assertIn("captured_at", s)

    def test_worktrees_listed_for_parent(self):
        main = make_repo(self.root / "hub")
        wt = self.root / "hub-wt"
        git(main, "worktree", "add", str(wt), "-b", "side")
        write(wt / "side.txt", "side work\n")
        git(wt, "add", "side.txt")
        git(wt, "commit", "-m", "side commit")
        s = self.status("hub")
        branches = {w["branch"] for w in s["worktrees"]}
        self.assertEqual(branches, {"main", "side"})
        detail = {d["name"]: d for d in s["branch_details"]}
        # The side branch is not yet contained in main.
        self.assertFalse(detail["side"]
                         ["contained_in_default"])

    def test_full_tree_collapses_pruned_directories(self):
        repo = make_repo(self.root / "treeful")
        write(repo / "venv" / "lib" / "x.py", "x\n")
        write(repo / ".pytest_cache" / "v" / "cache" / "n", "n\n")
        write(repo / "src" / "real.py", "r\n")
        out = repos_mod.repo_files(
            {"id": "treeful", "root": str(repo)},
            include_all=True)
        folders = {f["path"]: f["collapsed"]
                   for f in out["folders"]}
        self.assertTrue(folders["venv"])
        self.assertTrue(folders[".pytest_cache"])
        self.assertNotIn("venv/lib", folders)
        self.assertNotIn(".pytest_cache/v", folders)
        self.assertIn("src", folders)
        self.assertFalse(folders["src"])

    def test_broken_repo_status_is_the_degraded_summary(self):
        bad = self.root / "broken"
        (bad / ".git").mkdir(parents=True)
        s = self.status("broken")
        self.assertIsNotNone(s["error"])
        self.assertNotIn("staged", s)


class TestRepoDir(unittest.TestCase):
    """The lazy tree's unit (datasets follow-up 1): one
    directory's immediate listing, classified from git's
    own enumerations."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ws"
        self.root.mkdir(parents=True)
        repo = make_repo(self.root / "dirs")
        write(repo / ".gitignore", "*.log\n")
        write(repo / "src" / "real.py", "r\n")
        git(repo, "add", "src/real.py")
        git(repo, "commit", "-m", "src")
        write(repo / "loose.txt", "x\n")
        write(repo / "src" / "loose2.py", "x\n")
        write(repo / "debug.log", "x\n")
        write(repo / "src" / "trace.log", "x\n")
        write(repo / "venv" / "lib" / "x.py", "x\n")
        write(repo / ".config" / "app.yml", "x\n")
        self.record = record_for(self.root, "dirs")

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_listing(self):
        out = repos_mod.repo_dir(self.record, "")
        self.assertEqual(out["dir"], "")
        kinds = {e["path"]: e["kind"] for e in out["entries"]}
        self.assertEqual(kinds["file.txt"], "tracked")
        self.assertEqual(kinds["loose.txt"], "untracked")
        self.assertEqual(kinds["debug.log"], "ignored")
        self.assertNotIn("src/real.py", kinds)
        folders = {f["path"]: f for f in out["folders"]}
        self.assertFalse(folders["src"]["collapsed"])
        self.assertTrue(folders["venv"]["collapsed"])
        self.assertTrue(folders[".config"]["hidden"])
        self.assertFalse(out["truncated"])

    def test_subdirectory_listing(self):
        out = repos_mod.repo_dir(self.record, "src")
        kinds = {e["path"]: e["kind"] for e in out["entries"]}
        self.assertEqual(kinds, {"src/real.py": "tracked",
                                 "src/loose2.py": "untracked",
                                 "src/trace.log": "ignored"})
        self.assertEqual(out["folders"], [])

    def test_bad_and_missing_directories(self):
        with self.assertRaises(ValueError):
            repos_mod.repo_dir(self.record, "../outside")
        with self.assertRaises(FileNotFoundError):
            repos_mod.repo_dir(self.record, "nope")
        with self.assertRaises(FileNotFoundError):
            repos_mod.repo_dir(self.record, "file.txt")

    def test_listing_cap_flags(self):
        with unittest.mock.patch.object(
                repos_mod, "DIR_LISTING_CAP", 2):
            out = repos_mod.repo_dir(self.record, "")
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(out["entries"]), 2)


if __name__ == "__main__":
    unittest.main()
