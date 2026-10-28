"""lib/repo_state: the repo registry (reconcile, update
validation) and the change history (change-only appends,
heartbeat, streaks, legacy import).

Fixtures are plain dicts and temp files — the module is
pure state handling, no git needed. The legacy-shaped
fixtures mirror the sibling viewer's state files; one test
round-trips copies of its real state when present.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import repo_state

ROOT = Path(__file__).resolve().parent.parent

T0 = "2026-10-28T12:00:00+00:00"
T1 = "2026-10-28T12:15:00+00:00"


def discovered(repo_id, root):
    return {"id": repo_id, "name": repo_id, "root": str(root),
            "is_worktree": False, "parent_id": None}


def summary(repo_id="alpha", **over):
    s = {"id": repo_id, "error": None,
         "head_full": "a" * 40, "head": "a" * 40,
         "head_subject": "a commit", "branch": "main",
         "ahead": 0, "publication": "tracking",
         "dirty_counts": {"staged": 0, "unstaged": 0,
                          "untracked": 0},
         "exposure": {"level": "backed_up", "commits": 0,
                      "files": 0}}
    s.update(over)
    return s


def at(minutes):
    base = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=minutes)


class RegistryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "registry.json"
        self.root_a = self.tmp / "alpha"
        self.root_a.mkdir()

    def test_load_missing_is_empty(self):
        self.assertEqual(repo_state.load_registry(self.path),
                         {"repos": {}})

    def test_save_load_round_trip(self):
        data = {"repos": {"alpha": {"display_name": "Alpha"}}}
        repo_state.save_registry(self.path, data)
        self.assertEqual(repo_state.load_registry(self.path),
                         data)

    def test_reconcile_adds_new_as_untracked(self):
        data, changed = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        self.assertTrue(changed)
        entry = data["repos"]["alpha"]
        self.assertEqual(entry["expected"], "untracked")
        self.assertEqual(entry["display_name"], "alpha")
        self.assertEqual(entry["root"], str(self.root_a))
        self.assertEqual(entry["first_seen"], T0)
        self.assertEqual(entry["last_seen"], T0)
        self.assertFalse(entry["pinned"])

    def test_reconcile_adds_nested_id_display_name(self):
        data, _ = repo_state.reconcile(
            {"repos": {}},
            [discovered("group/beta", self.root_a)],
            healthy_scan=True, now=T0)
        self.assertEqual(
            data["repos"]["group/beta"]["display_name"], "beta")

    def test_reconcile_refreshes_seen_entry(self):
        data, _ = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        data, changed = repo_state.reconcile(
            data, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T1)
        self.assertTrue(changed)
        entry = data["repos"]["alpha"]
        self.assertEqual(entry["first_seen"], T0)
        self.assertEqual(entry["last_seen"], T1)

    def _seed_two(self):
        """alpha discovered, ghost undiscovered with a dead
        root, present undiscovered with a live root."""
        data, _ = repo_state.reconcile(
            {"repos": {}},
            [discovered("alpha", self.root_a),
             discovered("ghost", self.tmp / "ghost"),
             discovered("present", self.tmp / "present")],
            healthy_scan=True, now=T0)
        (self.tmp / "present").mkdir()
        return data

    def test_reconcile_prunes_dead_root_on_healthy_scan(self):
        data = self._seed_two()
        data, changed = repo_state.reconcile(
            data, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T1)
        self.assertTrue(changed)
        self.assertNotIn("ghost", data["repos"])
        # Root exists but undiscovered: kept (surfaces missing).
        self.assertIn("present", data["repos"])
        self.assertIn("alpha", data["repos"])

    def test_reconcile_preserves_all_on_failed_scan(self):
        data = self._seed_two()
        data, _ = repo_state.reconcile(
            data, [], healthy_scan=False, now=T1)
        self.assertEqual(set(data["repos"]),
                         {"alpha", "ghost", "present"})

    def test_update_entry_applies_valid_patch(self):
        data, _ = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        entry, err = repo_state.update_entry(
            data, "alpha",
            {"expected": "published", "pinned": True,
             "notes": "watched"})
        self.assertIsNone(err)
        self.assertEqual(entry["expected"], "published")
        self.assertTrue(entry["pinned"])
        self.assertEqual(data["repos"]["alpha"]["notes"],
                         "watched")

    def test_update_entry_rejects_unknown_id(self):
        entry, err = repo_state.update_entry(
            {"repos": {}}, "nope", {"notes": "x"})
        self.assertIsNone(entry)
        self.assertIn("unknown", err)

    def test_update_entry_rejects_bad_key_and_writes_nothing(self):
        data, _ = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        entry, err = repo_state.update_entry(
            data, "alpha", {"notes": "changed", "bogus": 1})
        self.assertIsNone(entry)
        self.assertIn("unknown field", err)
        self.assertEqual(data["repos"]["alpha"]["notes"], "")

    def test_update_entry_rejects_reconcile_managed_key(self):
        data, _ = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        entry, err = repo_state.update_entry(
            data, "alpha", {"root": "/elsewhere"})
        self.assertIsNone(entry)
        self.assertIn("unknown field", err)

    def test_update_entry_rejects_bad_enum(self):
        data, _ = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        entry, err = repo_state.update_entry(
            data, "alpha", {"expected": "sometimes"})
        self.assertIsNone(entry)
        self.assertIn("expected must be one of", err)
        self.assertEqual(data["repos"]["alpha"]["expected"],
                         "untracked")

    def test_update_entry_rejects_bad_types(self):
        data, _ = repo_state.reconcile(
            {"repos": {}}, [discovered("alpha", self.root_a)],
            healthy_scan=True, now=T0)
        for patch in ({"pinned": "yes"}, {"notes": 3},
                      {"expected": True}):
            entry, err = repo_state.update_entry(
                data, "alpha", patch)
            self.assertIsNone(entry, patch)
            self.assertIn("bad type", err, patch)


class HistoryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "history.jsonl"

    def lines(self):
        if not self.path.is_file():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_first_record_appends(self):
        self.assertTrue(repo_state.record_history(
            self.path, summary(), now=at(0)))
        recs = self.lines()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["repo"], "alpha")
        self.assertEqual(recs[0]["head"], "a" * 40)
        self.assertEqual(recs[0]["dirty_total"], 0)
        self.assertEqual(recs[0]["exposure_level"], "backed_up")

    def test_unchanged_within_heartbeat_appends_nothing(self):
        repo_state.record_history(self.path, summary(), now=at(0))
        self.assertFalse(repo_state.record_history(
            self.path, summary(), now=at(30)))
        self.assertEqual(len(self.lines()), 1)

    def test_heartbeat_appends_after_an_hour(self):
        repo_state.record_history(self.path, summary(), now=at(0))
        self.assertTrue(repo_state.record_history(
            self.path, summary(), now=at(61)))
        self.assertEqual(len(self.lines()), 2)

    def test_headline_change_appends(self):
        repo_state.record_history(self.path, summary(), now=at(0))
        dirty = summary(dirty_counts={"staged": 1, "unstaged": 2,
                                      "untracked": 0},
                        exposure={"level": "uncommitted_work",
                                  "commits": 0, "files": 3})
        self.assertTrue(repo_state.record_history(
            self.path, dirty, now=at(5)))
        recs = self.lines()
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[1]["dirty_total"], 3)

    def test_error_or_idless_summary_records_nothing(self):
        self.assertFalse(repo_state.record_history(
            self.path, summary(error="git failed"), now=at(0)))
        self.assertFalse(repo_state.record_history(
            self.path, {"error": None}, now=at(0)))
        self.assertEqual(self.lines(), [])

    def _write_series(self, repo_id, rows):
        with open(self.path, "a", encoding="utf-8") as f:
            for ts, head, branch, dirty, ahead in rows:
                f.write(json.dumps({
                    "at": ts, "repo": repo_id, "head": head,
                    "head_subject": "s", "branch": branch,
                    "ahead": ahead, "publication": "tracking",
                    "dirty_total": dirty,
                    "exposure_level": "backed_up",
                    "exposed_commits": 0}) + "\n")

    def test_streaks_and_timeline(self):
        t = [at(m).isoformat() for m in (0, 10, 20, 30)]
        self._write_series("alpha", [
            (t[0], "h1", "main", 0, 0),
            (t[1], "h1", "main", 2, 1),
            (t[2], "h2", "main", 5, 0),
            (t[3], "h2", "main", 1, 3),
        ])
        out = repo_state.history_for(self.path, "alpha")
        self.assertEqual(len(out["records"]), 4)
        self.assertEqual(out["dirty_since"], t[1])
        self.assertEqual(out["ahead_since"], t[3])
        self.assertEqual(out["timeline"], [
            {"ts": t[0], "head": "h1", "branch": "main"},
            {"ts": t[2], "head": "h2", "branch": "main"},
        ])

    def test_streaks_end_when_latest_record_is_clean(self):
        t = [at(m).isoformat() for m in (0, 10)]
        self._write_series("alpha", [
            (t[0], "h1", "main", 4, 2),
            (t[1], "h1", "main", 0, 0),
        ])
        out = repo_state.history_for(self.path, "alpha")
        self.assertIsNone(out["dirty_since"])
        self.assertIsNone(out["ahead_since"])

    def test_history_for_unknown_repo_is_empty(self):
        out = repo_state.history_for(self.path, "nope")
        self.assertEqual(out["records"], [])
        self.assertEqual(out["timeline"], [])
        self.assertIsNone(out["dirty_since"])
        self.assertIsNone(out["ahead_since"])


def legacy_registry():
    return {"repos": {
        "alpha": {"display_name": "Alpha", "project": "p1",
                  "expected": "published", "pinned": True,
                  "ignored": False, "notes": "n",
                  "root": "/srv/alpha",
                  "first_seen": T0, "last_seen": T1},
        "beta": {"display_name": "beta", "project": "",
                  "expected": "bogus", "pinned": False,
                  "ignored": True, "notes": "",
                  "root": "/srv/beta",
                  "first_seen": T0, "last_seen": T1},
    }}


def legacy_line(**over):
    rec = {"at": T0, "repo": "alpha", "head": "h1",
           "head_subject": "s", "branch": "main", "ahead": 0,
           "publication": "tracking", "dirty_total": 0,
           "exposed_commits": 0}
    rec.update(over)
    return rec


class ImportCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write_json(self, name, obj):
        path = self.tmp / name
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj))
        return path

    def write_jsonl(self, name, rows):
        path = self.tmp / name
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        return path

    def test_import_registry_maps_fields(self):
        source = self.write_json("legacy.json", legacy_registry())
        data = repo_state.import_registry(source)
        alpha = data["repos"]["alpha"]
        self.assertEqual(alpha["display_name"], "Alpha")
        self.assertEqual(alpha["expected"], "published")
        self.assertTrue(alpha["pinned"])
        self.assertEqual(alpha["root"], "/srv/alpha")
        # A value outside the enum falls back to untracked.
        self.assertEqual(data["repos"]["beta"]["expected"],
                         "untracked")
        self.assertTrue(data["repos"]["beta"]["ignored"])

    def test_import_registry_missing_source_is_empty(self):
        self.assertEqual(
            repo_state.import_registry(self.tmp / "absent.json"),
            {"repos": {}})

    def test_import_history_maps_and_derives_level(self):
        source = self.write_jsonl("legacy.jsonl", [
            legacy_line(),
            legacy_line(at=T1, dirty_total=2),
            legacy_line(at="2026-10-28T13:00:00+00:00",
                        publication="local_only",
                        exposed_commits=42),
            legacy_line(at="2026-10-28T14:00:00+00:00",
                        ahead=3, exposed_commits=3),
        ])
        dest = self.tmp / "history.jsonl"
        count = repo_state.import_history(source, dest)
        self.assertEqual(count, 4)
        with open(dest, encoding="utf-8") as f:
            recs = [json.loads(l) for l in f if l.strip()]
        self.assertEqual([r["exposure_level"] for r in recs],
                         ["backed_up", "uncommitted_work",
                          "local_only", "unbacked_commits"])
        self.assertEqual(recs[2]["exposed_commits"], 42)

    def test_import_history_skips_records_already_present(self):
        source = self.write_jsonl(
            "legacy.jsonl", [legacy_line(), legacy_line(at=T1)])
        dest = self.tmp / "history.jsonl"
        self.assertEqual(
            repo_state.import_history(source, dest), 2)
        self.assertEqual(
            repo_state.import_history(source, dest), 0)


class RealStateImportCase(unittest.TestCase):
    """Round-trip against copies of the legacy viewer's real
    state files, when they exist next to this repo."""

    SIBLING = ROOT.parent / "git-repo-viewer-server" / "state"

    def setUp(self):
        reg = self.SIBLING / "registry.json"
        hist = self.SIBLING / "history.jsonl"
        if not (reg.is_file() and hist.is_file()):
            self.skipTest("legacy state files not present")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.reg = self.tmp / "registry.json"
        self.hist = self.tmp / "history.jsonl"
        shutil.copy(reg, self.reg)
        shutil.copy(hist, self.hist)

    def test_real_registry_covers_the_same_ids(self):
        with open(self.reg, encoding="utf-8") as f:
            source_ids = set(json.load(f)["repos"])
        data = repo_state.import_registry(self.reg)
        self.assertEqual(set(data["repos"]), source_ids)
        for entry in data["repos"].values():
            self.assertIn(entry["expected"],
                          repo_state.EXPECTED_VALUES)
            self.assertEqual(set(entry),
                             set(repo_state.ENTRY_FIELDS))

    def test_real_history_imports_and_dedupes(self):
        dest = self.tmp / "ours.jsonl"
        count = repo_state.import_history(self.hist, dest)
        self.assertGreater(count, 0)
        self.assertEqual(
            repo_state.import_history(self.hist, dest), 0)
        out = repo_state.history_for(
            dest, next(iter(repo_state._read_records(dest)))["repo"])
        self.assertTrue(out["records"])


if __name__ == "__main__":
    unittest.main()
