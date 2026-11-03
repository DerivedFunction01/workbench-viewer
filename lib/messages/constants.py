"""Message-store constants, policy, schemas, and errors.

One slice of lib/messages (see the package docstring):
the state vocabulary, the selection-payload caps, the
legal-transition table, the cleanup policy defaults,
the store's own schema lineage (v1/v2/v3), and the
typed refusal.
"""

STATES = ("draft", "sent", "acknowledged", "done",
          "archived", "purged")
AUTHORS = ("owner", "Muse")
ANCHOR_TYPES = ("plan", "todo", "entry", "repo", "none",
                "text", "component")

# Selection payload rules (spec §12, annotation plan):
# quote cap at create (longer selections are refused,
# never truncated silently); prefix/suffix context caps;
# offset-shaped keys refused outright — quote + context is
# the anchor, raw offsets are too fragile across edits.
QUOTE_CAP = 500
CONTEXT_CAP = 120
OFFSET_KEYS = frozenset({
    "offset", "offsets", "start", "end", "char_offset",
    "start_offset", "end_offset", "char_start", "char_end",
    "range_start", "range_end",
})

# Legal transitions for the explicit mutation functions.
# cleanup() and the purge controls use their own guarded
# paths below; nothing else may move a message.
TRANSITIONS = {
    "draft": {"sent", "purged"},
    "sent": {"acknowledged", "archived"},
    "acknowledged": {"done", "archived"},
    "done": {"archived", "purged"},
    "archived": {"purged"},
    "purged": set(),
}

# Cleanup policy defaults (repo-home spec §5.3) — every
# value is config-tunable; the server builds the policy
# dict from the config seam and passes it in.
DEFAULT_POLICY = {
    "draft_ttl_days": 7,        # drafts untouched -> purged
    "done_archive_days": 30,    # done -> archived
    "archive_ttl_days": 90,     # archived -> purged
    "awaiting_badge_days": 14,  # sent-unacked -> badged
    "per_project_cap": 1000,    # non-archived roots/project
}

SCHEMA_V1 = """
CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_slug TEXT,
  anchor_type TEXT NOT NULL DEFAULT 'none',
  anchor_ref TEXT,
  author TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  showcase TEXT,
  state TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT,
  acked_at TEXT,
  done_at TEXT,
  archived_at TEXT,
  parent_id INTEGER REFERENCES messages(id)
);
CREATE TABLE message_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER,
  event TEXT NOT NULL,
  at TEXT NOT NULL,
  detail TEXT
);
CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE INDEX idx_messages_project_state
  ON messages(project_slug, state);
CREATE INDEX idx_messages_parent ON messages(parent_id);
"""

# Schema v2 (spec §15.1): the watcher outbox. One row per
# transition into `sent`, written in the same transaction
# as the state change (see _outbox). Consumers poll by id
# and keep their own checkpoints; `anchor_summary` is the
# human first line a wake-up handoff carries (§15.2).
SCHEMA_V2 = """
CREATE TABLE outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER NOT NULL,
  project_slug TEXT,
  anchor_type TEXT NOT NULL DEFAULT 'none',
  anchor_ref TEXT,
  anchor_summary TEXT,
  event TEXT NOT NULL DEFAULT 'sent',
  at TEXT NOT NULL
);
CREATE INDEX idx_outbox_message ON outbox(message_id);
"""

# Schema v3 (spec §12): the annotation selection payload.
# One nullable column; plain messages carry NULL. Existing
# rows are untouched — a NULL selection on a text/component
# anchor cannot occur (create validates), and pre-v3 rows
# are all plain anchors by construction.
SCHEMA_V3 = """
ALTER TABLE messages ADD COLUMN selection TEXT;
"""

SCHEMA_VERSION = 3


class MessageError(Exception):
    """A message-store mutation was refused, with a reason."""
