"""Entry preview read tests (home-hygiene plan, Step 4):
the rendered-preview read of an entry's own file serves
the file WHOLE — the peek caps guard the source surface,
not a rendered study. Guards still apply (secret-shaped
paths withheld, binary refusal, payload bound)."""

import tempfile
import unittest
from pathlib import Path

from lib import files as files_mod


def make_entry(root: Path, files: dict):
    entry_dir = root / "entry"
    entry_dir.mkdir(parents=True)
    for name, content in files.items():
        (entry_dir / name).write_text(content, encoding="utf-8")
    return {"source_kind": "entry-dir",
            "entry_dir": str(entry_dir),
            "main_file": "index.html"}


class EntryPreview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_over_peek_cap_file_serves_whole(self):
        # Over the byte cap AND over the line cap: the
        # peek truncates this file; the preview must not.
        big = ("<p>study line</p>\n" * 3000)  # ~54 KB, 3000 lines
        entry = make_entry(self.root, {"index.html": big})
        peek = files_mod.peek_file(entry, "index.html")
        self.assertTrue(peek["truncated"])
        preview = files_mod.entry_preview(entry, "index.html")
        self.assertEqual(preview["content"], big)
        self.assertFalse(preview["is_binary"])
        self.assertIsNone(preview["withheld"])
        self.assertNotIn("too_large", preview)

    def test_secret_shaped_file_is_withheld(self):
        entry = make_entry(self.root,
                           {"index.html": "x",
                            "api.key": "not-a-real-secret"})
        preview = files_mod.entry_preview(entry, "api.key")
        self.assertEqual(preview["withheld"], "secret")
        self.assertIsNone(preview["content"])

    def test_binary_file_is_refused(self):
        entry = make_entry(self.root, {"index.html": "x"})
        blob = self.root / "entry" / "blob.png"
        blob.write_bytes(b"\x89PNG\x00\x01")
        preview = files_mod.entry_preview(entry, "blob.png")
        self.assertTrue(preview["is_binary"])
        self.assertIsNone(preview["content"])

    def test_missing_file_raises_404(self):
        entry = make_entry(self.root, {"index.html": "x"})
        with self.assertRaises(files_mod.FileError_) as ctx:
            files_mod.entry_preview(entry, "nope.html")
        self.assertEqual(ctx.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
