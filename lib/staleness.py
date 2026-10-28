"""Derived staleness: computed at read time, never stored
over a ruling.

Per entry: age_days, days_since_verified, drift (the main
file's current hash differs from the recorded fingerprint),
and a verdict from per-status thresholds. `implemented` and
`abandoned` entries never stale-flag — their truth lives in
production / history (subplan 09).

Thresholds: defaults below; a project may override them with
a `thresholds.json` beside its registry DB
({"unexplored": {"unverified_days": 30}, ...}).

This module is pure: same inputs → same report. Recording a
stale-check run in history is the caller's business (wb does
it via registry.record_stale_check; server GET feeds never
write).
"""

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .util import parse_iso, sha256_file, state_sha256

DEFAULT_THRESHOLDS = {
    "unexplored": {"unverified_days": 30, "label": "may be stale"},
    "canonical": {"unverified_days": 90,
                  "label": "verification due"},
    "deferred": {"unverified_days": 90,
                 "label": "verification due"},
    "hard-gate": {"unverified_days": 90,
                  "label": "verification due"},
}
NO_FLAG_STATUSES = ("implemented", "abandoned")


def load_thresholds(db_path) -> dict:
    thresholds = {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()}
    if db_path is not None:
        side = Path(db_path).with_name("thresholds.json")
        if side.is_file():
            try:
                overrides = json.loads(side.read_text())
                for status, vals in overrides.items():
                    if status in thresholds:
                        thresholds[status].update(vals)
            except (json.JSONDecodeError, OSError):
                pass  # a broken override file never breaks reads
    return thresholds


def _days_between(earlier_iso: str, now: datetime) -> float:
    return (now - parse_iso(earlier_iso)).total_seconds() / 86400.0


def entry_staleness(entry: dict, *, now=None,
                    thresholds=None) -> dict:
    """The derived block for one entry (export + viewer feed
    share exactly this shape)."""
    now = now or datetime.now(timezone.utc)
    thresholds = thresholds or DEFAULT_THRESHOLDS
    age_days = round(_days_between(entry["created_at"], now), 1)
    verified_ref = entry.get("last_verified_at") \
        or entry["created_at"]
    days_since_verified = round(
        _days_between(verified_ref, now), 1)
    drift = False
    if entry.get("entry_dir") and entry.get("main_file") \
            and entry.get("content_sha256"):
        main = Path(entry["entry_dir"]) / entry["main_file"]
        drift = main.is_file() \
            and sha256_file(main) != entry["content_sha256"]
    reasons = []
    if entry["status"] not in NO_FLAG_STATUSES:
        if drift:
            reasons.append("content drifted since last verify")
        rule = thresholds.get(entry["status"])
        if rule and days_since_verified > rule["unverified_days"]:
            if entry.get("last_verified_at"):
                reasons.append(
                    f"{rule['label']}: unverified for "
                    f"{int(days_since_verified)} days")
            else:
                reasons.append(
                    f"{rule['label']}: never verified, "
                    f"{int(age_days)} days old")
    return {
        "age_days": age_days,
        "days_since_verified": days_since_verified,
        "never_verified": entry.get("last_verified_at") is None,
        "drift": drift,
        "stale": bool(reasons),
        "reasons": reasons,
    }


def approval_coverage(entry: dict, latest_review_row) -> dict:
    """Does the latest approval cover the CURRENT internal
    state? Derived from the latest approve review row."""
    current_sha = state_sha256(entry.get("state_json") or {})
    out = {"approved": False, "covers_current": False,
           "approved_state_sha256": None,
           "current_state_sha256": current_sha,
           "approved_at": None}
    if latest_review_row is not None:
        payload = latest_review_row.get("payload") or {}
        if payload.get("disposition") == "approve":
            out["approved"] = True
            out["approved_at"] = latest_review_row.get("ts")
            out["approved_state_sha256"] = \
                payload.get("state_sha256")
            out["covers_current"] = \
                payload.get("state_sha256") == current_sha
    return out


def triage_reasons(entry: dict, derived: dict,
                   latest_review_row) -> list:
    """Why an entry sits in the viewer's triage lane (or []).
    The lane = unexplored, stale-flagged, or needs-changes
    whose comments are unaddressed (no later review)."""
    reasons = []
    if entry["status"] == "unexplored" and not entry["archived"]:
        reasons.append("unexplored — awaiting a ruling")
    if derived.get("stale"):
        reasons.append("stale: " + "; ".join(derived["reasons"]))
    if latest_review_row is not None:
        payload = latest_review_row.get("payload") or {}
        if payload.get("disposition") == "needs-changes":
            reasons.append("needs-changes — unaddressed")
    return reasons


def project_report(entries: list, latest_reviews: dict, *,
                   now=None, thresholds=None) -> dict:
    """The `wb stale` report for one project: per-entry derived
    blocks + a summary. latest_reviews maps entry_id → the
    latest review row (or None)."""
    now = now or datetime.now(timezone.utc)
    items = []
    flagged = 0
    for entry in entries:
        derived = entry_staleness(entry, now=now,
                                  thresholds=thresholds)
        if derived["stale"]:
            flagged += 1
        items.append({
            "id": entry["id"], "status": entry["status"],
            "archived": entry["archived"], **derived,
            "triage": triage_reasons(
                entry, derived, latest_reviews.get(entry["id"])),
        })
    return {"computed_at": now.isoformat(),
            "entries": items,
            "summary": {"total": len(items), "stale": flagged}}


# ----------------------------------------------------------------
# Work staleness: open plans, bundles, and todos (the
# stale-work-warnings plan). The same doctrine as entry
# staleness above — derived at read time, never stored,
# this module stays pure — with a different birthdate and
# one configurable threshold: an item's age is whole days
# from its birthdate; it flags only while it is OPEN work
# and its age is strictly greater than the threshold (an
# item exactly at the threshold is not yet stale). An item
# with no readable birthdate gets age_days None and never
# flags. Birthdates follow the repo's own conventions:
# a todo's `created` frontmatter date; a plan's or
# bundle's `<date>-` file/dir name prefix.
# ----------------------------------------------------------------

# Todo statuses that are still open work (bundles.TODO_
# STATUSES minus the terminal "done").
OPEN_TODO_STATUSES = ("todo", "doing", "blocked")
# parser.status_bucket's terminal set: todo | doing | done.
TERMINAL_PLAN_BUCKETS = ("done",)
_NAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


def _resolve_today(today):
    return today or datetime.now(timezone.utc).date()


def _parse_day(value):
    """A YYYY-MM-DD value → date, else None (missing or
    malformed dates are honest unknowns, never guesses)."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _name_birth_date(name):
    """The `<date>-` prefix of a plan file or bundle
    directory name → its birthdate, else None."""
    m = _NAME_DATE_RE.match(name or "")
    return _parse_day(m.group(1)) if m else None


def _work_derived(born, is_open, threshold_days, today):
    age_days = None if born is None else (today - born).days
    return {
        "age_days": age_days,
        "stale": bool(is_open and age_days is not None
                      and age_days > threshold_days),
    }


def todo_staleness(todo: dict, *, threshold_days: int,
                   today=None) -> dict:
    """The work-staleness block for one bundle todo: age
    from its `created` frontmatter date; only the open
    statuses (todo / doing / blocked) can flag — a done
    todo is history and is allowed to be old."""
    return _work_derived(
        _parse_day(todo.get("created")),
        todo.get("status") in OPEN_TODO_STATUSES,
        threshold_days, _resolve_today(today))


def _plan_birth_date(summary: dict):
    """A plan summary's birthdate: the `<date>-` prefix of
    its file name — or, for a bundle's plan.md, of the
    bundle directory name that parents it. A leading
    finished/ segment is filing location, not name."""
    parts = [p for p in (summary.get("path") or "").split("/")
             if p and p != "finished"]
    if not parts:
        return None
    name = parts[-1]
    if name == "plan.md" and len(parts) > 1:
        name = parts[-2]
    return _name_birth_date(name)


def _plan_is_open(summary: dict) -> bool:
    """A plan is open work while its status bucket is
    non-terminal (mirroring parser.status_bucket's set)
    and it is not archived."""
    return summary.get("status_bucket") \
        not in TERMINAL_PLAN_BUCKETS \
        and not summary.get("archived")


def plan_staleness(summary: dict, *, threshold_days: int,
                   today=None) -> dict:
    """The work-staleness block for one plan summary: age
    from the `<date>-` prefix of its file name; terminal
    buckets and archived plans never flag."""
    return _work_derived(
        _plan_birth_date(summary), _plan_is_open(summary),
        threshold_days, _resolve_today(today))


def bundle_staleness(bundle: dict, *, threshold_days: int,
                     today=None) -> dict:
    """The work-staleness block for one bundle row: age
    from the `<date>-` prefix of the bundle id.

    Openness rule: a bundle is open work while it is
    unarchived AND still carries open work of its own —
    an open todo (a status in OPEN_TODO_STATUSES; for
    valid todos exactly the set the bundle's served
    open_count counts) OR a plan whose bucket is
    non-terminal. A bundle whose todos are all done and
    whose plan is terminal (or absent) is finished work
    and never flags, however old; an archived bundle
    never flags."""
    plan = bundle.get("plan")
    plan_open = plan is not None and _plan_is_open(plan)
    todos_open = any(t.get("status") in OPEN_TODO_STATUSES
                     for t in bundle.get("todos", []))
    is_open = not bundle.get("archived") \
        and (plan_open or todos_open)
    return _work_derived(
        _name_birth_date(bundle.get("id")), is_open,
        threshold_days, _resolve_today(today))
