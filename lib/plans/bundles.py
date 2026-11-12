"""The bundle parser: `.plans/` directories (bundles),
their plan.md files, and their todo files → structured
results. Part of the plans parser family (lib/plans/);
the plan.md inside a bundle is parsed by the house plan
parser (parser.py) — this module adds the bundle/todo
layer from the live-work-tracking spec §3.

Layout (§3.1): a bundle is a directory `<date>-<slug>`
under .plans/ holding an optional plan.md and a todos/
directory of one file per todo. Legacy flat plans
(top-level *.md, plus finished/*.md) remain first-class:
list_bundles() enumerates them as one-file bundles.
finished/ holds whole bundles (and flat plans) that are
done — they enumerate with archived=True.

A directory under .plans/ counts as a bundle only when it
carries bundle content (a plan.md or a todos/ dir), so
plain working directories stay invisible, as before.

Todo front-matter (§3.2) is the contract. Validation is
honest-feed style: a todo with missing/invalid
front-matter still appears in the result, flagged
valid=False with structured `errors` on THAT item (and
aggregated on its bundle) — never a silent skip, never
a crash of other items. Unknown front-matter fields are
preserved in `fields` (lossless, like the plan parser).

A flat plan whose declared Status contradicts its filing
location — `complete` while still active, or anything but
`complete`/`superseded` under finished/ — carries the
same treatment: one `closeout:` bundle error naming the
fix (the plan syntax standard's Closeout section, enforced
by `_closeout_error`). Bundle directories are not plan
files and are never closeout-checked.
"""

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .parser import declared_status, parse_plan, status_bucket

TODO_STATUSES = ("todo", "doing", "blocked", "done")
REQUIRED_TODO_FIELDS = ("id", "title", "status",
                        "created", "updated")
TODO_ID_RE = re.compile(r"^t-[0-9A-HJKMNP-TV-Z]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BUNDLE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")
_CADENCE_RE = re.compile(r"^(\d+)([mh])$")


def _valid_date(value: str) -> bool:
    if not _DATE_RE.match(value or ""):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def parse_cadence(value):
    """A progress-check cadence (`30m`, `2h`) → a
    timedelta, or None when the value is not a cadence.
    The one definition of the format: the writers refuse
    anything else, the parser flags it, and the progress
    derivation consumes exactly this."""
    m = _CADENCE_RE.match((value or "").strip())
    if not m or int(m.group(1)) < 1:
        return None
    amount = int(m.group(1))
    if m.group(2) == "h":
        return timedelta(hours=amount)
    return timedelta(minutes=amount)


# The progress_check field's two non-cadence states. A
# todo whose progress_check is PROGRESS_OPT_OUT has
# explicitly opted out of monitoring (the writer's
# --no-progress): no schedule, no stall derivation, and
# the doctor stays silent about it. A doing todo that
# declares neither a cadence nor the opt-out is armed
# by the writer at PROGRESS_DEFAULT_CADENCE on the
# doing move — arming is automatic, so monitored work
# never depends on someone remembering a flag. The
# default is 15m (the owner's 2026-11-03 ruling: the
# shorter interval catches dead or erroring work a lot
# earlier); an explicit cadence remains the override,
# and no cadence runs longer than 30m by convention.
PROGRESS_OPT_OUT = "off"
PROGRESS_DEFAULT_CADENCE = "15m"


# The goal contract (goal-prompt contract plan,
# 2026-11-12): a programme's standing bundle may carry
# a contract — contract.md in the bundle directory —
# as a field block. Four fields are filled per
# programme (Programme, Objective, Complete when,
# Work record); the other three are the template's
# verbatim clauses everywhere — handwritten variants
# are a defect. The template text below is the plan's
# fixed text; the starter repo's supervision rules
# carry the same text as the generic home. The doing
# transition's arming gate (lib/bundles.py) verifies
# completeness on any bundle carrying a contract and
# refuses to arm an incomplete record, naming the
# empty field.
CONTRACT_FILE = "contract.md"
CONTRACT_FIELDS = (
    "Programme", "Objective", "Complete when",
    "Blocked only when", "Work record", "Cadence",
    "Continuation")
CONTRACT_FILLED_FIELDS = (
    "Programme", "Objective", "Complete when",
    "Work record")
CONTRACT_FIXED = {
    "Blocked only when": (
        "a named hard stop, a genuine owner-only "
        "decision, or a verified external blocker — "
        "the claim carries its cited basis with its "
        "time and a verification stamp; an uncited or "
        "unverified claim is void, the work resumes "
        "under its standing authorization, and the "
        "claim is surfaced as a defect; sequencing "
        "choices, agent-clearable waits, and matters "
        "already decided are never blocked states"),
    "Cadence": (
        "conforming progress-checkpoints every 15 "
        "minutes while doing; two missed intervals "
        "is a stall"),
    "Continuation": (
        "a step landing staffs the next in the same "
        "movement; a turn ends only with work in "
        "flight, a complete report, or a blocked "
        "report satisfying the clause; attention "
        "dispatches continuation pings against this "
        "contract and an acknowledgement does not "
        "clear a stall — measured movement does"),
}

_CONTRACT_LINE_RE = re.compile(
    r"^-\s+(" + "|".join(CONTRACT_FIELDS) + r"):\s*(.*)$")


def render_contract(programme, objective, complete_when,
                    work_record) -> str:
    """The contract block as file text: the four
    per-programme fields filled, the three fixed
    clauses verbatim from CONTRACT_FIXED."""
    filled = {
        "Programme": programme,
        "Objective": objective,
        "Complete when": complete_when,
        "Work record": work_record,
    }
    lines = [f"# Goal contract — {programme}", ""]
    for field in CONTRACT_FIELDS:
        value = filled.get(field) \
            or CONTRACT_FIXED[field]
        lines.append(f"- {field}: {value}")
    return "\n".join(lines) + "\n"


def parse_contract(bundle_dir):
    """A bundle's goal contract, or None when the
    bundle carries none. Returns the field values
    plus the completeness verdict the arming gate
    consumes: `missing` names every field that is
    absent or empty, in template order."""
    path = Path(bundle_dir) / CONTRACT_FILE
    if not path.is_file():
        return None
    fields = {}
    for line in path.read_text(
            encoding="utf-8").splitlines():
        m = _CONTRACT_LINE_RE.match(line.strip())
        if m:
            fields[m.group(1)] = m.group(2).strip()
    missing = [f for f in CONTRACT_FIELDS
               if not fields.get(f)]
    return {
        "fields": fields,
        "missing": missing,
        "complete": not missing,
    }


def _valid_instant(value: str) -> bool:
    try:
        datetime.fromisoformat(
            (value or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def bundle_slug(bundle_id: str) -> str:
    """The slug part of a bundle id: the directory name
    minus its `<date>-` prefix (the whole name when it
    carries no date prefix)."""
    m = _BUNDLE_DATE_RE.match(bundle_id or "")
    return m.group(1) if m else (bundle_id or "")


def split_front_matter(text: str):
    """Split a todo file into (fields, body, fm_lines).
    fields maps key → raw string value (first colon splits;
    unknown keys preserved). Returns (None, text, []) when
    there is no front-matter block at all."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text, []
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text, []
    fields = {}
    fm_lines = lines[1:end]
    for line in fm_lines:
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1:])
    return fields, body, fm_lines


def parse_todo(text: str, *, path: str = "") -> dict:
    """Parse + validate one todo file (§3.2). Always
    returns a result dict; problems land in `errors` and
    flip `valid` to False — the raw fields and body are
    still carried, so nothing is silently dropped."""
    errors = []
    fields, body, _ = split_front_matter(text)
    if fields is None:
        fields = {}
        body = text
        errors.append("missing front-matter block")
    for key in REQUIRED_TODO_FIELDS:
        if not fields.get(key):
            errors.append(f"missing required field: {key}")
    todo_id = fields.get("id") or None
    if todo_id and not TODO_ID_RE.match(todo_id):
        errors.append(
            f"invalid id {todo_id!r}: expected the "
            f"generator form t-<timestamp-ordered token>")
    status = fields.get("status") or None
    if status and status not in TODO_STATUSES:
        errors.append(
            f"invalid status {status!r}: must be one of "
            f"{', '.join(TODO_STATUSES)}")
    for key in ("created", "updated"):
        if fields.get(key) and not _valid_date(fields[key]):
            errors.append(
                f"invalid {key} {fields[key]!r}: "
                f"expected YYYY-MM-DD")
    plan_step = None
    if fields.get("plan_step"):
        try:
            plan_step = int(fields["plan_step"])
            if plan_step < 1:
                raise ValueError
        except ValueError:
            errors.append(
                f"invalid plan_step {fields['plan_step']!r}: "
                f"expected a positive integer")
            plan_step = None
    progress_check = fields.get("progress_check") or None
    if progress_check is not None \
            and progress_check != PROGRESS_OPT_OUT \
            and parse_cadence(progress_check) is None:
        errors.append(
            f"invalid progress_check "
            f"{progress_check!r}: expected a cadence "
            f"like 30m or 2h, or off")
    progress_armed = fields.get("progress_armed") or None
    if progress_armed is not None \
            and not _valid_instant(progress_armed):
        errors.append(
            f"invalid progress_armed "
            f"{progress_armed!r}: expected an ISO-8601 "
            f"timestamp")
    if progress_check == PROGRESS_OPT_OUT \
            and progress_armed is not None:
        errors.append(
            "progress_armed is set while progress_check "
            "is off: an opted-out todo carries no "
            "armed stamp")
    return {
        "id": todo_id,
        "title": fields.get("title") or None,
        "status": status,
        "feature": fields.get("feature") or None,
        "plan": fields.get("plan") or None,
        "plan_step": plan_step,
        "worktree": fields.get("worktree") or None,
        "progress_check": progress_check,
        "progress_armed": progress_armed,
        "created": fields.get("created") or None,
        "updated": fields.get("updated") or None,
        "fields": fields,
        "body": body.strip("\n"),
        "markdown": text,
        "path": path,
        "valid": not errors,
        "errors": errors,
    }


def _parse_todo_path(todo_path: Path, rel: str) -> dict:
    try:
        text = todo_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return {
            "id": None, "title": None, "status": None,
            "feature": None, "plan": None, "plan_step": None,
            "worktree": None, "progress_check": None,
            "progress_armed": None, "created": None,
            "updated": None, "fields": {}, "body": "",
            "markdown": "", "path": rel, "valid": False,
            "errors": [f"unreadable todo file: {e}"],
        }
    return parse_todo(text, path=rel)


def _plan_summary(plan_path: Path, rel: str,
                  archived: bool) -> dict:
    doc = parse_plan(plan_path.read_text(encoding="utf-8"),
                     path=rel)
    return {
        "path": rel,
        "title": doc["title"],
        "status_raw": doc["status_raw"],
        "status_bucket": status_bucket(doc["status_raw"],
                                       archived=archived),
        "conforming": doc["conforming"],
        "step_count": doc["step_count"],
        "questions": doc["questions"],
        "subplans": doc["subplans"],
        "subplans_count": len(doc["subplans"]),
        "mermaid_count": doc["mermaid_count"],
        "archived": archived,
        "modified": plan_path.stat().st_mtime,
        "feature": doc["fields"].get("Feature")
        or doc["fields"].get("feature"),
    }


def _is_bundle_dir(d: Path) -> bool:
    return (d / "plan.md").is_file() or (d / "todos").is_dir()


def _read_bundle(bundle_dir: Path, rel_prefix: str,
                 archived: bool) -> dict:
    bundle_id = bundle_dir.name
    plan = None
    plan_file = bundle_dir / "plan.md"
    if plan_file.is_file():
        plan = _plan_summary(
            plan_file, f"{rel_prefix}plan.md", archived)
    todos = []
    errors = []
    todos_dir = bundle_dir / "todos"
    if todos_dir.is_dir():
        for f in sorted(todos_dir.glob("*.md")):
            rel = f"{rel_prefix}todos/{f.name}"
            todo = _parse_todo_path(f, rel)
            todo["bundle"] = bundle_id
            todo["archived"] = archived
            todos.append(todo)
            for err in todo["errors"]:
                errors.append({"path": rel, "error": err})
    feature = plan["feature"] if plan else None
    if feature is None:
        todo_features = {t["feature"] for t in todos
                         if t["feature"]}
        if len(todo_features) == 1:
            feature = next(iter(todo_features))
    return {
        "kind": "bundle",
        "id": bundle_id,
        "slug": bundle_slug(bundle_id),
        "path": rel_prefix.rstrip("/"),
        "archived": archived,
        "feature": feature,
        "plan": plan,
        "contract": parse_contract(bundle_dir),
        "todos": todos,
        "errors": errors,
        "todo_count": len(todos),
        "open_count": sum(
            1 for t in todos
            if t["valid"] and t["status"] != "done"),
    }


def _closeout_error(status_raw, archived: bool):
    """The plan-closeout contradiction (plan syntax
    standard, Closeout section): a plan file's declared
    Status and its filing location must agree. Returns
    the error text naming the fix, or None when they
    agree — and None when the plan declares nothing
    (no Status header: no flag; the degraded treatment
    covers it). Plan files only: bundle directories
    carry no plan file, and their state rides their
    todos, so they are never checked here."""
    declared = declared_status(status_raw)
    if declared is None:
        return None
    if not archived and declared == "complete":
        return ("closeout: Status declares complete, "
                "but the plan is filed under .plans/ — "
                "close it out by moving it to "
                ".plans/finished/")
    if archived and declared not in ("complete",
                                     "superseded"):
        return (f"closeout: Status declares {declared}, "
                f"but the plan is filed under "
                f".plans/finished/ — a finished plan must "
                f"declare complete or superseded: fix "
                f"the Status line, or move it back to "
                f".plans/")
    return None


def _flat_bundle(plan_path: Path, rel: str,
                 archived: bool) -> dict:
    plan = _plan_summary(plan_path, rel, archived)
    errors = []
    closeout = _closeout_error(plan["status_raw"], archived)
    if closeout is not None:
        errors.append({"path": rel, "error": closeout})
    return {
        "kind": "flat-plan",
        "id": plan_path.name,
        "slug": plan_path.stem,
        "path": rel,
        "archived": archived,
        "feature": plan["feature"],
        "plan": plan,
        "contract": None,
        "todos": [],
        "errors": errors,
        "todo_count": 0,
        "open_count": 0,
    }


def list_bundles(plans_dir) -> list:
    """Enumerate a repo's .plans/: bundle directories AND
    legacy flat plans, active and finished/. Sorted by
    path for stable output. A missing plans dir reads as
    an empty list."""
    plans_dir = Path(plans_dir)
    out = []
    if not plans_dir.is_dir():
        return out
    for f in sorted(plans_dir.glob("*.md")):
        out.append(_flat_bundle(f, f.name, False))
    for d in sorted(plans_dir.iterdir()):
        if d.is_dir() and d.name != "finished" \
                and _is_bundle_dir(d):
            out.append(_read_bundle(d, f"{d.name}/", False))
    finished = plans_dir / "finished"
    if finished.is_dir():
        for f in sorted(finished.glob("*.md")):
            out.append(_flat_bundle(
                f, f"finished/{f.name}", True))
        for d in sorted(finished.iterdir()):
            if d.is_dir() and _is_bundle_dir(d):
                out.append(_read_bundle(
                    d, f"finished/{d.name}/", True))
    return out


def list_todos(plans_dir, *, bundle=None, status=None) -> list:
    """Every todo across a repo's bundles (the same read
    the server will call — no second read path). `bundle`
    filters by bundle id or slug; `status` by todo status.
    Invalid todos are included, flagged, unless a status
    filter excludes them."""
    out = []
    for b in list_bundles(plans_dir):
        if bundle is not None and bundle not in (b["id"],
                                                 b["slug"]):
            continue
        for t in b["todos"]:
            if status is not None and t["status"] != status:
                continue
            out.append(t)
    return out


def all_todo_ids(plans_dir) -> set:
    """Every todo id in the repo (valid or not) — the
    collision-check set for id generation (§3.4)."""
    ids = set()
    for b in list_bundles(plans_dir):
        for t in b["todos"]:
            if t["id"]:
                ids.add(t["id"])
    return ids


# Terminal plan words for the attribution derivation: a plan
# declaring one of these is finished work; the entries made
# for it carry that disposition as their cleanup signal.
PLAN_TERMINAL_WORDS = ("complete", "completed", "done",
                       "finished", "implemented",
                       "superseded")


def resolve_plan_link(plans_dir, plan_ref, *, bundles=None):
    """Resolve an entry's plan_ref against a project's plans
    dir — the attribution anchor. Candidates, in order: the
    ref as given, minus a trailing .md, minus a bundle's
    trailing /plan.md. Matched against each bundle's id,
    slug, and plan path, active and finished alike.

    Returns {"ref", "found", "bundle_id", "path", "archived",
    "status", "terminal"}: status is the plan's declared
    status word (declared_status), terminal True when that
    word is a finished-work word OR the plan sits in
    finished/. found False — with the rest None/False — when
    no plan matches: a broken anchor, never a disposition."""
    miss = {"ref": plan_ref, "found": False,
            "bundle_id": None, "path": None, "archived": False,
            "status": None, "terminal": False}
    if not plan_ref or plans_dir is None:
        return miss
    ref = str(plan_ref).strip()
    candidates = {ref}
    if ref.endswith(".md"):
        candidates.add(ref[:-3])
    if ref.endswith("/plan"):
        candidates.add(ref[:-5])
    for b in (bundles if bundles is not None
              else list_bundles(plans_dir)):
        plan = b.get("plan")
        keys = {b.get("id"), b.get("slug")}
        if plan:
            keys.add(plan.get("path"))
            if plan.get("path", "").endswith(".md"):
                keys.add(plan["path"][:-3])
        if not candidates & {k for k in keys if k}:
            continue
        status = declared_status(
            plan["status_raw"]) if plan else None
        return {
            "ref": plan_ref, "found": True,
            "bundle_id": b.get("id"),
            "path": plan.get("path") if plan else None,
            "archived": bool(b.get("archived")),
            "status": status,
            "terminal": bool(b.get("archived"))
            or status in PLAN_TERMINAL_WORDS,
        }
    return miss
