"""Project fingerprint tests (cache-refresh plan Step
1): the fingerprint is a pure function of the corpus's
stat shape — stable for an untouched tree, moved by an
added file, a touched (mtime-bumped) file, or a manifest
edit — and a project with no .plans/ fingerprints
without raising.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lib import fingerprint as fp_mod  # noqa: E402


def bump_mtime(path: Path) -> None:
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns,
                       st.st_mtime_ns + 1_000_000))


class FingerprintCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        (self.root / ".plans" / "2026-11-05-work" / "todos") \
            .mkdir(parents=True)
        (self.root / "workbench.yaml").write_text(
            "name: Fixture\nplans: .plans\n",
            encoding="utf-8")
        self.todo = (self.root / ".plans" / "2026-11-05-work"
                     / "todos" / "t-1-step.md")
        self.todo.write_text("---\nstatus: todo\n---\n",
                             encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_stable_for_untouched_tree(self):
        first = fp_mod.project_fingerprint(self.root)
        self.assertEqual(len(first), 64)
        self.assertEqual(
            first, fp_mod.project_fingerprint(self.root))

    def test_added_file_moves_it(self):
        before = fp_mod.project_fingerprint(self.root)
        (self.root / ".plans" / "2026-11-05-work"
         / "plan.md").write_text("# plan\n",
                                 encoding="utf-8")
        self.assertNotEqual(
            before, fp_mod.project_fingerprint(self.root))

    def test_touched_file_moves_it(self):
        before = fp_mod.project_fingerprint(self.root)
        bump_mtime(self.todo)  # stat shape only: same bytes
        self.assertNotEqual(
            before, fp_mod.project_fingerprint(self.root))

    def test_manifest_edit_moves_it(self):
        before = fp_mod.project_fingerprint(self.root)
        manifest = self.root / "workbench.yaml"
        manifest.write_text("name: Renamed\nplans: .plans\n",
                            encoding="utf-8")
        bump_mtime(manifest)
        self.assertNotEqual(
            before, fp_mod.project_fingerprint(self.root))

    def test_missing_plans_dir_does_not_raise(self):
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        (bare / "workbench.yaml").write_text(
            "name: Bare\n", encoding="utf-8")
        fp = fp_mod.project_fingerprint(bare)
        self.assertEqual(len(fp), 64)

    def test_empty_root_does_not_raise(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        self.assertEqual(
            len(fp_mod.project_fingerprint(empty)), 64)


if __name__ == "__main__":
    unittest.main()
