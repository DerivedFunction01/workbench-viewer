"""Derived progress: computed at read time, never stored.

For every todo armed with a progress schedule (the
`progress_check` / `progress_armed` front-matter fields,
written only through lib/bundles.py), this module derives
the driver's view: the cadence interval, the last
checkpoint, the last activity (arming or checkpoint,
whichever is newer), how many whole check intervals have
passed with no activity, and the stall verdict — stalled
when the missed-check count reaches STALL_MISSED_CHECKS
(the progress-schedules plan's ruled threshold: 2).

A checkpoint is a todo-body line of the form

    progress-checkpoint: <ISO-8601 timestamp> — <text>

appended through `wb todo set --note` by whoever does
the work or runs a driver cycle; this module only reads
them. The todo file stays the progress record.

This module is pure: same inputs → same report. Acting
on a verdict (checkpointing, nudging, surfacing a
blocker) is the driver's business. The schedule that
runs the checks is the harness's own mechanism since
the owner's 2026-10-31 auto-create commission:
lib/progress_schedule.py writes a scheduler-registry
entry when a todo arms and deletes it when the todo
disarms, and each entry runs `wb progress-check` at
the todo's cadence (the older scheduling-is-a-platform-
concern doctrine survives only for the staleness
check's `print-schedule`).
"""

import re
from datetime import datetime, timezone

from .plans import bundles as bundle_parser
from .util import parse_iso

CHECKPOINT_PREFIX = "progress-checkpoint:"
_CHECKPOINT_RE = re.compile(r"^progress-checkpoint:\s*(\S+)")

# The ruled stall threshold: this many consecutive
# missed checks (a full cadence interval each with no
# checkpoint and no status move) declares the work
# stalled.
STALL_MISSED_CHECKS = 2


def _instant(value):
    """An ISO-8601 string → an aware datetime, or None.
    Malformed values are honest unknowns, never guesses;
    a naive value reads as UTC (the system's timestamps
    are UTC ISO-8601)."""
    if not value:
        return None
    try:
        parsed = parse_iso(str(value).strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def last_checkpoint(todo: dict):
    """The newest checkpoint timestamp in a todo's body,
    as an ISO string, or None when it has none. A line
    whose timestamp does not parse does not count as
    activity — body prose is not validated, so an
    unreadable checkpoint is simply not activity."""
    best = None
    for line in (todo.get("body") or "").splitlines():
        m = _CHECKPOINT_RE.match(line.strip())
        if not m:
            continue
        instant = _instant(m.group(1))
        if instant is not None \
                and (best is None or instant > best):
            best = instant
    return best.isoformat() if best is not None else None


def todo_progress(todo: dict, *, now=None):
    """The progress block for one todo, or None when the
    todo is not armed (no `progress_check` field)."""
    cadence = todo.get("progress_check")
    if not cadence:
        return None
    now = now or datetime.now(timezone.utc)
    interval = bundle_parser.parse_cadence(cadence)
    checkpoint = last_checkpoint(todo)
    activity = _instant(todo.get("progress_armed"))
    ck = _instant(checkpoint)
    if ck is not None \
            and (activity is None or ck > activity):
        activity = ck
    missed = None
    if interval is not None and activity is not None:
        elapsed = (now - activity).total_seconds()
        missed = max(
            0, int(elapsed // interval.total_seconds()))
    return {
        "id": todo.get("id"),
        "title": todo.get("title"),
        "status": todo.get("status"),
        "bundle": todo.get("bundle"),
        "archived": bool(todo.get("archived")),
        "path": todo.get("path"),
        "cadence": cadence,
        "interval_seconds": interval.total_seconds()
        if interval is not None else None,
        "armed_at": todo.get("progress_armed"),
        "last_checkpoint": checkpoint,
        "last_activity": activity.isoformat()
        if activity is not None else None,
        "missed_checks": missed,
        "stalled": missed is not None
        and missed >= STALL_MISSED_CHECKS,
    }


def project_progress(plans_dir, *, now=None) -> dict:
    """The `wb progress` report for one project: every
    armed todo across its bundles (active and finished)
    with its derived block, plus a summary. Unarmed
    todos are not the driver's business and never
    appear."""
    now = now or datetime.now(timezone.utc)
    armed = []
    for todo in bundle_parser.list_todos(plans_dir):
        block = todo_progress(todo, now=now)
        if block is not None:
            armed.append(block)
    return {
        "computed_at": now.isoformat(),
        "armed": armed,
        "summary": {
            "armed": len(armed),
            "stalled": sum(1 for b in armed if b["stalled"]),
        },
    }
