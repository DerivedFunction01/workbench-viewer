"""Message store: connections, migration, row helpers.

One slice of lib/messages (see the package docstring):
opening the store (WAL + busy_timeout, the stepwise
user_version migration), the one-transaction context,
the append-only event write, the row fetch, the stored-
dict shape, and the meta key/value helpers.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..util import now_iso
from .constants import (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3,
                        SCHEMA_VERSION, MessageError)

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


def _get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?",
                       (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value ="
        " excluded.value", (key, value))
