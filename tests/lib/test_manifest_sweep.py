"""Step 2 gate tests: manifest parsing (restricted YAML
subset) + the discovery sweep mechanics."""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from lib.manifest import ManifestError, load_manifest
from lib.sweep import sweep
from lib.worktrees import list_worktrees


def git(cwd, *args):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)}: {out.stderr}")
    return out.stdout.strip()


def make_repo(root: Path, name="Repo", slug="repo"):
    """A git repo carrying a committed manifest. The
    manifest is TRACKED, so a linked worktree checks out the
    same file under the same slug — the live duplicate-slug
    shape."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-b", "main")
    (root / "workbench.yaml").write_text(
        f"name: {name}\nslug: {slug}\n"
        "registry: workbench/registry.db\nplans: .plans\n")
    (root / "README.md").write_text("x\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    return root


def write_project(root: Path, name="Proj", extra=""):
    root.mkdir(parents=True, exist_ok=True)
    (root / "workbench.yaml").write_text(
        f"name: {name}\nregistry: workbench/registry.db\n"
        f"plans: .plans\n{extra}")
    return root


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, text):
        p = self.root / "workbench.yaml"
        p.write_text(text)
        return load_manifest(p)

    def test_full_manifest_and_defaults(self):
        m = self.load("name: My Project\n"
                      "registry: workbench/registry.db\n"
                      "plans: .plans\n")
        self.assertEqual(m.name, "My Project")
        self.assertEqual(m.slug, "proj")  # dir name default
        self.assertEqual(m.registry,
                         self.root / "workbench" / "registry.db")
        # mockups/archive default beside the registry
        self.assertEqual(m.mockups,
                         self.root / "workbench" / "entries")
        self.assertEqual(m.archive,
                         self.root / "workbench" / "archive")
        self.assertEqual(m.plans, self.root / ".plans")

    def test_explicit_slug_and_comments(self):
        m = self.load("# a comment\nname: X  # trailing\n"
                      "slug: custom-slug\n")
        self.assertEqual(m.slug, "custom-slug")
        self.assertIsNone(m.registry)
        self.assertIsNone(m.plans)

    def test_registration_posture(self):
        m = self.load("name: X\nregistration: as-is\n")
        self.assertTrue(m.registered_as_is)
        # Absent registration is a full adoption.
        m = self.load("name: X\n")
        self.assertFalse(m.registered_as_is)

    def test_catalog_classification(self):
        m = self.load(
            "name: X\ncatalog_origin: hand\n"
            "catalog_generality: parameterized\n"
            "catalog_use_case: work-tracking\n")
        self.assertEqual(m.catalog, {
            "origin": "hand",
            "generality": "parameterized",
            "use_case": "work-tracking",
        })

    def test_catalog_absent_is_unclassified(self):
        m = self.load("name: X\n")
        self.assertIsNone(m.catalog)

    def test_catalog_partial_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load("name: X\ncatalog_origin: hand\n")

    def test_catalog_bad_origin_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load(
                "name: X\ncatalog_origin: robot\n"
                "catalog_generality: parameterized\n"
                "catalog_use_case: work-tracking\n")

    def test_catalog_bad_generality_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load(
                "name: X\ncatalog_origin: hand\n"
                "catalog_generality: copyable\n"
                "catalog_use_case: work-tracking\n")

    def test_catalog_bad_use_case_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load(
                "name: X\ncatalog_origin: hand\n"
                "catalog_generality: parameterized\n"
                "catalog_use_case: Work Tracking\n")

    def test_unknown_key_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load("name: X\nregsitry: typo.db\n")

    def test_missing_name_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load("plans: .plans\n")

    def test_escaping_path_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load("name: X\nregistry: ../outside.db\n")

    def test_absolute_path_is_an_error(self):
        with self.assertRaises(ManifestError):
            self.load("name: X\nregistry: /etc/passwd\n")


class TestSweep(unittest.TestCase):
    def test_finds_projects_and_only_projects(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            write_project(ws / "alpha", "Alpha")
            write_project(ws / "beta", "Beta")
            (ws / "no-manifest").mkdir()
            # a manifest inside a pruned dir must not be found
            write_project(ws / ".venv" / "hidden", "Hidden")
            # nested inside a found repo: never descended into
            write_project(ws / "alpha" / "inner", "Inner")
            result = sweep([ws])
            slugs = sorted(p.slug for p in result.projects)
            self.assertEqual(slugs, ["alpha", "beta"])
            self.assertEqual(result.errors, [])

    def test_broken_manifest_is_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            write_project(ws / "good", "Good")
            bad = ws / "bad"
            bad.mkdir()
            (bad / "workbench.yaml").write_text("nope: 1\n")
            result = sweep([ws])
            self.assertEqual([p.slug for p in result.projects],
                             ["good"])
            self.assertEqual(len(result.errors), 1)
            self.assertIn("bad", result.errors[0]["manifest"])

    def test_depth_bound(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            deep = ws / "a" / "b" / "c" / "deep-proj"
            write_project(deep, "Deep")
            self.assertEqual(sweep([ws], max_depth=3).projects,
                             [])
            found = sweep([ws], max_depth=4)
            self.assertEqual([p.slug for p in found.projects],
                             ["deep-proj"])

    def test_sections_degrade_independently(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            proj = write_project(ws / "p", "P")
            (proj / ".plans").mkdir()
            result = sweep([ws])
            sections = result.projects[0].sections()
            # plans dir exists, DB does not: Plans yes, rest no
            self.assertTrue(sections["plans"])
            self.assertFalse(sections["mockups"])
            self.assertFalse(sections["artifacts"])
            self.assertTrue(sections["registry_declared"])

    def test_artifacts_section_tracks_mockups(self):
        """Artifacts rides the registry declaration (SPEC
        §14.4): reported exactly when Mockups is."""
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            proj = write_project(ws / "p", "P")
            (proj / "workbench").mkdir(exist_ok=True)
            (proj / "workbench" / "registry.db").write_bytes(b"")
            result = sweep([ws])
            sections = result.projects[0].sections()
            self.assertTrue(sections["mockups"])
            self.assertTrue(sections["artifacts"])


class TestSweepWorktreeDedupe(unittest.TestCase):
    """Repo identity, not directory identity: a linked
    worktree carrying the same tracked manifest must not
    register as a second project under the same slug."""

    def test_repo_plus_linked_worktree_is_one_project(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            repo = make_repo(ws / "repo")
            wt = ws / "repo-wt"
            git(repo, "worktree", "add", "-b", "build/x",
                str(wt))
            result = sweep([ws])
            self.assertEqual(result.errors, [])
            self.assertEqual([p.slug for p in result.projects],
                             ["repo"])
            self.assertEqual(result.projects[0].root,
                             repo.resolve())
            # the worktree stays visible through the main
            # checkout's worktree derivations
            derived = list_worktrees(result.projects[0].root)
            self.assertTrue(derived["available"])
            by_path = {w["path"]: w
                       for w in derived["worktrees"]}
            self.assertIn(str(wt), by_path)
            self.assertTrue(
                by_path[str(repo.resolve())]["is_main"])
            self.assertFalse(by_path[str(wt)]["is_main"])

    def test_worktree_seen_first_still_registers_main(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            repo = make_repo(ws / "z-area" / "repo")
            linked = ws / "a-area" / "linked"
            git(repo, "worktree", "add", "-b", "build/x",
                str(linked))
            # roots ordered so the worktree is walked first
            result = sweep([ws / "a-area", ws / "z-area"])
            self.assertEqual([p.slug for p in result.projects],
                             ["repo"])
            self.assertEqual(result.projects[0].root,
                             repo.resolve())

    def test_worktree_only_registers_main_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            repo = make_repo(ws / "z-area" / "repo")
            linked = ws / "a-area" / "linked"
            git(repo, "worktree", "add", "-b", "build/x",
                str(linked))
            # the main checkout is under no sweep root: the
            # identity still registers once, rooted at main
            result = sweep([ws / "a-area"])
            self.assertEqual(result.errors, [])
            self.assertEqual([p.slug for p in result.projects],
                             ["repo"])
            self.assertEqual(result.projects[0].root,
                             repo.resolve())

    def test_two_unrelated_repos_register_as_two(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            make_repo(ws / "one", name="One", slug="one")
            make_repo(ws / "two", name="Two", slug="two")
            result = sweep([ws])
            self.assertEqual(
                sorted(p.slug for p in result.projects),
                ["one", "two"])
            self.assertEqual(result.errors, [])


class TestSweepHygiene(unittest.TestCase):
    """Registration hygiene (2026-11-09): scratch trees
    inside a swept root never register, and standalone
    clones declaring one slug fold into one project."""

    def test_scratch_trees_never_register(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            write_project(ws / "real", "Real")
            # hidden tree (dot-directory component)
            write_project(ws / ".hidden-clone", "Hidden")
            # tmp-named tree
            write_project(ws / "tmp-fixtures" / "fix",
                          "Fixture")
            # scratch-named tree
            write_project(ws / "my-scratch" / "fix2",
                          "Fixture Two")
            result = sweep([ws])
            self.assertEqual([p.slug for p in result.projects],
                             ["real"])
            self.assertEqual(result.errors, [])

    def test_same_slug_clones_fold_to_most_recent(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            older = make_repo(ws / "copy-old", name="Proj",
                              slug="proj")
            newer = make_repo(ws / "copy-new", name="Proj",
                              slug="proj")
            old_t = 1_700_000_000
            new_t = old_t + 10_000
            for base, t in ((older, old_t), (newer, new_t)):
                os.utime(base / "workbench.yaml", (t, t))
                os.utime(base / ".git", (t, t))
            result = sweep([ws])
            self.assertEqual(result.errors, [])
            self.assertEqual(len(result.projects), 1)
            project = result.projects[0]
            self.assertEqual(project.slug, "proj")
            self.assertEqual(project.root, newer.resolve())
            self.assertEqual(project.also_at,
                             [older.resolve()])
            by = result.by_slug("proj")
            self.assertIs(by, project)


class TestSweepGitBudget(unittest.TestCase):
    """The sweep's aggregate git budget (wedge fix,
    2026-11-10): under a storage stall every git child
    burns its per-call timeout in sequence, so the bound
    that matters is the sweep's total. A parked git must
    degrade identity resolution (directory identity), not
    queue the sweep — and a healthy tree is untouched."""

    def test_parked_git_bounds_the_sweep(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            write_project(ws / "alpha")
            write_project(ws / "beta")

            def parked_run(*a, **kw):
                # Every git call parks past its (budget-
                # clamped) timeout and is killed there —
                # the storage-stall shape.
                time.sleep(kw["timeout"] + 0.05)
                raise subprocess.TimeoutExpired(
                    cmd=a[0], timeout=kw["timeout"])

            t0 = time.monotonic()
            with mock.patch("lib.sweep.subprocess.run",
                            side_effect=parked_run):
                result = sweep([ws], git_budget_s=0.6)
            elapsed = time.monotonic() - t0
            # The whole sweep's git work stayed at the
            # budget, not at per-call-timeout × calls.
            self.assertLess(elapsed, 2.0)
            # Both projects still register (identity
            # degraded to the directory path), no errors.
            self.assertEqual(
                sorted(p.slug for p in result.projects),
                ["alpha", "beta"])
            self.assertEqual(result.errors, [])

    def test_healthy_repo_identity_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            make_repo(ws / "repo")
            result = sweep([ws], git_budget_s=20.0)
            self.assertEqual(result.errors, [])
            self.assertEqual([p.slug for p in result.projects],
                             ["repo"])


if __name__ == "__main__":
    unittest.main()
