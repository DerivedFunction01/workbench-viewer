"""Registry todos: the DB todo store.

One slice of lib/registry (see the package docstring):
todos share the registry store but keep their own
tables; a todo may LINK to a plan/step/entry, that is
all — steps are never copied here.
"""

from pathlib import Path

from ..util import now_iso
from .constants import (TODO_FIELDS, TODO_STATUSES,
                        RegistryError, check_slug)
from .store import (_check_version, _tx, connect,
                    connect_readonly)

# ----------------------------------------------------------------
# Todos — same store, own tables. Steps are never copied here;
# a todo may LINK to a plan/step/entry, that is all.
# ----------------------------------------------------------------

def todo_dict(row) -> dict:
    return {k: row[k] for k in TODO_FIELDS}


def add_todo(db_path, todo_id, title, *, actor="cli", notes=None,
             link_kind=None, link_ref=None) -> dict:
    check_slug(todo_id)
    if link_kind is not None and link_kind not in (
            "plan", "step", "entry"):
        raise RegistryError("link_kind must be plan|step|entry")
    ts = now_iso()
    conn = connect(db_path, create=True)
    try:
        with _tx(conn):
            if conn.execute("SELECT 1 FROM todos WHERE id = ?",
                            (todo_id,)).fetchone():
                raise RegistryError(f"todo exists: {todo_id}")
            conn.execute(
                "INSERT INTO todos (id, title, status, notes,"
                " link_kind, link_ref, created_at, updated_at,"
                " version) VALUES (?,?,?,?,?,?,?,?,1)",
                (todo_id, title, "todo", notes, link_kind,
                 link_ref, ts, ts))
            conn.execute(
                "INSERT INTO todo_events (todo_id, ts, actor,"
                " verb, note) VALUES (?,?,?,?,?)",
                (todo_id, ts, actor, "add", None))
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?",
                (todo_id,)).fetchone()
            return todo_dict(row)
    finally:
        conn.close()


def list_todos(db_path, *, status=None) -> list:
    if not Path(db_path).is_file():
        return []  # an absent registry reads as an empty one
    conn = connect_readonly(db_path)
    try:
        sql = "SELECT * FROM todos"
        args = []
        if status:
            sql += " WHERE status = ?"
            args.append(status)
        sql += " ORDER BY id"
        return [todo_dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def set_todo_status(db_path, todo_id, status, *, actor="cli",
                    expect_version=None) -> dict:
    if status not in TODO_STATUSES:
        raise RegistryError(
            f"todo status must be one of {TODO_STATUSES}")
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?",
                (todo_id,)).fetchone()
            if row is None:
                raise RegistryError(f"unknown todo: {todo_id}")
            _check_version(row, expect_version, todo_id)
            conn.execute(
                "UPDATE todos SET status = ?, updated_at = ?,"
                " version = version + 1 WHERE id = ?",
                (status, now_iso(), todo_id))
            conn.execute(
                "INSERT INTO todo_events (todo_id, ts, actor,"
                " verb, field, old, new) VALUES (?,?,?,?,?,?,?)",
                (todo_id, now_iso(), actor, "set-status",
                 "status", row["status"], status))
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?",
                (todo_id,)).fetchone()
            return todo_dict(row)
    finally:
        conn.close()


def set_todo_fields(db_path, todo_id, fields: dict, *,
                    actor="cli", expect_version=None) -> dict:
    allowed = {"title", "notes", "link_kind", "link_ref"}
    bad = set(fields) - allowed
    if bad:
        raise RegistryError(f"todo fields not settable: {sorted(bad)}")
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?",
                (todo_id,)).fetchone()
            if row is None:
                raise RegistryError(f"unknown todo: {todo_id}")
            _check_version(row, expect_version, todo_id)
            for key, value in fields.items():
                conn.execute(
                    f"UPDATE todos SET {key} = ? WHERE id = ?",
                    (value, todo_id))
                conn.execute(
                    "INSERT INTO todo_events (todo_id, ts,"
                    " actor, verb, field, old, new)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (todo_id, now_iso(), actor, "set", key,
                     row[key], value))
            conn.execute(
                "UPDATE todos SET updated_at = ?,"
                " version = version + 1 WHERE id = ?",
                (now_iso(), todo_id))
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?",
                (todo_id,)).fetchone()
            return todo_dict(row)
    finally:
        conn.close()
