"""The viewer-tied message store (repo-home spec §5).

Messages live in a SQLite database owned by the VIEWER — in
the server's state directory, never inside a project repo,
never in a project registry (the owner's ruling, repo-home spec
D4). Projects are referenced by slug only. The store carries
its OWN `user_version` lineage, independent of the registry
schema: adopting the viewer needs no registry migration to
receive messages.

Same store discipline as lib/registry.py: WAL + busy_timeout
on every connection, ONE short BEGIN IMMEDIATE per mutation,
append-only `message_events` audit (a purged message's rows
are deleted; its event rows remain). Every function takes an
explicit db path so tests run on temp files. Stdlib only.

State machine (spec §5.2), enforced here — the ONLY path:
  draft -> sent -> acknowledged -> done -> archived -> purged
Side exits: draft -> purged and done -> purged happen only
through the manual purge controls (spec §5.4); the cleanup
pass (cleanup()) drives draft -> purged, done -> archived,
archived -> purged on the §5.3 schedule, plus orphan and
cap archiving. Sent-but-unacknowledged messages are never
purged by anything automatic.

Watcher core (spec §15.1): every transition INTO `sent`
also writes one row to the `outbox` table IN THE SAME
TRANSACTION as the state change — an event can never
exist without its state change or vice versa. Consumers
poll list_outbox(after=<id>) and keep their own
checkpoints; the cleanup pass prunes outbox rows once
they age past the archived horizon. The server's notify
checkpoint (meta key `notify_checkpoint`) is read/written
through the helpers here so no SQL lives outside lib/.

Annotations (spec §12): an annotation is a message whose
anchor is a SELECTION — a text passage in a plan
(anchor_type `text`) or a component in a mockup exhibit
(anchor_type `component`). The selection payload rides in
the nullable `selection` JSON column (schema v3): quote +
surrounding context for text, the deterministic manifest
component id for components. Raw offsets are REFUSED at
create — quote + context is the anchor, re-located at
read time by lib/annotations.py (never stored back).
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .util import now_iso, parse_iso

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


def connect(db_path, *, busy_timeout_ms: int = 5000,
            create: bool = True) -> sqlite3.Connection:
    """Open the message store, migrating to the current
    schema. The store is created on first use (it is the
    viewer's own data, so creation is never a refusal)."""
    db_path = Path(db_path)
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path),
                           timeout=busy_timeout_ms / 1000.0,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    conn.execute("PRAGMA journal_mode = WAL")
    _migrate(conn)
    return conn


def _migrate(conn):
    """Stepwise, one version at a time (the store's own
    user_version lineage): 0 -> 1 creates the v1 schema,
    1 -> 2 adds the watcher outbox (existing rows are
    untouched — the outbox starts empty; nothing already
    sent is backfilled, per §15.1's same-transaction rule:
    an event exists only with its state change), 2 -> 3
    adds the annotation selection column (§12)."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        conn.executescript(SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
        version = 1
    if version == 1:
        conn.executescript(SCHEMA_V2)
        conn.execute("PRAGMA user_version = 2")
        version = 2
    if version == 2:
        conn.executescript(SCHEMA_V3)
        conn.execute("PRAGMA user_version = 3")
        version = 3
    if version != SCHEMA_VERSION:
        raise MessageError(
            f"unsupported messages schema version {version}")


@contextmanager
def _tx(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _event(conn, message_id, event, detail=None):
    conn.execute(
        "INSERT INTO message_events (message_id, event, at,"
        " detail) VALUES (?, ?, ?, ?)",
        (message_id, event, now_iso(), detail))


def _row(conn, message_id) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM messages WHERE id = ?",
                       (message_id,)).fetchone()
    if row is None:
        raise MessageError(f"unknown message: {message_id}")
    return row


def message_dict(row) -> dict:
    out = dict(row)
    raw = out.get("showcase")
    if raw:
        try:
            out["showcase"] = json.loads(raw)
        except json.JSONDecodeError:
            out["showcase"] = None
    raw = out.get("selection")
    if raw:
        try:
            out["selection"] = json.loads(raw)
        except json.JSONDecodeError:
            out["selection"] = None
    return out


def _validate_selection(anchor_type, anchor_ref, selection,
                        parent_id):
    """The selection-payload rules (spec §12 + the
    annotation plan's anchor design), enforced on the one
    create path:

      - required iff anchor_type is text/component,
        forbidden otherwise (and on replies — the thread
        root holds the anchor; replies inherit it for
        display);
      - kind must match the anchor type;
      - text: component_id + quote (<= QUOTE_CAP) required,
        prefix/suffix <= CONTEXT_CAP;
      - component: component_id required (the manifest id,
        verbatim);
      - any offset-shaped key is refused outright: quote
        + context is the anchor, raw offsets are too
        fragile across edits.
    Returns the payload to store (or None)."""
    if anchor_type not in ("text", "component"):
        if selection is not None:
            raise MessageError(
                "selection payload requires anchor_type "
                "'text' or 'component' (got "
                f"{anchor_type!r})")
        return None
    if parent_id is not None:
        raise MessageError(
            "replies carry no selection payload — the "
            "thread root holds the anchor")
    if not anchor_ref:
        raise MessageError(
            f"anchor_type {anchor_type!r} requires "
            "anchor_ref (the plan path for text, the entry "
            "id for component)")
    if selection is None:
        raise MessageError(
            f"annotation (anchor_type {anchor_type!r}) "
            "requires a selection payload")
    if not isinstance(selection, dict):
        raise MessageError("selection must be an object")
    bad = sorted(OFFSET_KEYS & selection.keys())
    if bad:
        raise MessageError(
            f"selection must not carry raw offsets "
            f"(key {bad[0]!r}): quote + context is the "
            "anchor (spec §12)")
    kind = selection.get("kind")
    if kind != anchor_type:
        raise MessageError(
            f"selection kind {kind!r} does not match "
            f"anchor_type {anchor_type!r}")
    component_id = selection.get("component_id")
    if not isinstance(component_id, str) \
            or not component_id.strip():
        raise MessageError(
            "selection requires a component_id (the "
            "enclosing component's data-anchor id)")
    label = selection.get("component_label")
    if label is not None and not isinstance(label, str):
        raise MessageError(
            "selection component_label must be a string")
    if anchor_type == "text":
        quote = selection.get("quote")
        if not isinstance(quote, str) or not quote:
            raise MessageError(
                "text selection requires a quote (the "
                "selected text, verbatim)")
        if len(quote) > QUOTE_CAP:
            raise MessageError(
                f"selection quote is {len(quote)} chars; "
                f"the cap is {QUOTE_CAP} — select a "
                "shorter passage")
        for key in ("prefix", "suffix"):
            value = selection.get(key)
            if value is not None:
                if not isinstance(value, str):
                    raise MessageError(
                        f"selection {key} must be a string")
                if len(value) > CONTEXT_CAP:
                    raise MessageError(
                        f"selection {key} is {len(value)} "
                        f"chars; the cap is {CONTEXT_CAP}")
        heading = selection.get("section_heading")
        if heading is not None \
                and not isinstance(heading, str):
            raise MessageError(
                "selection section_heading must be a "
                "string")
    else:
        entry_id = selection.get("entry_id")
        if entry_id is not None \
                and not isinstance(entry_id, str):
            raise MessageError(
                "selection entry_id must be a string")
    return selection


def _check_transition(row, target, verb):
    if target not in TRANSITIONS[row["state"]]:
        raise MessageError(
            f"message {row['id']}: cannot {verb} from state "
            f"{row['state']!r} (allowed: "
            f"{sorted(TRANSITIONS[row['state']]) or 'none'})")


def _outbox(conn, row):
    """Append the watcher outbox row for a transition into
    `sent` (§15.1) — called INSIDE the same transaction as
    the state change, never on its own. The anchor summary
    is the body's first line, clipped: a wake-up handoff
    carries the summary, never the whole message (§15.2)."""
    body = row["body"] or ""
    first = body.strip().split("\n")[0].strip() \
        if body.strip() else ""
    conn.execute(
        "INSERT INTO outbox (message_id, project_slug,"
        " anchor_type, anchor_ref, anchor_summary, event,"
        " at) VALUES (?, ?, ?, ?, ?, 'sent', ?)",
        (row["id"], row["project_slug"], row["anchor_type"],
         row["anchor_ref"], first[:120] or None, now_iso()))


def _move(conn, row, target, *, event, detail=None,
          stamp=None):
    """Apply a state move inside the caller's transaction:
    set state + the state's timestamp column + updated_at,
    and append the event. A move INTO `sent` also appends
    the outbox row (§15.1) in this same transaction."""
    ts = now_iso()
    sets = {"state": target, "updated_at": ts}
    if stamp:
        sets[stamp] = ts
    cols = ", ".join(f"{k} = ?" for k in sets)
    conn.execute(f"UPDATE messages SET {cols} WHERE id = ?",
                 (*sets.values(), row["id"]))
    _event(conn, row["id"], event, detail)
    if target == "sent":
        _outbox(conn, row)


# ----------------------------------------------------------------
# Mutations (the one path — server endpoints call these)
# ----------------------------------------------------------------

def create_message(db_path, *, author, body="",
                   project_slug=None, anchor_type="none",
                   anchor_ref=None, showcase=None,
                   parent_id=None, send=False,
                   selection=None) -> dict:
    """Create a message: a draft, or sent when send=True.
    A reply is a create with parent_id set (replies are
    normally sent immediately — spec §7 — so pass send=True).
    An annotation is a create with anchor_type text/component
    and a validated selection payload (§12). Returns the
    stored message."""
    if author not in AUTHORS:
        raise MessageError(
            f"bad author {author!r}: one of {AUTHORS}")
    if anchor_type not in ANCHOR_TYPES:
        raise MessageError(
            f"bad anchor_type {anchor_type!r}: "
            f"one of {ANCHOR_TYPES}")
    if showcase is not None and not isinstance(showcase, dict):
        raise MessageError("showcase must be an object "
                           "{main: ref, docs: [ref...]}")
    selection = _validate_selection(anchor_type, anchor_ref,
                                    selection, parent_id)
    conn = connect(db_path)
    try:
        with _tx(conn):
            if parent_id is not None:
                _row(conn, parent_id)  # must exist
            ts = now_iso()
            cur = conn.execute(
                "INSERT INTO messages (project_slug,"
                " anchor_type, anchor_ref, author, body,"
                " showcase, state, created_at, updated_at,"
                " sent_at, parent_id, selection) VALUES"
                " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_slug, anchor_type, anchor_ref, author,
                 body,
                 json.dumps(showcase) if showcase else None,
                 "sent" if send else "draft", ts, ts,
                 ts if send else None, parent_id,
                 json.dumps(selection) if selection else None))
            mid = cur.lastrowid
            _event(conn, mid, "created",
                   "reply" if parent_id is not None else None)
            if send:
                _event(conn, mid, "sent")
                # Born sent: the outbox row lands in this
                # same transaction (§15.1).
                _outbox(conn, _row(conn, mid))
            return message_dict(_row(conn, mid))
    finally:
        conn.close()


def update_draft(db_path, message_id, body) -> dict:
    """Replace a draft's body (the composer's autosave,
    D7: drafts are state=draft messages from the first
    keystroke-save, so editing one is a store mutation,
    not a client-side fiction). Drafts only — a sent
    message's body is its record. Bumps updated_at, so
    the §5.3 draft TTL measures from the last edit."""
    if not isinstance(body, str):
        raise MessageError("draft body must be a string")
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, message_id)
            if row["state"] != "draft":
                raise MessageError(
                    f"message {message_id}: body can only "
                    f"be edited while a draft (state is "
                    f"{row['state']!r})")
            conn.execute(
                "UPDATE messages SET body = ?,"
                " updated_at = ? WHERE id = ?",
                (body, now_iso(), message_id))
            _event(conn, message_id, "edited")
            return message_dict(_row(conn, message_id))
    finally:
        conn.close()


def send_message(db_path, message_id) -> dict:
    """draft -> sent."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, message_id)
            _check_transition(row, "sent", "send")
            _move(conn, row, "sent", event="sent",
                  stamp="sent_at")
            return message_dict(_row(conn, message_id))
    finally:
        conn.close()


def fetch_unacked(db_path, project_slug=None) -> list:
    """Agent pickup (spec D3): return the sent (not yet
    acknowledged) messages and mark them acknowledged in the
    SAME transaction — the fetch IS the acknowledgement, and
    the fetch is recorded in message_events. With a project
    slug, that project's messages plus workspace-wide ones
    (project_slug NULL) are picked up; with None, all."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            if project_slug is None:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE state ="
                    " 'sent' ORDER BY id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE state ="
                    " 'sent' AND (project_slug = ? OR"
                    " project_slug IS NULL) ORDER BY id",
                    (project_slug,)).fetchall()
            out = []
            for row in rows:
                _move(conn, row, "acknowledged",
                      event="acknowledged", stamp="acked_at",
                      detail="pickup fetch")
                out.append(message_dict(_row(conn, row["id"])))
            return out
    finally:
        conn.close()


def mark_done(db_path, message_id) -> dict:
    """acknowledged -> done (the explicit post-back, §7)."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, message_id)
            _check_transition(row, "done", "mark done")
            _move(conn, row, "done", event="done",
                  stamp="done_at")
            return message_dict(_row(conn, message_id))
    finally:
        conn.close()


def archive_message(db_path, message_id) -> dict:
    """done/sent/acknowledged -> archived. Archiving a root
    archives its whole thread (a thread's state is its
    root's state, §5.2)."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, message_id)
            _check_transition(row, "archived", "archive")
            _archive_tree(conn, row, detail="manual")
            return message_dict(_row(conn, message_id))
    finally:
        conn.close()


def _archive_tree(conn, row, *, detail):
    """Archive a message and every descendant, inside the
    caller's transaction. Already-archived descendants are
    left as-is."""
    _move(conn, row, "archived", event="archived",
          stamp="archived_at", detail=detail)
    for child in conn.execute(
            "SELECT * FROM messages WHERE parent_id = ?"
            " AND state != 'archived'", (row["id"],)):
        _archive_tree(conn, child, detail=detail)


def purge_message(db_path, message_id, *, detail="manual"):
    """Delete a message row outright (manual control, §5.4 —
    legal only from draft/done/archived). The message_events
    rows remain: the audit outlives the message."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, message_id)
            _check_transition(row, "purged", "purge")
            _purge_row(conn, row, detail=detail)
    finally:
        conn.close()


def _purge_row(conn, row, *, detail):
    _event(conn, row["id"], "purged", detail)
    conn.execute("DELETE FROM messages WHERE id = ?",
                 (row["id"],))


# ----------------------------------------------------------------
# Reads
# ----------------------------------------------------------------

def get_message(db_path, message_id) -> dict:
    conn = connect(db_path)
    try:
        return message_dict(_row(conn, message_id))
    finally:
        conn.close()


def list_messages(db_path, *, project_slug=None, state=None,
                  anchor_type=None, anchor_ref=None,
                  badge_days=None, now=None) -> list:
    """Filtered list, oldest first. The anchor filters are
    how a plan/entry view fetches exactly its annotations
    (§12). Each row carries the derived `awaiting_pickup`
    flag when badge_days is given: state sent and sent_at
    older than the badge threshold (§5.3 — a display
    derivation, never stored)."""
    clauses, params = [], []
    if project_slug is not None:
        clauses.append("(project_slug = ? OR"
                       " project_slug IS NULL)")
        params.append(project_slug)
    if state is not None:
        if state not in STATES:
            raise MessageError(f"bad state {state!r}")
        clauses.append("state = ?")
        params.append(state)
    if anchor_type is not None:
        if anchor_type not in ANCHOR_TYPES:
            raise MessageError(
                f"bad anchor_type {anchor_type!r}")
        clauses.append("anchor_type = ?")
        params.append(anchor_type)
    if anchor_ref is not None:
        clauses.append("anchor_ref = ?")
        params.append(anchor_ref)
    where = (" WHERE " + " AND ".join(clauses)) if clauses \
        else ""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM messages{where} ORDER BY id",
            params).fetchall()
    finally:
        conn.close()
    out = [message_dict(r) for r in rows]
    if badge_days is not None:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=badge_days)
        for m in out:
            m["awaiting_pickup"] = bool(
                m["state"] == "sent" and m["sent_at"]
                and parse_iso(m["sent_at"]) < cutoff)
    return out


def counts_by_state(db_path) -> dict:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT state, COUNT(*) AS n FROM messages"
            " GROUP BY state").fetchall()
    finally:
        conn.close()
    counts = {s: 0 for s in STATES if s != "purged"}
    for r in rows:
        counts[r["state"]] = r["n"]
    return counts


def events_for(db_path, message_id) -> list:
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM message_events WHERE"
            " message_id = ? ORDER BY id", (message_id,))]
    finally:
        conn.close()


def list_outbox(db_path, *, after=0, limit=500) -> list:
    """Watcher poll (spec §15.1): outbox rows with id >
    `after`, oldest first. Consumers keep their own
    last-seen id and pass it back — the store never marks
    events consumed (acknowledgement stays an agent act,
    §15.2)."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM outbox WHERE id > ? ORDER BY id"
            " LIMIT ?", (int(after), int(limit))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def notify_checkpoint(db_path) -> int:
    """The server maintenance loop's own outbox checkpoint
    (§15.1: kept in the store's meta). 0 = nothing fired
    yet."""
    conn = connect(db_path)
    try:
        raw = _get_meta(conn, "notify_checkpoint")
        return int(raw) if raw else 0
    finally:
        conn.close()


def set_notify_checkpoint(db_path, event_id) -> None:
    conn = connect(db_path)
    try:
        with _tx(conn):
            _set_meta(conn, "notify_checkpoint",
                      str(int(event_id)))
    finally:
        conn.close()


def _get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?",
                       (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value ="
        " excluded.value", (key, value))


# ----------------------------------------------------------------
# Cleanup lifecycle (spec §5.3/§5.4)
# ----------------------------------------------------------------

def _older(ts, now, days) -> bool:
    return bool(ts) and parse_iso(ts) < now - timedelta(
        days=days)


def cleanup(db_path, *, known_slugs=None, policy=None,
            now=None) -> dict:
    """One idempotent cleanup pass (§5.3). All thresholds
    come from the policy dict (DEFAULT_POLICY merged with
    the caller's values — the server builds it from the
    config seam). Rules, in order:

      drafts untouched draft_ttl_days        -> purged
      done older than done_archive_days      -> archived
      archived older than archive_ttl_days   -> purged
      project no longer discovered (orphans) -> archived
      per-project cap overflow               -> oldest
        DONE roots archived first; sent/acknowledged
        roots are never archived by the cap

    Sent-but-unacknowledged messages are NEVER purged.
    The orphan rule is skipped when known_slugs is None
    or empty — a failed sweep must not archive the world.
    Counts count ROOT messages for archive moves (a
    thread follows its root) and rows for purges. The
    pass records itself in meta (last_cleanup_at/counts)
    in the same transaction, so a re-run at the same clock
    changes nothing.

    The watcher outbox is pruned in the same pass (§15.1):
    rows older than the archived horizon (archive_ttl_days)
    are deleted — consumers checkpoint by id, and an event
    older than the horizon has outlived every message it
    could wake anyone about."""
    policy = {**DEFAULT_POLICY, **(policy or {})}
    now = now or datetime.now(timezone.utc)
    counts = {"drafts_purged": 0, "done_archived": 0,
              "archived_purged": 0, "orphans_archived": 0,
              "cap_archived": 0, "outbox_pruned": 0}
    conn = connect(db_path)
    try:
        with _tx(conn):
            for row in conn.execute(
                    "SELECT * FROM messages WHERE state ="
                    " 'draft'").fetchall():
                if _older(row["updated_at"], now,
                          policy["draft_ttl_days"]):
                    _purge_row(conn, row,
                               detail="cleanup: draft ttl")
                    counts["drafts_purged"] += 1
            for row in conn.execute(
                    "SELECT * FROM messages WHERE state ="
                    " 'done' AND parent_id IS NULL").fetchall():
                if _older(row["done_at"], now,
                          policy["done_archive_days"]):
                    _archive_tree(conn, row,
                                  detail="cleanup: done age")
                    counts["done_archived"] += 1
            for row in conn.execute(
                    "SELECT * FROM messages WHERE state ="
                    " 'archived'").fetchall():
                if _older(row["archived_at"], now,
                          policy["archive_ttl_days"]):
                    _purge_row(conn, row,
                               detail="cleanup: archive ttl")
                    counts["archived_purged"] += 1
            if known_slugs:
                known = set(known_slugs)
                for row in conn.execute(
                        "SELECT * FROM messages WHERE"
                        " project_slug IS NOT NULL AND state"
                        " != 'archived' AND parent_id IS NULL"
                        ).fetchall():
                    if row["project_slug"] not in known:
                        _archive_tree(
                            conn, row,
                            detail="cleanup: orphan project")
                        counts["orphans_archived"] += 1
            cap = policy["per_project_cap"]
            roots = conn.execute(
                "SELECT * FROM messages WHERE parent_id IS"
                " NULL AND state != 'archived' ORDER BY id"
            ).fetchall()
            by_project = {}
            for row in roots:
                by_project.setdefault(
                    row["project_slug"], []).append(row)
            for slug, rows in by_project.items():
                excess = len(rows) - cap
                if excess <= 0:
                    continue
                done_roots = sorted(
                    (r for r in rows if r["state"] == "done"),
                    key=lambda r: r["done_at"] or "")
                for row in done_roots[:excess]:
                    _archive_tree(conn, row,
                                  detail="cleanup: cap")
                    counts["cap_archived"] += 1
            horizon = now - timedelta(
                days=policy["archive_ttl_days"])
            stale_outbox = conn.execute(
                "SELECT id, at FROM outbox").fetchall()
            for orow in stale_outbox:
                if parse_iso(orow["at"]) < horizon:
                    conn.execute(
                        "DELETE FROM outbox WHERE id = ?",
                        (orow["id"],))
                    counts["outbox_pruned"] += 1
            _set_meta(conn, "last_cleanup_at",
                      now.isoformat())
            _set_meta(conn, "last_cleanup_counts",
                      json.dumps(counts, sort_keys=True))
    finally:
        conn.close()
    return counts


def purge_archived(db_path) -> int:
    """Manual control (§5.4): purge every archived row.
    Returns the row count; events remain."""
    return _purge_state(db_path, "archived",
                        "manual: purge-archived")


def purge_drafts(db_path) -> int:
    """Manual control (§5.4): purge every draft row."""
    return _purge_state(db_path, "draft",
                        "manual: purge-drafts")


def _purge_state(db_path, state, detail) -> int:
    conn = connect(db_path)
    try:
        with _tx(conn):
            rows = conn.execute(
                "SELECT * FROM messages WHERE state = ?",
                (state,)).fetchall()
            for row in rows:
                _purge_row(conn, row, detail=detail)
            return len(rows)
    finally:
        conn.close()


def store_stats(db_path) -> dict:
    """Counts by state + the last cleanup record (Settings →
    Workspace/Messages panels, spec §3/§5.3)."""
    conn = connect(db_path)
    try:
        last_at = _get_meta(conn, "last_cleanup_at")
        last_counts = _get_meta(conn, "last_cleanup_counts")
        outbox_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM outbox").fetchone()["n"]
        checkpoint = _get_meta(conn, "notify_checkpoint")
    finally:
        conn.close()
    return {
        "counts": counts_by_state(db_path),
        "last_cleanup_at": last_at,
        "last_cleanup_counts": json.loads(last_counts)
        if last_counts else None,
        "outbox_rows": outbox_rows,
        "notify_checkpoint": int(checkpoint)
        if checkpoint else 0,
    }
