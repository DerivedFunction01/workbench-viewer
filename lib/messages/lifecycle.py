"""Message lifecycle: create, transitions, and reads.

One slice of lib/messages (see the package docstring):
the state machine's mutation path (create/update/send/
pickup/done/archive/purge) and the plain reads. The
event and outbox writes go through the package
namespace (lib.messages._event / ._outbox) so the
atomicity contract stays patch-visible in tests: a
failed event or outbox write must roll the whole
transition back.
"""

import json
from datetime import datetime, timedelta, timezone

from .. import messages as _pkg
from ..util import now_iso, parse_iso
from .constants import (ANCHOR_TYPES, AUTHORS, STATES,
                        TRANSITIONS, MessageError)
from .selection import _validate_selection
from .store import _row, _tx, connect, message_dict

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
    _pkg._event(conn, row["id"], event, detail)
    if target == "sent":
        _pkg._outbox(conn, row)


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
            _pkg._event(conn, mid, "created",
                   "reply" if parent_id is not None else None)
            if send:
                _pkg._event(conn, mid, "sent")
                # Born sent: the outbox row lands in this
                # same transaction (§15.1).
                _pkg._outbox(conn, _row(conn, mid))
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
            _pkg._event(conn, message_id, "edited")
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
    _pkg._event(conn, row["id"], "purged", detail)
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
