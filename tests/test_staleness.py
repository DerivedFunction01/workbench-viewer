"""Step 2/8-of-subplan-09 gate tests: derived staleness is
computable, explainable per entry, and provably non-mutating
against ruled columns."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import export as export_mod
from lib import registry as reg
from lib import staleness as stale_mod

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def age(db, entry_id, *, created_days, verified_days=None):
    created = (NOW - timedelta(days=created_days)).isoformat()
    verified = None
    if verified_days is not None:
        verified = (NOW - timedelta(days=verified_days)).isoformat()
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE entries SET created_at = ?,"
        " status_changed_at = ?, last_verified_at = ?"
        " WHERE id = ?",
        (created, created, verified, entry_id))
    conn.commit()
    conn.close()


class TestStaleness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "workbench" / "registry.db"
        self.layout = (self.root / "workbench" / "entries",
                        self.root / "workbench" / "archive")
        reg.init_registry(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def derived(self, entry_id):
        entry = reg.get_entry(self.db, entry_id)
        return stale_mod.entry_staleness(entry, now=NOW)

    def test_unexplored_41_days_never_verified(self):
        # the subplan's example: "unexplored, 41 days old,
        # never verified"
        reg.add_entry(self.db, self.layout, "old-exp")
        age(self.db, "old-exp", created_days=41)
        d = self.derived("old-exp")
        self.assertTrue(d["stale"])
        self.assertTrue(d["never_verified"])
        self.assertEqual(d["age_days"], 41.0)
        self.assertTrue(any("never verified" in r
                            for r in d["reasons"]))

    def test_fresh_unexplored_not_stale(self):
        reg.add_entry(self.db, self.layout, "fresh")
        age(self.db, "fresh", created_days=3)
        self.assertFalse(self.derived("fresh")["stale"])

    def test_canonical_threshold_is_90(self):
        reg.add_entry(self.db, self.layout, "canon")
        reg.set_status(self.db, "canon", "canonical",
                       ruling="ruled")
        age(self.db, "canon", created_days=100,
            verified_days=100)
        d = self.derived("canon")
        self.assertTrue(d["stale"])
        self.assertTrue(any("verification due" in r
                            for r in d["reasons"]))
        age(self.db, "canon", created_days=100,
            verified_days=10)
        self.assertFalse(self.derived("canon")["stale"])

    def test_implemented_and_abandoned_never_flag(self):
        reg.add_entry(self.db, self.layout, "done")
        reg.set_status(self.db, "done", "canonical",
                       ruling="r")
        reg.set_status(self.db, "done", "implemented",
                       ruling="shipped")
        reg.add_entry(self.db, self.layout, "dead")
        reg.set_status(self.db, "dead", "abandoned",
                       ruling="dead")
        for eid in ("done", "dead"):
            age(self.db, eid, created_days=400)
            self.assertFalse(self.derived(eid)["stale"],
                             f"{eid} must never stale-flag")

    def test_drift_is_a_reason(self):
        e = reg.add_entry(self.db, self.layout, "drifty")
        main = Path(e["entry_dir"]) / "mock.html"
        main.write_text("<html>edited under the metadata"
                        "</html>\n")
        d = self.derived("drifty")
        self.assertTrue(d["drift"])
        self.assertTrue(d["stale"])

    def test_report_is_non_mutating_for_ruled_columns(self):
        reg.add_entry(self.db, self.layout, "x")
        reg.add_todo(self.db, "t", "T")
        before = export_mod.build_export(self.db, now=NOW)
        entries = reg.list_entries(self.db, archived=False)
        latest = {e["id"]: reg.latest_review(self.db, e["id"])
                  for e in entries}
        stale_mod.project_report(entries, latest, now=NOW)
        reg.record_stale_check(self.db, "test run")
        after = export_mod.build_export(self.db, now=NOW)
        # ruled entry data byte-identical; only history grew
        ruled_before = export_mod.ruled_sections(before)
        ruled_after = export_mod.ruled_sections(after)
        self.assertEqual(ruled_before["entries"],
                         ruled_after["entries"])
        self.assertEqual(ruled_before["todos"],
                         ruled_after["todos"])
        self.assertEqual(
            len(ruled_after["history"]),
            len(ruled_before["history"]) + 1)
        self.assertEqual(ruled_after["history"][-1]["verb"],
                         "stale-check")


if __name__ == "__main__":
    unittest.main()
