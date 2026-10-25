"""Validator registry: planted violations each produce a
named finding (subplan 09 Step 7 verify, landed with the
Step 2 core since the registry lives in lib/)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lib import registry as reg
from lib import validators as val


class TestValidators(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "workbench" / "registry.db"
        self.layout = (self.root / "workbench" / "entries",
                       self.root / "workbench" / "archive")
        reg.init_registry(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self):
        return val.validate_project(self.db, self.layout)

    def names(self):
        return {f["validator"] for f in self.findings()}

    def test_clean_project_has_no_findings(self):
        reg.add_entry(self.db, self.layout, "tidy")
        reg.verify_entry(self.db, "tidy")
        self.assertEqual(self.findings(), [])

    def test_broken_supersedes_link(self):
        reg.add_entry(self.db, self.layout, "a")
        conn = sqlite3.connect(str(self.db))
        conn.execute("UPDATE entries SET superseded_by = "
                     "'ghost' WHERE id = 'a'")
        conn.commit()
        conn.close()
        self.assertIn("supersedes-resolve", self.names())

    def test_drifted_entry_file(self):
        e = reg.add_entry(self.db, self.layout, "a")
        main = Path(e["entry_dir"]) / "mock.html"
        main.write_text("<html>tampered</html>\n")
        self.assertIn("fingerprint-match", self.names())

    def test_folder_without_row(self):
        (self.layout[0] / "orphan").mkdir(parents=True)
        self.assertIn("entry-dirs-have-rows", self.names())

    def test_archived_flag_folder_mismatch(self):
        e = reg.add_entry(self.db, self.layout, "a")
        reg.archive_entry(self.db, self.layout, "a")
        # move the folder back by hand: flag says archived,
        # folder says active -> named finding with the repair
        import shutil
        shutil.move(e["entry_dir"].replace(
            str(self.layout[1]), str(self.layout[0]))
            if False else str(Path(
                reg.get_entry(self.db, "a")["entry_dir"])),
            str(self.layout[0] / "a"))
        self.assertIn("archived-folder-agreement", self.names())

    def test_registry_shape(self):
        names = [n for n, _ in val.ALL_VALIDATORS]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("uniformity", names)


if __name__ == "__main__":
    unittest.main()
