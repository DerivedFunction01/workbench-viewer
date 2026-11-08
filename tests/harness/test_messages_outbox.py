"""Repo-home spec §15.1: the watcher core — the outbox
table, its same-transaction rule, the poll semantics,
cleanup pruning, the v1 -> v2 migration, and the generic
notify targets (lib/notify).

Atomicity is proven by sabotage: forcing a failure on
either side of the state change (the event append, the
outbox append) must roll BOTH back — no sent message
without an outbox row, no outbox row without a sent
message.
"""

import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from lib import messages as msg
from lib import notify as notify_mod


class OutboxCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-outbox-"))
        self.db = self.tmp / "messages.db"

    def send_one(self, **kw):
        return msg.create_message(
            self.db, author="owner", send=True,
            body="First line\nsecond line", **kw)

    def test_born_sent_writes_outbox_row(self):
        m = self.send_one(project_slug="alpha",
                          anchor_type="plan",
                          anchor_ref="plan.md")
        rows = msg.list_outbox(self.db)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["message_id"], m["id"])
        self.assertEqual(row["project_slug"], "alpha")
        self.assertEqual(row["anchor_type"], "plan")
        self.assertEqual(row["anchor_ref"], "plan.md")
        self.assertEqual(row["anchor_summary"], "First line")
        self.assertEqual(row["event"], "sent")
        self.assertTrue(row["at"])

    def test_draft_writes_nothing_then_send_writes_one(self):
        m = msg.create_message(self.db, author="Muse",
                               body="a draft")
        self.assertEqual(msg.list_outbox(self.db), [])
        msg.send_message(self.db, m["id"])
        rows = msg.list_outbox(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["message_id"], m["id"])

    def test_sent_reply_writes_outbox_row(self):
        root = self.send_one()
        reply = msg.create_message(
            self.db, author="Muse", body="done — see the "
            "checkpoint", parent_id=root["id"], send=True)
        rows = msg.list_outbox(self.db)
        self.assertEqual([r["message_id"] for r in rows],
                         [root["id"], reply["id"]])

    def test_non_sent_transitions_write_nothing(self):
        m = self.send_one()
        msg.fetch_unacked(self.db)          # -> acknowledged
        msg.mark_done(self.db, m["id"])     # -> done
        msg.archive_message(self.db, m["id"])  # -> archived
        self.assertEqual(len(msg.list_outbox(self.db)), 1)

    def test_atomicity_outbox_failure_rolls_back_send(self):
        m = msg.create_message(self.db, author="owner",
                               body="draft")
        with mock.patch.object(
                msg, "_outbox",
                side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                msg.send_message(self.db, m["id"])
        got = msg.get_message(self.db, m["id"])
        self.assertEqual(got["state"], "draft")
        self.assertIsNone(got["sent_at"])
        self.assertEqual(msg.list_outbox(self.db), [])
        events = [e["event"] for e in
                  msg.events_for(self.db, m["id"])]
        self.assertNotIn("sent", events)

    def test_atomicity_event_failure_leaves_no_outbox(self):
        real_event = msg._event

        def flaky(conn, mid, event, detail=None):
            if event == "sent":
                raise RuntimeError("boom")
            return real_event(conn, mid, event, detail)

        with mock.patch.object(msg, "_event",
                               side_effect=flaky):
            with self.assertRaises(RuntimeError):
                self.send_one()
        self.assertEqual(msg.list_outbox(self.db), [])
        self.assertEqual(
            sum(msg.counts_by_state(self.db).values()), 0)

    def test_poll_after_and_limit(self):
        ids = [self.send_one()["id"] for _ in range(3)]
        rows = msg.list_outbox(self.db)
        self.assertEqual([r["message_id"] for r in rows], ids)
        first_id = rows[0]["id"]
        rest = msg.list_outbox(self.db, after=first_id)
        self.assertEqual([r["message_id"] for r in rest],
                         ids[1:])
        one = msg.list_outbox(self.db, after=0, limit=1)
        self.assertEqual(len(one), 1)
        # Reading never consumes: a re-poll returns the same.
        self.assertEqual(msg.list_outbox(self.db), rows)

    def test_notify_checkpoint_roundtrip(self):
        self.assertEqual(msg.notify_checkpoint(self.db), 0)
        msg.set_notify_checkpoint(self.db, 42)
        self.assertEqual(msg.notify_checkpoint(self.db), 42)
        stats = msg.store_stats(self.db)
        self.assertEqual(stats["notify_checkpoint"], 42)

    def test_cleanup_prunes_outbox_past_archive_horizon(self):
        self.send_one()
        old = msg.list_outbox(self.db)[0]
        conn = sqlite3.connect(str(self.db))
        ancient = (datetime.now(timezone.utc)
                   - timedelta(days=120)).isoformat()
        conn.execute("UPDATE outbox SET at = ? WHERE id = ?",
                     (ancient, old["id"]))
        conn.commit()
        conn.close()
        self.send_one()  # a fresh row, must survive
        counts = msg.cleanup(self.db, known_slugs=["x"])
        self.assertEqual(counts["outbox_pruned"], 1)
        rows = msg.list_outbox(self.db)
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["id"], old["id"])
        # Idempotent at the same state.
        counts = msg.cleanup(self.db, known_slugs=["x"])
        self.assertEqual(counts["outbox_pruned"], 0)

    def test_migration_v1_to_v2_keeps_messages(self):
        conn = sqlite3.connect(str(self.db))
        conn.executescript(msg.SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO messages (project_slug, anchor_type,"
            " author, body, state, created_at, updated_at,"
            " sent_at) VALUES ('alpha', 'none', 'owner',"
            " 'old sent', 'sent', '2026-01-01T00:00:00+00:00',"
            " '2026-01-01T00:00:00+00:00',"
            " '2026-01-01T00:00:00+00:00')")
        conn.commit()
        conn.close()
        opened = msg.connect(self.db)
        try:
            version = opened.execute(
                "PRAGMA user_version").fetchone()[0]
        finally:
            opened.close()
        self.assertEqual(version, msg.SCHEMA_VERSION)
        rows = msg.list_messages(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["body"], "old sent")
        # No backfill: an event exists only with its state
        # change (§15.1), and this one predates the outbox.
        self.assertEqual(msg.list_outbox(self.db), [])


class NotifyCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-notify-"))
        self.db = self.tmp / "messages.db"
        msg.create_message(self.db, author="owner", send=True,
                           body="wake up", project_slug="alpha")
        self.event = msg.list_outbox(self.db)[0]

    def test_no_targets_no_attempts(self):
        self.assertEqual(
            notify_mod.fire_targets(
                {"webhook": None, "command": None},
                [self.event]),
            [])

    def test_command_target_gets_event_json_on_stdin(self):
        out = self.tmp / "event.json"
        results = notify_mod.fire_targets(
            {"webhook": None,
             "command": f"cat > {out}"}, [self.event])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["ok"], results)
        payload = json.loads(out.read_text())
        self.assertEqual(payload["message_id"],
                         self.event["message_id"])
        self.assertEqual(payload["anchor_summary"], "wake up")
        self.assertEqual(payload["project_slug"], "alpha")

    def test_command_failure_is_reported_not_raised(self):
        results = notify_mod.fire_targets(
            {"webhook": None, "command": "exit 3"},
            [self.event])
        self.assertFalse(results[0]["ok"])
        self.assertIn("exit 3", results[0]["detail"])

    def test_webhook_target_posts_event_json(self):
        received = []

        class Hook(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(
                    int(self.headers["Content-Length"]))
                received.append(json.loads(body))
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Hook)
        thread = threading.Thread(target=server.serve_forever,
                                  daemon=True)
        thread.start()
        try:
            url = (f"http://127.0.0.1:"
                   f"{server.server_address[1]}/hook")
            results = notify_mod.fire_targets(
                {"webhook": url, "command": None},
                [self.event])
        finally:
            server.shutdown()
        self.assertTrue(results[0]["ok"], results)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["id"], self.event["id"])

    def test_dead_webhook_is_reported_not_raised(self):
        results = notify_mod.fire_targets(
            {"webhook": "http://127.0.0.1:1/hook",
             "command": None}, [self.event], timeout=2)
        self.assertFalse(results[0]["ok"])


if __name__ == "__main__":
    unittest.main()
