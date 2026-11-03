"""Registry entries: reads, mutations, and history.

One slice of lib/registry (see the package docstring):
the entry CRUD path — add/set/set-status/supersede/
verify/archive, entry state and reviews — plus the
export-fold reconstruction (apply_export) whose writes
live here so all SQL stays in the registry package.
"""

import json
import shutil
from pathlib import Path

from ..util import (now_iso, sha256_file, state_sha256,
                   write_text)
from .constants import (ENTRY_FIELDS, KINDS,
                        REVIEW_DISPOSITIONS,
                        SETTABLE_FIELDS, SOURCE_KINDS,
                        STATUSES, TODO_FIELDS,
                        RegistryError, RulingRequired,
                        UniformityRefused, check_slug)
from .store import (_append_history, _check_version,
                    _row, _tx, connect, connect_readonly)

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
        from ..validators import uniformity_findings_for
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
    from ..validators import check_state_schema
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
                from ..validators import check_state_values
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
        from ..validators import uniformity_findings_for
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
