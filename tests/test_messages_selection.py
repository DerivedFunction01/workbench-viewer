"""Annotation selection payloads (spec §12): the schema
v3 migration, payload validation on the one create path,
and the round trip. The store's migration lineage is its
own: v1 = messages tables, v2 = watcher outbox,
v3 = the selection column — each step preserves rows.

Re-location lives in test_annotations.py; the HTTP round
trip in test_server_annotations.py.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lib import messages as msg

TEXT_SELECTION = {
    "kind": "text",
    "component_id": "plans/step-3",
    "component_label": "Step 3",
    "section_heading": "Steps",
    "quote": "Anything that moved is listed.",
    "prefix": "compare the result. ",
    "suffix": " Only then close.",
}

COMPONENT_SELECTION = {
    "kind": "component",
    "component_id": "summary/bars-by-year",
    "component_label": "chart · bars-by-year",
    "entry_id": "entry-1",
}


def bare_db(path, scripts, version):
    """Build a store file by hand at an older schema
    version (the fixture the migration must survive)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    for script in scripts:
        conn.executescript(script)
    conn.execute(f"PRAGMA user_version = {version}")
    conn.execute(
        "INSERT INTO messages (project_slug, anchor_type,"
        " anchor_ref, author, body, state, created_at,"
        " updated_at) VALUES ('alpha', 'plan', 'p.md',"
        " 'owner', 'old row', 'sent', '2026-01-01T00:00:00"
        "+00:00', '2026-01-01T00:00:00+00:00')")
    conn.execute(
        "INSERT INTO message_events (message_id, event,"
        " at) VALUES (1, 'created', '2026-01-01T00:00:00"
        "+00:00')")
    conn.commit()
    conn.close()


class SelectionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-sel-"))
        self.db = self.tmp / "state" / "messages.db"

    def version(self):
        conn = msg.connect(self.db)
        try:
            return conn.execute(
                "PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()


class TestMigration(SelectionCase):
    def test_fresh_db_starts_at_v3(self):
        msg.connect(self.db).close()
        self.assertEqual(self.version(), 3)

    def test_v1_fixture_migrates_rows_intact(self):
        bare_db(self.db, [msg.SCHEMA_V1], 1)
        self.assertEqual(self.version(), 3)
        rows = msg.list_messages(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["body"], "old row")
        self.assertIsNone(rows[0]["selection"])
        events = msg.events_for(self.db, 1)
        self.assertEqual([e["event"] for e in events],
                         ["created"])

    def test_v2_fixture_migrates_with_outbox(self):
        bare_db(self.db, [msg.SCHEMA_V1, msg.SCHEMA_V2], 2)
        self.assertEqual(self.version(), 3)
        self.assertEqual(msg.store_stats(self.db)
                         ["outbox_rows"], 0)
        rows = msg.list_messages(self.db)
        self.assertIsNone(rows[0]["selection"])

    def test_unsupported_version_refused(self):
        bare_db(self.db, [msg.SCHEMA_V1], 1)
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA user_version = 99")
        conn.commit()
        conn.close()
        with self.assertRaises(msg.MessageError):
            msg.connect(self.db)


class TestSelectionPayload(SelectionCase):
    def make(self, **kw):
        kw.setdefault("author", "owner")
        kw.setdefault("body", "a comment")
        kw.setdefault("project_slug", "alpha")
        return msg.create_message(self.db, **kw)

    def test_text_round_trip(self):
        m = self.make(anchor_type="text",
                      anchor_ref="plan.md",
                      selection=dict(TEXT_SELECTION))
        self.assertEqual(m["selection"], TEXT_SELECTION)
        got = msg.get_message(self.db, m["id"])
        self.assertEqual(got["selection"], TEXT_SELECTION)
        rows = msg.list_messages(self.db)
        self.assertEqual(rows[0]["selection"],
                         TEXT_SELECTION)

    def test_component_round_trip(self):
        m = self.make(anchor_type="component",
                      anchor_ref="entry-1",
                      selection=dict(COMPONENT_SELECTION),
                      send=True)
        self.assertEqual(m["selection"],
                         COMPONENT_SELECTION)
        self.assertEqual(m["state"], "sent")

    def test_plain_message_has_no_selection(self):
        m = self.make(anchor_type="plan",
                      anchor_ref="plan.md")
        self.assertIsNone(m["selection"])

    def test_missing_selection_refused(self):
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      anchor_ref="plan.md")

    def test_selection_on_plain_anchor_refused(self):
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="plan",
                      anchor_ref="plan.md",
                      selection=dict(TEXT_SELECTION))
        with self.assertRaises(msg.MessageError):
            self.make(selection=dict(TEXT_SELECTION))

    def test_missing_anchor_ref_refused(self):
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      selection=dict(TEXT_SELECTION))

    def test_kind_mismatch_refused(self):
        bad = dict(TEXT_SELECTION, kind="component")
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      anchor_ref="plan.md", selection=bad)

    def test_missing_component_id_refused(self):
        bad = dict(TEXT_SELECTION)
        del bad["component_id"]
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      anchor_ref="plan.md", selection=bad)

    def test_missing_quote_refused(self):
        bad = dict(TEXT_SELECTION)
        del bad["quote"]
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      anchor_ref="plan.md", selection=bad)

    def test_oversize_quote_refused_not_truncated(self):
        bad = dict(TEXT_SELECTION,
                   quote="x" * (msg.QUOTE_CAP + 1))
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      anchor_ref="plan.md", selection=bad)
        # At the cap exactly: accepted whole.
        ok = dict(TEXT_SELECTION, quote="x" * msg.QUOTE_CAP)
        m = self.make(anchor_type="text",
                      anchor_ref="plan.md", selection=ok)
        self.assertEqual(len(m["selection"]["quote"]),
                         msg.QUOTE_CAP)

    def test_oversize_context_refused(self):
        bad = dict(TEXT_SELECTION,
                   prefix="p" * (msg.CONTEXT_CAP + 1))
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="text",
                      anchor_ref="plan.md", selection=bad)

    def test_offset_keys_refused(self):
        for key in ("offset", "start", "end", "char_offset"):
            bad = dict(TEXT_SELECTION, **{key: 12})
            with self.assertRaises(msg.MessageError,
                                   msg=f"key {key}"):
                self.make(anchor_type="text",
                          anchor_ref="plan.md", selection=bad)
        bad = dict(COMPONENT_SELECTION, offset=3)
        with self.assertRaises(msg.MessageError):
            self.make(anchor_type="component",
                      anchor_ref="entry-1", selection=bad)

    def test_reply_cannot_carry_selection(self):
        root = self.make(anchor_type="text",
                         anchor_ref="plan.md",
                         selection=dict(TEXT_SELECTION),
                         send=True)
        with self.assertRaises(msg.MessageError):
            msg.create_message(
                self.db, author="Muse", body="reply",
                project_slug="alpha", parent_id=root["id"],
                anchor_type="text", anchor_ref="plan.md",
                selection=dict(TEXT_SELECTION), send=True)
        # A plain reply is fine (it inherits the anchor).
        reply = msg.create_message(
            self.db, author="Muse", body="reply",
            project_slug="alpha", parent_id=root["id"],
            send=True)
        self.assertIsNone(reply["selection"])


if __name__ == "__main__":
    unittest.main()
