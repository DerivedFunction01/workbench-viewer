"""Repo-home spec §5.3/§5.4: the cleanup lifecycle.

Time is controlled by backdating stored timestamps (fixture
manipulation of the test's own DB file) and passing an
explicit `now` to cleanup(). Proves each TTL rule, the
never-purge-sent safety rule, orphan archiving (and its
empty-sweep guard), the per-project cap archiving oldest
done first, idempotence, and the manual purge controls.
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import messages as msg

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.isoformat()


class CleanupCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-clean-"))
        self.db = self.tmp / "messages.db"

    def make(self, **kw):
        kw.setdefault("author", "owner")
        kw.setdefault("body", "x")
        return msg.create_message(self.db, **kw)

    def backdate(self, mid, **fields):
        conn = sqlite3.connect(str(self.db))
        try:
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE messages SET {sets} WHERE id = ?",
                (*fields.values(), mid))
            conn.commit()
        finally:
            conn.close()

    def run_cleanup(self, **kw):
        kw.setdefault("now", NOW)
        return msg.cleanup(self.db, **kw)


class TestTtls(CleanupCase):
    def test_draft_ttl_purges_only_old_drafts(self):
        old = self.make(project_slug="a")
        self.backdate(old["id"], updated_at=iso(
            NOW - timedelta(days=8)))
        fresh = self.make(project_slug="a")
        self.backdate(fresh["id"], updated_at=iso(
            NOW - timedelta(days=6)))
        counts = self.run_cleanup(known_slugs=["a"])
        self.assertEqual(counts["drafts_purged"], 1)
        with self.assertRaises(msg.MessageError):
            msg.get_message(self.db, old["id"])
        self.assertEqual(
            msg.get_message(self.db, fresh["id"])["state"],
            "draft")
        # Purged rows leave their events behind.
        self.assertTrue(msg.events_for(self.db, old["id"]))

    def test_done_archives_then_purges_on_schedule(self):
        m = self.make(project_slug="a", send=True)
        msg.fetch_unacked(self.db, "a")
        msg.mark_done(self.db, m["id"])
        self.backdate(m["id"], done_at=iso(
            NOW - timedelta(days=31)))
        counts = self.run_cleanup(known_slugs=["a"])
        self.assertEqual(counts["done_archived"], 1)
        got = msg.get_message(self.db, m["id"])
        self.assertEqual(got["state"], "archived")
        # Freshly archived rows are NOT purged in the same
        # pass (archived_at is now), even past the TTL math.
        self.assertEqual(counts["archived_purged"], 0)
        self.backdate(m["id"], archived_at=iso(
            NOW - timedelta(days=91)))
        counts = self.run_cleanup(known_slugs=["a"])
        self.assertEqual(counts["archived_purged"], 1)
        with self.assertRaises(msg.MessageError):
            msg.get_message(self.db, m["id"])

    def test_sent_unacked_is_never_purged(self):
        m = self.make(project_slug="a", send=True)
        ancient = iso(NOW - timedelta(days=365))
        self.backdate(m["id"], sent_at=ancient,
                      updated_at=ancient)
        counts = self.run_cleanup(known_slugs=["a"])
        self.assertEqual(sum(counts.values()), 0)
        self.assertEqual(
            msg.get_message(self.db, m["id"])["state"], "sent")
        # ...but it does badge as awaiting pickup (§5.3).
        rows = msg.list_messages(self.db, badge_days=14,
                                 now=NOW)
        self.assertTrue(rows[0]["awaiting_pickup"])

    def test_idempotent(self):
        m = self.make(project_slug="a")
        self.backdate(m["id"], updated_at=iso(
            NOW - timedelta(days=30)))
        first = self.run_cleanup(known_slugs=["a"])
        stats = msg.store_stats(self.db)
        self.assertEqual(stats["last_cleanup_at"],
                         NOW.isoformat())
        self.assertEqual(stats["last_cleanup_counts"], first)
        second = self.run_cleanup(known_slugs=["a"])
        self.assertEqual(first["drafts_purged"], 1)
        self.assertEqual(sum(second.values()), 0)


class TestOrphansAndCap(CleanupCase):
    def test_orphan_project_archived(self):
        gone = self.make(project_slug="ghost", send=True)
        kept = self.make(project_slug="a", send=True)
        counts = self.run_cleanup(known_slugs=["a"])
        self.assertEqual(counts["orphans_archived"], 1)
        self.assertEqual(
            msg.get_message(self.db, gone["id"])["state"],
            "archived")
        self.assertEqual(
            msg.get_message(self.db, kept["id"])["state"],
            "sent")

    def test_orphan_rule_skipped_without_known_slugs(self):
        m = self.make(project_slug="ghost", send=True)
        for known in (None, []):
            counts = self.run_cleanup(known_slugs=known)
            self.assertEqual(counts["orphans_archived"], 0)
        self.assertEqual(
            msg.get_message(self.db, m["id"])["state"], "sent")

    def test_cap_archives_oldest_done_first(self):
        policy = {**msg.DEFAULT_POLICY, "per_project_cap": 2}
        ids = []
        for i in range(3):
            m = self.make(project_slug="a", send=True)
            msg.fetch_unacked(self.db, "a")
            msg.mark_done(self.db, m["id"])
            self.backdate(m["id"], done_at=iso(
                NOW - timedelta(days=10 - i)))
            ids.append(m["id"])
        live = self.make(project_slug="a", send=True)
        counts = msg.cleanup(self.db, known_slugs=["a"],
                             policy=policy, now=NOW)
        self.assertEqual(counts["cap_archived"], 2)
        states = {i: msg.get_message(self.db, i)["state"]
                  for i in ids}
        # 4 non-archived roots, cap 2 -> excess 2: the two
        # OLDEST done roots archive; the newest done stays.
        self.assertEqual(states[ids[0]], "archived")
        self.assertEqual(states[ids[1]], "archived")
        self.assertEqual(states[ids[2]], "done")
        # Sent roots are never cap-archived.
        self.assertEqual(
            msg.get_message(self.db, live["id"])["state"],
            "sent")


class TestManualPurges(CleanupCase):
    def test_purge_controls(self):
        d = self.make(project_slug="a")
        m = self.make(project_slug="a", send=True)
        msg.fetch_unacked(self.db, "a")
        msg.mark_done(self.db, m["id"])
        msg.archive_message(self.db, m["id"])
        self.assertEqual(msg.purge_drafts(self.db), 1)
        self.assertEqual(msg.purge_archived(self.db), 1)
        self.assertEqual(
            sum(msg.counts_by_state(self.db).values()), 0)


if __name__ == "__main__":
    unittest.main()
