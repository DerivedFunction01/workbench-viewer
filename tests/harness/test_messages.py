"""Repo-home spec §5: the viewer-tied message store.

Proves: the state machine is enforced on the one mutation
path; pickup (fetch) acknowledges atomically and records
the fetch; threading via parent_id; archiving a root
archives its thread; purge deletes the row but the audit
events remain; bad authors/anchors/states are refused.
Cleanup lifecycle lives in test_messages_cleanup.py.
"""

import tempfile
import unittest
from pathlib import Path

from lib import messages as msg


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-msg-"))
        self.db = self.tmp / "state" / "messages.db"

    def make(self, **kw):
        kw.setdefault("author", "owner")
        kw.setdefault("body", "hello")
        return msg.create_message(self.db, **kw)


class TestLifecycle(StoreCase):
    def test_draft_send_ack_done_archive(self):
        m = self.make(project_slug="alpha")
        self.assertEqual(m["state"], "draft")
        self.assertIsNone(m["sent_at"])
        m = msg.send_message(self.db, m["id"])
        self.assertEqual(m["state"], "sent")
        self.assertIsNotNone(m["sent_at"])
        picked = msg.fetch_unacked(self.db, "alpha")
        self.assertEqual([p["id"] for p in picked], [m["id"]])
        self.assertEqual(picked[0]["state"], "acknowledged")
        self.assertIsNotNone(picked[0]["acked_at"])
        # Pickup is one-shot: a second fetch finds nothing.
        self.assertEqual(msg.fetch_unacked(self.db, "alpha"),
                         [])
        m = msg.mark_done(self.db, m["id"])
        self.assertEqual(m["state"], "done")
        self.assertIsNotNone(m["done_at"])
        m = msg.archive_message(self.db, m["id"])
        self.assertEqual(m["state"], "archived")
        self.assertIsNotNone(m["archived_at"])
        events = [e["event"] for e in
                  msg.events_for(self.db, m["id"])]
        self.assertEqual(events, ["created", "sent",
                                  "acknowledged",
                                  "done", "archived"])

    def test_create_sent_directly(self):
        m = self.make(send=True)
        self.assertEqual(m["state"], "sent")
        events = [e["event"] for e in
                  msg.events_for(self.db, m["id"])]
        self.assertEqual(events, ["created", "sent"])

    def test_illegal_transitions_refused(self):
        m = self.make()
        with self.assertRaises(msg.MessageError):
            msg.mark_done(self.db, m["id"])       # draft->done
        with self.assertRaises(msg.MessageError):
            msg.archive_message(self.db, m["id"])  # draft->arch
        msg.send_message(self.db, m["id"])
        with self.assertRaises(msg.MessageError):
            msg.send_message(self.db, m["id"])     # sent->sent
        with self.assertRaises(msg.MessageError):
            msg.mark_done(self.db, m["id"])       # sent->done
        with self.assertRaises(msg.MessageError):
            msg.purge_message(self.db, m["id"])   # sent purge
        # The refused moves changed nothing.
        self.assertEqual(
            msg.get_message(self.db, m["id"])["state"], "sent")

    def test_validation(self):
        with self.assertRaises(msg.MessageError):
            self.make(author="mallory")
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="widget")
        with self.assertRaises(msg.MessageError):
            self.make(showcase=["not-a-dict"])
        with self.assertRaises(msg.MessageError):
            msg.list_messages(self.db, state="bogus")
        with self.assertRaises(msg.MessageError):
            msg.get_message(self.db, 9999)

    def test_showcase_round_trip(self):
        showcase = {"main": {"path": "SPEC.md",
                             "kind": "doc"},
                    "docs": [{"path": "a.py", "kind": "file"}]}
        m = self.make(showcase=showcase, anchor_type="plan",
                      anchor_ref="plan.md", send=True)
        self.assertEqual(m["showcase"], showcase)
        got = msg.get_message(self.db, m["id"])
        self.assertEqual(got["showcase"], showcase)


class TestPickup(StoreCase):
    def test_pickup_scoped_by_project_plus_workspace(self):
        a = self.make(project_slug="alpha", send=True)
        b = self.make(project_slug="beta", send=True)
        w = self.make(project_slug=None, send=True)
        self.make(project_slug="alpha")  # draft: not picked
        picked = msg.fetch_unacked(self.db, "alpha")
        self.assertEqual({p["id"] for p in picked},
                         {a["id"], w["id"]})
        # Beta's message is untouched by alpha's pickup.
        self.assertEqual(
            msg.get_message(self.db, b["id"])["state"], "sent")
        picked_all = msg.fetch_unacked(self.db)
        self.assertEqual([p["id"] for p in picked_all],
                         [b["id"]])


class TestThreading(StoreCase):
    def test_reply_and_thread_archive(self):
        root = self.make(project_slug="alpha", send=True)
        msg.fetch_unacked(self.db, "alpha")
        reply = msg.create_message(
            self.db, author="Muse", body="done it",
            project_slug="alpha", parent_id=root["id"],
            send=True)
        self.assertEqual(reply["parent_id"], root["id"])
        msg.mark_done(self.db, root["id"])
        msg.archive_message(self.db, root["id"])
        # The thread follows its root (§5.2).
        self.assertEqual(
            msg.get_message(self.db, reply["id"])["state"],
            "archived")
        with self.assertRaises(msg.MessageError):
            msg.create_message(self.db, author="Muse",
                               parent_id=4242)

    def test_purge_keeps_events(self):
        m = self.make()
        msg.purge_message(self.db, m["id"])  # draft -> purged
        with self.assertRaises(msg.MessageError):
            msg.get_message(self.db, m["id"])
        events = msg.events_for(self.db, m["id"])
        self.assertEqual([e["event"] for e in events],
                         ["created", "purged"])
        counts = msg.counts_by_state(self.db)
        self.assertEqual(sum(counts.values()), 0)


class TestReads(StoreCase):
    def test_list_filters_and_badge(self):
        from datetime import datetime, timedelta, timezone
        old = self.make(project_slug="alpha", send=True)
        self.make(project_slug="alpha")
        rows = msg.list_messages(self.db, project_slug="alpha")
        self.assertEqual(len(rows), 2)
        rows = msg.list_messages(self.db, state="draft")
        self.assertEqual(len(rows), 1)
        now = datetime.now(timezone.utc) + timedelta(days=15)
        rows = msg.list_messages(self.db, badge_days=14,
                                 now=now)
        by_id = {r["id"]: r for r in rows}
        self.assertTrue(by_id[old["id"]]["awaiting_pickup"])
        stats = msg.store_stats(self.db)
        self.assertEqual(stats["counts"]["sent"], 1)
        self.assertEqual(stats["counts"]["draft"], 1)
        self.assertIsNone(stats["last_cleanup_at"])


if __name__ == "__main__":
    unittest.main()
