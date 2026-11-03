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


class TestWorkStaleness(unittest.TestCase):
    """Work staleness (stale-work-warnings plan): open
    plans/bundles/todos older than the threshold flag;
    the boundary is strict; terminal/archived/missing-date
    items never flag. TODAY is fixed so ages are exact."""

    TODAY = None  # set in setUp

    def setUp(self):
        from datetime import date
        self.today = date(2026, 10, 28)

    def todo(self, created, status):
        return stale_mod.todo_staleness(
            {"created": created, "status": status},
            threshold_days=3, today=self.today)

    def test_todo_boundary_is_strict(self):
        # exactly at the threshold: not yet stale
        self.assertEqual(self.todo("2026-10-25", "doing"),
                         {"age_days": 3, "stale": False})
        # one day past: stale
        self.assertEqual(self.todo("2026-10-24", "doing"),
                         {"age_days": 4, "stale": True})

    def test_todo_open_statuses_flag_done_never(self):
        for status in ("todo", "doing", "blocked"):
            self.assertTrue(
                self.todo("2026-10-01", status)["stale"],
                status)
        done = self.todo("2020-01-01", "done")
        self.assertGreater(done["age_days"], 2000)  # age served
        self.assertFalse(done["stale"])
        # an unrecognized status is not open work
        self.assertFalse(self.todo("2020-01-01", "weird")
                         ["stale"])

    def test_todo_missing_or_bad_date_never_flags(self):
        for created in (None, "", "not-a-date", "2026-13-40"):
            self.assertEqual(
                self.todo(created, "todo"),
                {"age_days": None, "stale": False}, created)

    def test_todo_default_today(self):
        # no explicit today: a years-old open todo flags
        # against the real clock at any run date
        out = stale_mod.todo_staleness(
            {"created": "2000-01-01", "status": "todo"},
            threshold_days=3)
        self.assertTrue(out["stale"])
        self.assertGreater(out["age_days"], 3)

    def plan(self, path, bucket, archived=False):
        return stale_mod.plan_staleness(
            {"path": path, "status_bucket": bucket,
             "archived": archived},
            threshold_days=3, today=self.today)

    def test_plan_age_from_filename_prefix(self):
        self.assertEqual(
            self.plan("2026-10-20-some-work.md", "todo"),
            {"age_days": 8, "stale": True})
        # a bundle's plan.md takes its parent dir's date
        self.assertEqual(
            self.plan("2026-10-20-bundle/plan.md", "doing"),
            {"age_days": 8, "stale": True})
        # boundary: exactly 3 days old does not flag
        self.assertFalse(
            self.plan("2026-10-25-x.md", "doing")["stale"])

    def test_plan_terminal_and_archived_never_flag(self):
        self.assertFalse(
            self.plan("2020-01-01-x.md", "done")["stale"])
        self.assertFalse(
            self.plan("2020-01-01-x.md", "doing",
                      archived=True)["stale"])
        # archived summaries live under finished/; the
        # prefix still parses (age served, flag off)
        out = self.plan("finished/2020-01-01-x.md", "done",
                        archived=True)
        self.assertIsNotNone(out["age_days"])
        self.assertFalse(out["stale"])

    def test_plan_missing_date_never_flags(self):
        self.assertEqual(self.plan("notes.md", "todo"),
                         {"age_days": None, "stale": False})
        self.assertEqual(
            self.plan("2026-13-40-x.md", "todo"),
            {"age_days": None, "stale": False})

    def bundle(self, **kw):
        base = {"id": "2026-10-20-work", "archived": False,
                "plan": None, "todos": []}
        base.update(kw)
        return stale_mod.bundle_staleness(
            base, threshold_days=3, today=self.today)

    def test_bundle_all_done_terminal_plan_never_flags(self):
        out = self.bundle(
            plan={"status_bucket": "done", "archived": False},
            todos=[{"status": "done"}, {"status": "done"}])
        self.assertEqual(out, {"age_days": 8,
                               "stale": False})

    def test_bundle_open_todo_flags_despite_terminal_plan(
            self):
        out = self.bundle(
            plan={"status_bucket": "done", "archived": False},
            todos=[{"status": "done"}, {"status": "doing"}])
        self.assertTrue(out["stale"])

    def test_bundle_open_plan_flags_with_all_todos_done(
            self):
        out = self.bundle(
            plan={"status_bucket": "doing",
                  "archived": False},
            todos=[{"status": "done"}])
        self.assertTrue(out["stale"])

    def test_bundle_planless_openness_rides_todos(self):
        self.assertTrue(self.bundle(
            todos=[{"status": "blocked"}])["stale"])
        self.assertFalse(self.bundle(
            todos=[{"status": "done"}])["stale"])
        # no plan, no todos: nothing open, nothing flags
        self.assertFalse(self.bundle()["stale"])

    def test_bundle_archived_and_undated_never_flag(self):
        self.assertFalse(self.bundle(
            archived=True,
            todos=[{"status": "todo"}])["stale"])
        out = stale_mod.bundle_staleness(
            {"id": "undated", "archived": False, "plan": None,
             "todos": [{"status": "todo"}]},
            threshold_days=3, today=self.today)
        self.assertEqual(out, {"age_days": None,
                               "stale": False})

    def test_threshold_is_the_callers(self):
        todo = {"created": "2026-10-20", "status": "todo"}
        self.assertTrue(stale_mod.todo_staleness(
            todo, threshold_days=3, today=self.today)
            ["stale"])
        self.assertFalse(stale_mod.todo_staleness(
            todo, threshold_days=30, today=self.today)
            ["stale"])


if __name__ == "__main__":
    unittest.main()
