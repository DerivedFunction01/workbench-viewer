"""Regression tests for ops/bootstrap-staging.sh (SPEC section 2.1).

The staging project is a separate swept project with its own git
repo; this repo carries only its seed files under
templates/staging/. The bootstrap script materializes the seed as
a sibling project when it does not exist, and must never touch an
existing project or an unrelated directory.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "ops" / "bootstrap-staging.sh"
SEED_DIR = REPO_ROOT / "templates" / "staging"
SEED_FILES = ("workbench.yaml", "README.md", "GRADUATIONS.md",
              ".gitignore")


def _run_script(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(target)],
        capture_output=True, text=True, timeout=120)


def _git(target: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        capture_output=True, text=True, timeout=60).stdout


class TestBootstrapStaging(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-bootstrap-"))
        self.target = self.tmp / "staging"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_project_with_own_repo_and_registry(self):
        result = _run_script(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in SEED_FILES:
            copied = self.target / name
            self.assertTrue(copied.is_file(), name)
            self.assertEqual(copied.read_bytes(),
                             (SEED_DIR / name).read_bytes(), name)
        self.assertTrue((self.target / ".git").is_dir())
        self.assertEqual(len(_git(self.target, "log", "--oneline")
                             .strip().splitlines()), 1)
        self.assertEqual(_git(self.target, "status", "--porcelain"),
                         "")
        self.assertTrue(
            (self.target / "workbench" / "registry.db").is_file())

    def test_second_run_is_a_noop(self):
        self.assertEqual(_run_script(self.target).returncode, 0)
        readme = self.target / "README.md"
        readme.write_text(readme.read_text() + "\nlocal marker\n")
        result = _run_script(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("local marker", readme.read_text())
        self.assertEqual(len(_git(self.target, "log", "--oneline")
                             .strip().splitlines()), 1)

    def test_refuses_an_existing_non_staging_directory(self):
        self.target.mkdir(parents=True)
        stray = self.target / "stray.txt"
        stray.write_text("not a staging project\n")
        result = _run_script(self.target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(stray.read_text(), "not a staging project\n")
        self.assertFalse((self.target / ".git").exists())
        self.assertFalse((self.target / "workbench.yaml").exists())


if __name__ == "__main__":
    unittest.main()
