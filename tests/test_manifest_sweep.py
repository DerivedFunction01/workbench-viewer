"""Step 2 gate tests: manifest parsing (restricted YAML
subset) + the discovery sweep mechanics."""

import tempfile
import unittest
from pathlib import Path

from lib.manifest import ManifestError, load_manifest
from lib.sweep import sweep


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
            self.assertTrue(sections["registry_declared"])


if __name__ == "__main__":
    unittest.main()
