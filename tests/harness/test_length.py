"""Tests for tools/length.py — the 800-line cap scanner.

The scanner module lives outside the lib/ tree (it is a gate
tool), so it is loaded by path. Fixtures are plain temp trees;
find_over_cap takes an explicit path list, so no git repo is
needed to exercise the counting and cap logic.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "length_scan", ROOT / "tools" / "length.py")
length = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(length)


def write(root: Path, rel: str, lines: int, trailing_newline: bool = True):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(f"line {i}" for i in range(lines))
    if trailing_newline and lines:
        text += "\n"
    path.write_text(text, encoding="utf-8")


class CapLogicTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_at_cap_is_clean_over_cap_is_flagged(self):
        write(self.root, "at.py", length.MAX_LINES)
        write(self.root, "over.py", length.MAX_LINES + 1)
        findings = length.find_over_cap(self.root, ["at.py", "over.py"])
        self.assertEqual(findings, [("over.py", length.MAX_LINES + 1)])

    def test_no_trailing_newline_counts_the_last_line(self):
        write(self.root, "nonl.ts", length.MAX_LINES + 1,
              trailing_newline=False)
        findings = length.find_over_cap(self.root, ["nonl.ts"])
        self.assertEqual(findings, [("nonl.ts", length.MAX_LINES + 1)])

    def test_unreadable_and_missing_files_are_skipped(self):
        findings = length.find_over_cap(self.root, ["missing.py"])
        self.assertEqual(findings, [])


class ScopeTests(unittest.TestCase):
    def test_extensions_in_scope(self):
        for rel in ("a.py", "b.ts", "c.tsx", "d.js", "e.mjs"):
            self.assertTrue(length.is_in_scope(rel), rel)

    def test_non_source_extensions_out_of_scope(self):
        for rel in ("a.css", "b.md", "c.json", "d.html"):
            self.assertFalse(length.is_in_scope(rel), rel)

    def test_vendored_and_generated_trees_excluded(self):
        self.assertFalse(length.is_in_scope("viewer/vendor/space-sdk/x.ts"))
        self.assertFalse(
            length.is_in_scope("viewer/server/.generated/actions.ts"))

    def test_dependency_and_build_segments_excluded(self):
        self.assertFalse(length.is_in_scope("viewer/node_modules/pkg/i.ts"))
        self.assertFalse(length.is_in_scope("viewer/client/dist/main.js"))
        self.assertFalse(length.is_in_scope("viewer/.bun-cache/pkg/i.mjs"))


if __name__ == "__main__":
    unittest.main()
