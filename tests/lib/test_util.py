"""The lib write seam (util.write_text): atomic staging.

The seam once opened its target directly — truncate,
then write — so a write denied inside one of this
environment's EPERM windows left the target at 0 bytes
(a programme todo was lost that way, 2026-11-13). These
tests pin the staged form: content lands whole, a
failed stage leaves the target untouched, and the
target's mode survives the rename."""

import tempfile
import unittest
from pathlib import Path

from lib import util


class TestWriteText(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_and_overwrite(self):
        target = self.dir / "note.md"
        util.write_text(target, "first\n")
        self.assertEqual(target.read_text(), "first\n")
        util.write_text(target, "second\n")
        self.assertEqual(target.read_text(), "second\n")
        # no staging litter remains
        self.assertEqual(
            [p.name for p in self.dir.iterdir()],
            ["note.md"])

    def test_failed_stage_leaves_target_untouched(self):
        target = self.dir / "note.md"
        target.write_text("original\n")
        # Occupy the staging path with a directory: the
        # staged open fails before any byte can land.
        (self.dir / "note.md.tmp").mkdir()
        with self.assertRaises(OSError):
            util.write_text(target, "replacement\n")
        self.assertEqual(target.read_text(), "original\n")

    def test_existing_mode_is_preserved(self):
        target = self.dir / "note.md"
        target.write_text("original\n")
        target.chmod(0o640)
        util.write_text(target, "replacement\n")
        self.assertEqual(target.stat().st_mode & 0o777,
                         0o640)
        self.assertEqual(target.read_text(),
                         "replacement\n")


if __name__ == "__main__":
    unittest.main()
