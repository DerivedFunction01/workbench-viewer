"""Repo registry + change history: the harness-owned state
for browsed repos (absorption plan, steps 5 and 7).

The registry is the tracking metadata for every repo the
census finds — display name, expected publication state,
pinned / ignored, notes — reconciled against discovery on
every serve. The history is a compact JSONL log: one line
per repo when a headline field changes (plus an hourly
heartbeat), from which the HEAD timeline and the dirty /
ahead streaks are derived at read time.

State lives with the viewer's own project-zero data, never
in the browsed repos, and is written only through here.
All writes ride the lib.util write seam or a builtin open()
inside an OSError guard (the write-denial hardening: a
failed state write degrades to a no-op, never a crash).
Stdlib only.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .util import now_iso, parse_iso, write_text

# ----------------------------------------------------------------
# Registry

ENTRY_FIELDS = ("display_name", "project", "expected",
                "pinned", "ignored", "notes",
                "first_seen", "last_seen", "root")

# The fields an update patch may touch. first_seen, last_seen,
# and root are reconcile-managed and never patched directly.
PATCH_FIELDS = {"display_name": str, "project": str,
                "expected": str, "pinned": bool,
                "ignored": bool, "notes": str}

EXPECTED_VALUES = ("published", "local_ok", "untracked")


def _empty_registry() -> dict:
    return {"repos": {}}


def load_registry(path) -> dict:
    """The registry at `path` as {"repos": {id: entry}}.
    A missing or unreadable file is an empty registry."""
    path = Path(path)
    if not path.is_file():
        return _empty_registry()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _empty_registry()
    if not isinstance(data, dict) \
            or not isinstance(data.get("repos"), dict):
        return _empty_registry()
    return data


def save_registry(path, data) -> None:
    """Persist the registry: write a temp sibling through
    the write seam, then replace — a reader never sees a
    half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    write_text(tmp, json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def _new_entry(repo_id: str, root, now: str) -> dict:
    return {
        "display_name": repo_id.rsplit("/", 1)[-1],
        "project": "", "expected": "untracked",
        "pinned": False, "ignored": False, "notes": "",
        "root": str(root) if root is not None else "",
        "first_seen": now, "last_seen": now,
    }


def reconcile(data, discovered, *, healthy_scan: bool,
              now: str):
    """Fold one census into the registry; returns
    (data, changed). `discovered` is the record list from
    lib.repos.discover_repos.

    New ids are added untracked; seen ids get their root
    and last_seen refreshed. An entry whose recorded root
    no longer exists on disk is pruned ONLY on a healthy
    scan (workspace readable, at least one repo discovered)
    — a transient scan failure can never wipe the registry.
    An entry whose root exists but was not discovered stays;
    the server surfaces it as missing.
    """
    repos = data.setdefault("repos", {})
    changed = False
    seen = set()
    for record in discovered:
        repo_id = record.get("id")
        if not repo_id:
            continue
        seen.add(repo_id)
        entry = repos.get(repo_id)
        if entry is None:
            repos[repo_id] = _new_entry(
                repo_id, record.get("root"), now)
            changed = True
            continue
        if entry.get("root") != record.get("root"):
            entry["root"] = record.get("root")
            changed = True
        if entry.get("last_seen") != now:
            entry["last_seen"] = now
            changed = True
    if healthy_scan:
        for repo_id in list(repos):
            if repo_id in seen:
                continue
            root = repos[repo_id].get("root")
            if root and not Path(root).exists():
                del repos[repo_id]
                changed = True
    return data, changed


def update_entry(data, repo_id, patch):
    """Apply a validated patch to one entry; returns
    (entry, None) or (None, error). The whole patch is
    validated before anything mutates, so a bad patch
    leaves the entry untouched."""
    entry = data.get("repos", {}).get(repo_id)
    if entry is None:
        return None, "unknown repo id"
    if not isinstance(patch, dict):
        return None, "patch must be an object"
    for key, value in patch.items():
        if key not in PATCH_FIELDS:
            return None, f"unknown field: {key}"
        want = PATCH_FIELDS[key]
        if not isinstance(value, want) \
                or isinstance(value, bool) != (want is bool):
            return None, f"bad type for {key}"
        if key == "expected" and value not in EXPECTED_VALUES:
            return None, \
                f"expected must be one of {EXPECTED_VALUES}"
    for key, value in patch.items():
        entry[key] = value
    return dict(entry), None


# ----------------------------------------------------------------
# History

# The fields whose change earns a history line.
HEADLINE_FIELDS = ("head", "branch", "ahead", "dirty_total",
                   "publication", "exposure_level")

HEARTBEAT = timedelta(hours=1)


def _as_datetime(now) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, str):
        return parse_iso(now)
    return now


def _summary_record(summary: dict, at: str) -> dict:
    dirty_counts = summary.get("dirty_counts") or {}
    exposure = summary.get("exposure") or {}
    return {
        "at": at,
        "repo": summary.get("id"),
        "head": summary.get("head_full")
        or summary.get("head"),
        "head_subject": summary.get("head_subject"),
        "branch": summary.get("branch"),
        "ahead": summary.get("ahead"),
        "publication": summary.get("publication"),
        "dirty_total": sum(dirty_counts.values()),
        "exposure_level": exposure.get("level"),
        "exposed_commits": exposure.get("commits"),
    }


def _read_records(path) -> list:
    """Every parseable history line, in file order. A
    missing file reads as no history."""
    path = Path(path)
    records = []
    if not path.is_file():
        return records
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return records
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records


def _append_line(path, line: str) -> bool:
    """Append one line via builtin open(); a denied write
    (OSError) degrades to False, never an exception."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return False
    return True


def record_history(path, summary, *, now=None) -> bool:
    """Append one compact record for a repo_summary-shaped
    dict when a headline field changed vs the repo's last
    record, or when that record is older than the hourly
    heartbeat. Returns whether a line was appended. A
    summary with no id or with an error records nothing.
    """
    repo_id = summary.get("id")
    if not repo_id or summary.get("error"):
        return False
    moment = _as_datetime(now)
    rec = _summary_record(summary, moment.isoformat())
    last = None
    for existing in _read_records(path):
        if existing.get("repo") == repo_id:
            last = existing
    if last is not None:
        same = all(last.get(f) == rec[f]
                   for f in HEADLINE_FIELDS)
        if same:
            try:
                age = moment - parse_iso(last["at"])
            except (KeyError, ValueError):
                age = HEARTBEAT
            if age < HEARTBEAT:
                return False
    return _append_line(path, json.dumps(rec) + "\n")


def _streak(records, field):
    """The start of the current uninterrupted run of truthy
    `field`, scanning newest-first; None when the newest
    record is not in the run (or there are no records)."""
    since = None
    for rec in reversed(records):
        if rec.get(field):
            since = rec.get("at")
        else:
            break
    return since


def history_for(path, repo_id) -> dict:
    """One repo's history: its records in file order, the
    HEAD timeline (consecutive same-head runs collapsed to
    their first sighting), and the current dirty / ahead
    streak starts."""
    records = [r for r in _read_records(path)
               if r.get("repo") == repo_id]
    timeline = []
    for rec in records:
        if not timeline or timeline[-1]["head"] != rec.get("head"):
            timeline.append({"ts": rec.get("at"),
                             "head": rec.get("head"),
                             "branch": rec.get("branch")})
    return {"records": records,
            "timeline": timeline,
            "dirty_since": _streak(records, "dirty_total"),
            "ahead_since": _streak(records, "ahead")}


# ----------------------------------------------------------------
# Import: the legacy viewer's state, mapped once at cutover.
# Its registry file is {"repos": {id: entry}} with the same
# entry fields; its history lines carry the same headline
# fields except the exposure level, re-derived here by the
# same rule lib.repos applies (publication + dirty + exposed
# counts decide the level).

def _import_entry(repo_id: str, raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    expected = raw.get("expected")
    if expected not in EXPECTED_VALUES:
        expected = "untracked"
    entry = _new_entry(repo_id, raw.get("root") or "",
                       raw.get("first_seen") or "")
    entry.update({
        "display_name": raw.get("display_name")
        or entry["display_name"],
        "project": raw.get("project") or "",
        "expected": expected,
        "pinned": raw.get("pinned") is True,
        "ignored": raw.get("ignored") is True,
        "notes": raw.get("notes") or "",
        "first_seen": raw.get("first_seen") or "",
        "last_seen": raw.get("last_seen") or "",
    })
    return entry


def import_registry(source_path) -> dict:
    """The legacy registry file at `source_path`, mapped to
    our shape. A missing or unreadable source imports as an
    empty registry."""
    raw = load_registry(source_path)
    return {"repos": {repo_id: _import_entry(repo_id, entry)
                      for repo_id, entry
                      in raw["repos"].items()}}


def _import_exposure_level(rec: dict):
    if rec.get("publication") == "local_only":
        return "local_only" if rec.get("exposed_commits") \
            else "backed_up"
    if rec.get("dirty_total"):
        return "uncommitted_work"
    if rec.get("exposed_commits"):
        return "unbacked_commits"
    return "backed_up"


def _import_record(raw: dict) -> dict:
    rec = {
        "at": raw.get("at"),
        "repo": raw.get("repo"),
        "head": raw.get("head"),
        "head_subject": raw.get("head_subject"),
        "branch": raw.get("branch"),
        "ahead": raw.get("ahead"),
        "publication": raw.get("publication"),
        "dirty_total": raw.get("dirty_total"),
        "exposed_commits": raw.get("exposed_commits"),
    }
    rec["exposure_level"] = _import_exposure_level(rec)
    return rec


def import_history(source_path, dest_path) -> int:
    """Append the legacy history lines at `source_path` to
    `dest_path`, mapped to our record shape. A record
    already present (same repo + ts + head) is skipped, so
    a repeated import appends nothing. Returns the number
    of lines appended.
    """
    existing = {(r.get("repo"), r.get("at"), r.get("head"))
                for r in _read_records(dest_path)}
    lines = []
    for raw in _read_records(source_path):
        if not raw.get("repo") or not raw.get("at"):
            continue
        rec = _import_record(raw)
        key = (rec["repo"], rec["at"], rec["head"])
        if key in existing:
            continue
        existing.add(key)
        lines.append(json.dumps(rec) + "\n")
    if not lines:
        return 0
    dest = Path(dest_path)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "a", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        return 0
    return len(lines)
