"""Registry store: connections, migration, transactions.

One slice of lib/registry (see the package docstring):
opening a registry DB (WAL + busy_timeout, PRAGMA
user_version migration), the one-transaction context,
and the row/history helpers every mutation builds on.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..util import now_iso
from .constants import (RegistryError, SCHEMA_V1,
                        VersionConflict)

def connect(db_path, *, busy_timeout_ms: int = 5000,
            create: bool = False) -> sqlite3.Connection:
    """Open a registry DB, migrating to the current schema.
    Read-only callers should prefer connect_readonly()."""
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


def connect_readonly(db_path, *, busy_timeout_ms: int = 250):
    """Open an existing DB read-only (server feeds). A locked
    DB raises sqlite3.OperationalError fast, so one project's
    lock degrades only its own feed."""
    db_path = Path(db_path)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True,
                           timeout=busy_timeout_ms / 1000.0,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    return conn


def _migrate(conn):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        conn.executescript(SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
    elif version != 1:
        raise RegistryError(
            f"unsupported registry schema version {version}")


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


def _append_history(conn, entry_id, actor, verb, field=None,
                    old=None, new=None, note=None):
    conn.execute(
        "INSERT INTO history (entry_id, ts, actor, verb, field,"
        " old, new, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (entry_id, now_iso(), actor, verb, field, old, new, note))


def _row(conn, entry_id) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM entries WHERE id = ?",
                       (entry_id,)).fetchone()
    if row is None:
        raise RegistryError(f"unknown entry: {entry_id}")
    return row


def _check_version(row, expect_version, subject):
    if expect_version is not None \
            and row["version"] != expect_version:
        raise VersionConflict(subject, expect_version,
                              row["version"])
