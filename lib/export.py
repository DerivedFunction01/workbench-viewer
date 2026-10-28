"""The generated registry.json: a canonical fold of the DB,
and the rebuild path back.

The DB is the truth; the export is a deterministic function
of it (sorted keys, canonical JSON) — the diffable review
surface and the viewer's serve input. It carries a
`_generated` header saying so. Derived staleness is computed
at export time and stamped with its computation time; ruled
content is a pure fold, so export → rebuild → export returns
the ruled sections byte-identical (the test proves it with a
fixed clock).

Every mutation caller (wb verbs, server endpoints) pairs its
lib/ mutation with regenerate() — regeneration is a pure
read-fold, safe to repeat, never a second source of truth.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import registry as reg
from .staleness import (entry_staleness, load_thresholds,
                        approval_coverage)
from .util import canonical_json, write_text


def build_export(db_path, *, project=None, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    thresholds = load_thresholds(db_path)
    conn = reg.connect_readonly(db_path)
    try:
        entries = [reg.entry_dict(r) for r in conn.execute(
            "SELECT * FROM entries ORDER BY id")]
        history = [dict(r) for r in conn.execute(
            "SELECT * FROM history ORDER BY id")]
        todos = [reg.todo_dict(r) for r in conn.execute(
            "SELECT * FROM todos ORDER BY id")]
        todo_events = [dict(r) for r in conn.execute(
            "SELECT * FROM todo_events ORDER BY id")]
    finally:
        conn.close()
    latest_reviews = {}
    for e in entries:
        row = None
        for h in reversed(history):
            if h["entry_id"] == e["id"] and h["verb"] == "review":
                row = dict(h)
                try:
                    row["payload"] = json.loads(h["new"] or "{}")
                except json.JSONDecodeError:
                    row["payload"] = {}
                break
        latest_reviews[e["id"]] = row
    for e in entries:
        e["derived"] = entry_staleness(
            e, now=now, thresholds=thresholds)
        e["approval"] = approval_coverage(
            e, latest_reviews[e["id"]])
    return {
        "_generated": {
            "by": "workbench-viewer lib (wb export)",
            "at": now.isoformat(),
            "warning": "GENERATED from registry.db — never "
                       "hand-edit. The DB is the truth; "
                       "rebuild it with `wb rebuild`.",
        },
        "project": project,
        "entries": entries,
        "history": history,
        "todos": todos,
        "todo_events": todo_events,
    }


def canonical_text(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True,
                      ensure_ascii=False) + "\n"


def regenerate(db_path, *, project=None) -> Path:
    """Fold the DB into registry.json beside it. Returns the
    export path."""
    db_path = Path(db_path)
    out = db_path.with_name("registry.json")
    data = build_export(db_path, project=project)
    tmp = out.with_suffix(".json.tmp")
    write_text(tmp, canonical_text(data))
    tmp.replace(out)
    return out


def ruled_sections(data: dict) -> dict:
    """The export minus everything time-derived — the part
    rebuild must preserve exactly."""
    entries = []
    for e in data.get("entries", []):
        e2 = dict(e)
        e2.pop("derived", None)
        e2.pop("approval", None)
        entries.append(e2)
    return {"entries": entries,
            "history": data.get("history", []),
            "todos": data.get("todos", []),
            "todo_events": data.get("todo_events", [])}


def rebuild(db_path, export_path) -> dict:
    """Reconstruct registry.db from an export file
    (fresh-clone / disaster path; also the losslessness
    proof). Refuses to overwrite a non-empty DB."""
    data = json.loads(Path(export_path).read_text(
        encoding="utf-8"))
    reg.apply_export(db_path, data)
    return data
