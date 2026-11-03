"""Message outbox reads, notify checkpoint, and cleanup.

One slice of lib/messages (see the package docstring):
the watcher poll (list_outbox — reading never consumes),
the server's notify checkpoint in the store meta, and
the §5.3 cleanup pass with its §5.4 manual purges and
store stats.
"""

import json
from datetime import datetime, timedelta, timezone

from ..util import parse_iso
from .constants import DEFAULT_POLICY
from .lifecycle import (_archive_tree, _purge_row,
                        counts_by_state)
from .store import _get_meta, _set_meta, _tx, connect

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
