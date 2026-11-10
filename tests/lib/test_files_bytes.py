"""Raw byte-route read tests (byte-route plan, Step 1):
entry_bytes serves an entry file's bytes verbatim with a
guessed content type — the read behind GET /raw/... The
guards are the entry reads' guards: containment, secret
refusal before existence, and the payload bound."""

import tempfile
import unittest
from pathlib import Path

from lib import files as files_mod


def make_entry(root: Path, files: dict):
    entry_dir = root / "entry"
    entry_dir.mkdir(parents=True)
    for name, content in files.items():
        target = entry_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return {"source_kind": "entry-dir",
            "entry_dir": str(entry_dir),
            "main_file": "index.html"}


class EntryBytes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_round_trip_byte_identical(self):
        page = "<html><script>1</script><p>study</p></html>\n"
        entry = make_entry(self.root, {"index.html": page})
        raw, content_type = files_mod.entry_bytes(
            entry, "index.html")
        self.assertEqual(raw, page.encode("utf-8"))
        self.assertEqual(content_type, "text/html")

    def test_binary_asset_serves_with_its_type(self):
        blob = b"\x89PNG\r\n\x1a\n\x00\x01"
        entry = make_entry(self.root,
                           {"index.html": "x", "img.png": blob})
        raw, content_type = files_mod.entry_bytes(
            entry, "img.png")
        self.assertEqual(raw, blob)
        self.assertEqual(content_type, "image/png")

    def test_css_type(self):
        entry = make_entry(self.root,
                           {"index.html": "x",
                            "style.css": "body{}"})
        _raw, content_type = files_mod.entry_bytes(
            entry, "style.css")
        self.assertEqual(content_type, "text/css")

    def test_unknown_extension_falls_back(self):
        entry = make_entry(self.root,
                           {"index.html": "x",
                            "data.weirdext": "zz"})
        _raw, content_type = files_mod.entry_bytes(
            entry, "data.weirdext")
        self.assertEqual(content_type,
                         "application/octet-stream")

    def test_over_peek_cap_file_serves_whole(self):
        big = "<p>line</p>\n" * 5000  # ~60 KB, 5000 lines
        entry = make_entry(self.root, {"index.html": big})
        raw, _ct = files_mod.entry_bytes(entry, "index.html")
        self.assertEqual(raw.decode("utf-8"), big)

    def test_secret_shaped_path_refused_403(self):
        entry = make_entry(self.root,
                           {"index.html": "x",
                            "api.key": "not-a-real-secret"})
        with self.assertRaises(files_mod.FileError_) as ctx:
            files_mod.entry_bytes(entry, "api.key")
        self.assertEqual(ctx.exception.status, 403)

    def test_escape_refused(self):
        entry = make_entry(self.root, {"index.html": "x"})
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        with self.assertRaises(files_mod.FileError_) as ctx:
            files_mod.entry_bytes(entry, "../outside.txt")
        self.assertEqual(ctx.exception.status, 400)

    def test_absolute_path_refused(self):
        entry = make_entry(self.root, {"index.html": "x"})
        with self.assertRaises(files_mod.FileError_) as ctx:
            files_mod.entry_bytes(entry, "/etc/hostname")
        self.assertEqual(ctx.exception.status, 400)

    def test_missing_file_404(self):
        entry = make_entry(self.root, {"index.html": "x"})
        with self.assertRaises(files_mod.FileError_) as ctx:
            files_mod.entry_bytes(entry, "nope.html")
        self.assertEqual(ctx.exception.status, 404)

    def test_payload_bound_413(self):
        entry = make_entry(self.root, {"index.html": "x"})
        big = self.root / "entry" / "big.bin"
        big.write_bytes(b"\x00" * (files_mod.RAW_MAX_BYTES + 1))
        with self.assertRaises(files_mod.FileError_) as ctx:
            files_mod.entry_bytes(entry, "big.bin")
        self.assertEqual(ctx.exception.status, 413)


if __name__ == "__main__":
    unittest.main()
