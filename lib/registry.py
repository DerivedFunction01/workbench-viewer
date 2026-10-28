"""The per-project registry store: schema, mutations, history.

THE mutation path. The `wb` CLI and the companion server both
write exclusively through the functions in this module; the
server holds no SQL of its own. Modeled on the prototype's
calendar store discipline (subplan 09): schema via
`PRAGMA user_version`, WAL + busy_timeout on every connection,
ONE short BEGIN IMMEDIATE per mutation, per-row `version`
compare-and-swap — a stale version fails naming the newer
state, never a silent overwrite. History is append-only and
kept whole; "latest" is a derivation, not a destructive
update. Every function takes an explicit db path so tests run
on temp files.

Ruled vs derived (the split is the design): `status` changes
only through `set_status`/`supersede` carrying a ruling note.
Staleness is computed elsewhere (lib/staleness.py) and never
written here.
"""

import json
import re
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .util import (now_iso, sha256_file, state_sha256,
                   write_text)

STATUSES = ("canonical", "implemented", "deferred",
            "unexplored", "hard-gate", "abandoned")
KINDS = ("mockup", "prototype", "test-route",
         "component-variant", "storyboard", "artifact")
SOURCE_KINDS = ("entry-dir", "artifact-slug", "external")
TODO_STATUSES = ("todo", "doing", "done")
REVIEW_DISPOSITIONS = ("approve", "needs-changes", "stale")
ACTORS = ("cli", "viewer", "stale-check")

ENTRY_FIELDS = ("id", "title", "kind", "status", "gate",
                "ruling_text", "ruling_date", "spec_ref",
                "plan_ref", "source_kind", "source_ref",
                "entry_dir", "main_file", "content_sha256",
                "config_path", "state_schema", "state_json",
                "created_at", "updated_at", "status_changed_at",
                "last_verified_at", "archived", "archived_at",
                "superseded_by", "version")
SETTABLE_FIELDS = ("title", "gate", "ruling_text", "spec_ref",
                   "plan_ref", "config_path", "main_file",
                   "source_ref")
TODO_FIELDS = ("id", "title", "status", "notes", "link_kind",
               "link_ref", "created_at", "updated_at", "version")

SCHEMA_V1 = """
CREATE TABLE entries (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'mockup',
  status TEXT NOT NULL DEFAULT 'unexplored',
  gate TEXT,
  ruling_text TEXT,
  ruling_date TEXT,
  spec_ref TEXT,
  plan_ref TEXT,
  source_kind TEXT NOT NULL DEFAULT 'entry-dir',
  source_ref TEXT,
  entry_dir TEXT,
  main_file TEXT,
  content_sha256 TEXT,
  config_path TEXT,
  state_schema TEXT,
  state_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status_changed_at TEXT NOT NULL,
  last_verified_at TEXT,
  archived INTEGER NOT NULL DEFAULT 0,
  archived_at TEXT,
  superseded_by TEXT,
  version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_id TEXT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  verb TEXT NOT NULL,
  field TEXT,
  old TEXT,
  new TEXT,
  note TEXT
);
CREATE TABLE todos (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'todo',
  notes TEXT,
  link_kind TEXT,
  link_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE todo_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id TEXT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  verb TEXT NOT NULL,
  field TEXT,
  old TEXT,
  new TEXT,
  note TEXT
);
"""

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class RegistryError(Exception):
    """A mutation was refused, with a human-readable reason."""


class VersionConflict(RegistryError):
    def __init__(self, subject, expected, current):
        super().__init__(
            f"{subject}: version conflict — expected "
            f"{expected}, current version is {current}")
        self.current_version = current


class RulingRequired(RegistryError):
    pass


class UniformityRefused(RegistryError):
    def __init__(self, entry_id, findings):
        self.findings = findings
        detail = "; ".join(f["message"] for f in findings)
        super().__init__(
            f"{entry_id}: uniformity validators refuse this "
            f"transition: {detail}")


def check_slug(slug: str):
    if not _SLUG_RE.match(slug or ""):
        raise RegistryError(
            f"bad slug {slug!r}: lowercase letters, digits, "
            f"hyphens; must start with a letter or digit")


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


def entry_dict(row) -> dict:
    out = {k: row[k] for k in ENTRY_FIELDS}
    out["archived"] = bool(out["archived"])
    for key in ("state_schema", "state_json"):
        raw = out[key]
        out[key] = json.loads(raw) if raw else None
    return out


def get_entry(db_path, entry_id) -> dict:
    if not Path(db_path).is_file():
        raise RegistryError(
            f"registry not initialized: {db_path} "
            f"(wb init creates it)")
    conn = connect_readonly(db_path)
    try:
        return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def list_entries(db_path, *, archived=None) -> list:
    if not Path(db_path).is_file():
        return []  # an absent registry reads as an empty one
    conn = connect_readonly(db_path)
    try:
        sql = "SELECT * FROM entries"
        args = []
        if archived is not None:
            sql += " WHERE archived = ?"
            args.append(1 if archived else 0)
        sql += " ORDER BY id"
        return [entry_dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def history_for(db_path, entry_id) -> list:
    if not Path(db_path).is_file():
        return []
    conn = connect_readonly(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM history WHERE entry_id = ?"
            " ORDER BY id", (entry_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ----------------------------------------------------------------
# Entry mutations. `layout` is a (entries_dir, archive_dir) pair
# of Paths for the filesystem side; mutations that only touch
# the DB do not need it.
# ----------------------------------------------------------------

def _entry_dir_rel(layout, entry_id, archived, when=None):
    entries_dir, archive_dir = layout
    if archived:
        year = (when or now_iso())[:4]
        return archive_dir / year / entry_id
    return entries_dir / entry_id


def init_registry(db_path) -> Path:
    """Create the DB (and schema) if it does not exist."""
    conn = connect(db_path, create=True)
    conn.close()
    return Path(db_path)


def add_entry(db_path, layout, slug, *, title=None, kind="mockup",
              actor="cli", status="unexplored", ruling=None,
              source_kind="entry-dir", source_ref=None,
              main_file="mock.html", state_schema=None) -> dict:
    check_slug(slug)
    if kind not in KINDS:
        raise RegistryError(f"kind must be one of {KINDS}")
    if status not in STATUSES:
        raise RegistryError(f"status must be one of {STATUSES}")
    if status in ("canonical", "hard-gate") and not ruling:
        raise RulingRequired(
            f"status {status} requires a ruling note")
    if source_kind not in SOURCE_KINDS:
        raise RegistryError(
            f"source_kind must be one of {SOURCE_KINDS}")
    ts = now_iso()
    entry_dir = None
    abs_dir = None
    if source_kind == "entry-dir":
        entries_dir, _ = layout
        abs_dir = entries_dir / slug
        if abs_dir.exists():
            raise RegistryError(
                f"entry dir already exists: {abs_dir}")
        entry_dir = str(abs_dir)
    conn = connect(db_path, create=True)
    try:
        with _tx(conn):
            if conn.execute("SELECT 1 FROM entries WHERE id = ?",
                            (slug,)).fetchone():
                raise RegistryError(f"entry exists: {slug}")
            if abs_dir is not None:
                abs_dir.mkdir(parents=True)
                main = abs_dir / main_file
                if not main.exists():
                    write_text(
                        main,
                        "<!-- placeholder — replace with the"
                        " mock -->\n")
            sha = None
            if abs_dir is not None and (abs_dir / main_file).is_file():
                sha = sha256_file(abs_dir / main_file)
            conn.execute(
                "INSERT INTO entries (id, title, kind, status,"
                " ruling_text, ruling_date, source_kind,"
                " source_ref, entry_dir, main_file,"
                " content_sha256, state_schema, state_json,"
                " created_at, updated_at, status_changed_at,"
                " version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,"
                "?,?,?,1)",
                (slug, title or slug, kind, status,
                 ruling, ts[:10] if ruling else None,
                 source_kind, source_ref, entry_dir, main_file,
                 sha,
                 json.dumps(state_schema) if state_schema else None,
                 json.dumps({}) if state_schema else None,
                 ts, ts, ts))
            _append_history(conn, slug, actor, "add",
                            note=ruling)
            row = _row(conn, slug)
        return entry_dict(row)
    finally:
        conn.close()


def set_fields(db_path, entry_id, fields: dict, *, actor="cli",
               expect_version=None) -> dict:
    bad = set(fields) - set(SETTABLE_FIELDS)
    if bad:
        raise RegistryError(
            f"fields not settable via set: {sorted(bad)} "
            f"(settable: {', '.join(SETTABLE_FIELDS)})")
    if not fields:
        raise RegistryError("no fields given")
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, entry_id)
            _check_version(row, expect_version, entry_id)
            for key, value in fields.items():
                conn.execute(
                    f"UPDATE entries SET {key} = ? WHERE id = ?",
                    (value, entry_id))
                _append_history(conn, entry_id, actor, "set",
                                field=key, old=row[key], new=value)
            conn.execute(
                "UPDATE entries SET updated_at = ?,"
                " version = version + 1 WHERE id = ?",
                (now_iso(), entry_id))
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def set_status(db_path, entry_id, status, *, actor="cli",
               ruling=None, gate=None, expect_version=None,
               layout=None) -> dict:
    """A RULED transition. canonical requires a ruling note;
    hard-gate requires a ruling note AND a gate name. A
    transition to canonical runs the uniformity validators
    when a layout is available (the approve-path rule)."""
    if status not in STATUSES:
        raise RegistryError(f"status must be one of {STATUSES}")
    if status == "canonical" and not ruling:
        raise RulingRequired(
            "canonical requires a ruling note (--ruling)")
    if status == "hard-gate":
        if not ruling:
            raise RulingRequired(
                "hard-gate requires a ruling note (--ruling)")
        if not gate:
            raise RulingRequired(
                "hard-gate requires a gate name (--gate)")
    if status == "canonical" and layout is not None:
        from .validators import uniformity_findings_for
        conn = connect_readonly(db_path)
        try:
            entry = entry_dict(_row(conn, entry_id))
        finally:
            conn.close()
        findings = uniformity_findings_for(entry, layout)
        if findings:
            raise UniformityRefused(entry_id, findings)
    ts = now_iso()
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, entry_id)
            _check_version(row, expect_version, entry_id)
            conn.execute(
                "UPDATE entries SET status = ?, gate = ?,"
                " ruling_text = COALESCE(?, ruling_text),"
                " ruling_date = ?, status_changed_at = ?,"
                " updated_at = ?, version = version + 1"
                " WHERE id = ?",
                (status, gate if status == "hard-gate" else None,
                 ruling, ts[:10] if ruling else row["ruling_date"],
                 ts, ts, entry_id))
            _append_history(conn, entry_id, actor, "set-status",
                            field="status", old=row["status"],
                            new=status, note=ruling)
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def supersede(db_path, old_id, new_id, *, actor="cli",
              ruling=None) -> dict:
    ts = now_iso()
    conn = connect(db_path)
    try:
        with _tx(conn):
            old = _row(conn, old_id)
            _row(conn, new_id)
            if old["superseded_by"]:
                raise RegistryError(
                    f"{old_id} is already superseded by "
                    f"{old['superseded_by']}")
            conn.execute(
                "UPDATE entries SET status = 'abandoned',"
                " superseded_by = ?, status_changed_at = ?,"
                " updated_at = ?, version = version + 1"
                " WHERE id = ?",
                (new_id, ts, ts, old_id))
            _append_history(conn, old_id, actor, "supersede",
                            field="superseded_by", old=None,
                            new=new_id, note=ruling)
            _append_history(conn, new_id, actor, "supersede",
                            field="supersedes", old=None,
                            new=old_id, note=ruling)
            return entry_dict(_row(conn, old_id))
    finally:
        conn.close()


def verify_entry(db_path, entry_id, *, actor="cli",
                 accept_drift=False) -> dict:
    """Re-fingerprint the main file. If the hash drifted and
    the caller does not accept the drift, refuse (nothing is
    written). Otherwise stamp last_verified_at — the ONLY
    thing that clears a stale flag."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, entry_id)
            sha = row["content_sha256"]
            if row["entry_dir"] and row["main_file"]:
                main = Path(row["entry_dir"]) / row["main_file"]
                if main.is_file():
                    current = sha256_file(main)
                    if sha is not None and current != sha \
                            and not accept_drift:
                        raise RegistryError(
                            f"{entry_id}: content drifted "
                            f"(recorded {sha[:12]}…, current "
                            f"{current[:12]}…) — re-run with "
                            f"accept-drift to verify anyway")
                    sha = current
            ts = now_iso()
            conn.execute(
                "UPDATE entries SET content_sha256 = ?,"
                " last_verified_at = ?, updated_at = ?,"
                " version = version + 1 WHERE id = ?",
                (sha, ts, ts, entry_id))
            _append_history(conn, entry_id, actor, "verify",
                            field="last_verified_at",
                            old=row["last_verified_at"], new=ts,
                            note="drift accepted" if accept_drift
                            else None)
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def archive_entry(db_path, layout, entry_id, *, actor="cli",
                  resume=False) -> dict:
    """Folder move + registry update as one operation. If the
    DB half fails after the move, the row still points at the
    old path and `wb validate` reports it; --resume completes
    the row update without moving anything. Folder-less rows
    (entry_dir NULL — artifact-slug / external sources never
    had a folder) skip the move entirely and keep entry_dir
    NULL; stamping the archive path onto them would invent a
    folder that does not exist."""
    entries_dir, archive_dir = layout
    conn = connect(db_path)
    try:
        row = _row(conn, entry_id)
        if row["archived"] and not resume:
            raise RegistryError(f"{entry_id} is already archived")
        folderless = row["entry_dir"] is None
        src = None if folderless else Path(row["entry_dir"])
        dst = _entry_dir_rel(layout, entry_id, True)
        if not resume and not folderless:
            if not src.exists():
                raise RegistryError(
                    f"{entry_id}: entry dir missing: {src}")
            if dst.exists():
                raise RegistryError(
                    f"{entry_id}: archive target exists: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        new_dir = None if folderless else str(dst)
        ts = now_iso()
        with _tx(conn):
            row = _row(conn, entry_id)
            conn.execute(
                "UPDATE entries SET archived = 1,"
                " archived_at = ?, entry_dir = ?,"
                " updated_at = ?, version = version + 1"
                " WHERE id = ?",
                (ts, new_dir, ts, entry_id))
            _append_history(conn, entry_id, actor, "archive",
                            field="entry_dir",
                            old=row["entry_dir"], new=new_dir,
                            note="folder-less entry — no folder "
                                 "moved" if folderless else None)
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def unarchive_entry(db_path, layout, entry_id, *,
                    actor="cli") -> dict:
    entries_dir, archive_dir = layout
    conn = connect(db_path)
    try:
        row = _row(conn, entry_id)
        if not row["archived"]:
            raise RegistryError(f"{entry_id} is not archived")
        folderless = row["entry_dir"] is None
        if not folderless:
            src = Path(row["entry_dir"])
            dst = entries_dir / entry_id
            if not src.exists():
                raise RegistryError(
                    f"{entry_id}: archived dir missing: {src}")
            if dst.exists():
                raise RegistryError(
                    f"{entry_id}: entries target exists: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        new_dir = None if folderless else str(dst)
        ts = now_iso()
        with _tx(conn):
            row = _row(conn, entry_id)
            conn.execute(
                "UPDATE entries SET archived = 0,"
                " archived_at = NULL, entry_dir = ?,"
                " updated_at = ?, version = version + 1"
                " WHERE id = ?",
                (new_dir, ts, entry_id))
            _append_history(conn, entry_id, actor, "unarchive",
                            field="entry_dir",
                            old=row["entry_dir"], new=new_dir,
                            note="folder-less entry — no folder "
                                 "moved" if folderless else None)
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def set_state_schema(db_path, entry_id, schema, *,
                     actor="cli") -> dict:
    from .validators import check_state_schema
    problem = check_state_schema(schema)
    if problem:
        raise RegistryError(f"state schema: {problem}")
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, entry_id)
            conn.execute(
                "UPDATE entries SET state_schema = ?,"
                " state_json = COALESCE(state_json, '{}'),"
                " updated_at = ?, version = version + 1"
                " WHERE id = ?",
                (json.dumps(schema), now_iso(), entry_id))
            _append_history(conn, entry_id, actor,
                            "set-state-schema",
                            field="state_schema",
                            old=row["state_schema"],
                            new=json.dumps(schema))
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def set_state(db_path, entry_id, state: dict, *, actor="cli",
              expect_version=None) -> dict:
    """Edit the entry's current internal state (the mix-and-
    match toggles). Validated against the declared schema
    when one exists."""
    conn = connect(db_path)
    try:
        with _tx(conn):
            row = _row(conn, entry_id)
            _check_version(row, expect_version, entry_id)
            if row["state_schema"]:
                from .validators import check_state_values
                problem = check_state_values(
                    json.loads(row["state_schema"]), state)
                if problem:
                    raise RegistryError(f"state: {problem}")
            conn.execute(
                "UPDATE entries SET state_json = ?,"
                " updated_at = ?, version = version + 1"
                " WHERE id = ?",
                (json.dumps(state), now_iso(), entry_id))
            _append_history(conn, entry_id, actor, "set-state",
                            field="state_json",
                            old=row["state_json"],
                            new=json.dumps(state))
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def review_entry(db_path, entry_id, disposition, *,
                 actor="viewer", comment=None,
                 layout=None) -> dict:
    """A review disposition: approve / needs-changes / stale,
    with an optional comment — appended to the entry's history
    as its review log. Approve runs the uniformity validators
    and records the internal-state snapshot it covers."""
    if disposition not in REVIEW_DISPOSITIONS:
        raise RegistryError(
            f"disposition must be one of {REVIEW_DISPOSITIONS}")
    conn = connect(db_path)
    try:
        row = _row(conn, entry_id)
        entry = entry_dict(row)
    finally:
        conn.close()
    if disposition == "approve" and layout is not None:
        from .validators import uniformity_findings_for
        findings = uniformity_findings_for(entry, layout)
        if findings:
            raise UniformityRefused(entry_id, findings)
    payload = {"disposition": disposition}
    if comment:
        payload["comment"] = comment
    if disposition == "approve":
        state = entry.get("state_json") or {}
        payload["state"] = state
        payload["state_sha256"] = state_sha256(state)
    conn = connect(db_path)
    try:
        with _tx(conn):
            _append_history(conn, entry_id, actor, "review",
                            field="review",
                            new=json.dumps(payload,
                                           ensure_ascii=False),
                            note=comment)
            conn.execute(
                "UPDATE entries SET updated_at = ?"
                " WHERE id = ?", (now_iso(), entry_id))
            return entry_dict(_row(conn, entry_id))
    finally:
        conn.close()


def latest_review(db_path, entry_id):
    if not Path(db_path).is_file():
        return None
    conn = connect_readonly(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM history WHERE entry_id = ?"
            " AND verb = 'review' ORDER BY id DESC LIMIT 1",
            (entry_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        try:
            out["payload"] = json.loads(out["new"] or "{}")
        except json.JSONDecodeError:
            out["payload"] = {}
        return out
    finally:
        conn.close()


def record_stale_check(db_path, summary: str, *, actor="stale-check"):
    conn = connect(db_path)
    try:
        with _tx(conn):
            _append_history(conn, None, actor, "stale-check",
                            note=summary)
    finally:
        conn.close()


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


# ----------------------------------------------------------------
# Rebuild support (export.py parses the file; the writes live
# here so all SQL stays in this module).
# ----------------------------------------------------------------

def apply_export(db_path, data: dict):
    """Reconstruct a registry DB from an export document.
    Refuses to overwrite an existing non-empty DB."""
    db_path = Path(db_path)
    if db_path.exists():
        conn = connect_readonly(db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM entries").fetchone()[0]
        finally:
            conn.close()
        if n:
            raise RegistryError(
                f"{db_path} already holds {n} entries — "
                f"rebuild refuses to overwrite")
    conn = connect(db_path, create=True)
    try:
        with _tx(conn):
            for e in data.get("entries", []):
                row = dict(e)
                row.pop("derived", None)
                row["archived"] = 1 if row.get("archived") else 0
                for key in ("state_schema", "state_json"):
                    if isinstance(row.get(key), (dict, list)):
                        row[key] = json.dumps(row[key])
                cols = [k for k in ENTRY_FIELDS]
                conn.execute(
                    f"INSERT INTO entries"
                    f" ({', '.join(cols)}) VALUES"
                    f" ({', '.join('?' * len(cols))})",
                    [row.get(k) for k in cols])
            for h in data.get("history", []):
                conn.execute(
                    "INSERT INTO history (id, entry_id, ts,"
                    " actor, verb, field, old, new, note)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (h.get("id"), h.get("entry_id"), h.get("ts"),
                     h.get("actor"), h.get("verb"), h.get("field"),
                     h.get("old"), h.get("new"), h.get("note")))
            for t in data.get("todos", []):
                cols = list(TODO_FIELDS)
                conn.execute(
                    f"INSERT INTO todos"
                    f" ({', '.join(cols)}) VALUES"
                    f" ({', '.join('?' * len(cols))})",
                    [t.get(k) for k in cols])
            for ev in data.get("todo_events", []):
                conn.execute(
                    "INSERT INTO todo_events (id, todo_id, ts,"
                    " actor, verb, field, old, new, note)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (ev.get("id"), ev.get("todo_id"),
                     ev.get("ts"), ev.get("actor"),
                     ev.get("verb"), ev.get("field"),
                     ev.get("old"), ev.get("new"),
                     ev.get("note")))
    finally:
        conn.close()
