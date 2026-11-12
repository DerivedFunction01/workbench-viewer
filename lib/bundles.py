"""Bundle + file-todo mutations (live-work-tracking
spec §3.4): the ONE write path for bundles and todo
files. The `wb` CLI calls these functions; the server
will call the same ones — no second path, and file
writes never happen anywhere else in lib/ for todos.

Reads live in the plans parser family
(lib/plans/bundles.py) — writers scan through it, so a
write can never disagree with what the feeds will read.

Front-matter is written in the §3.2 field order, with
optional fields (feature / plan / plan_step / worktree)
present only when set — present-or-omitted exactly.
"""

import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from .progress import attention as attention_mod
from .progress import schedule as progress_schedule_mod
from . import registry as reg
from .plans import bundles as bundle_parser
from .plans.parser import parse_plan
from .util import now_iso, write_text

TODO_STATUSES = bundle_parser.TODO_STATUSES

# Statuses that end a todo's active life: a move to one
# of these disarms its progress schedule (the schedule
# stops at done/blocked, per the progress-schedules
# plan's rulings). `done` is also the parser's only
# terminal status — blocked is resumable work, but its
# schedule has already surfaced the blocker and stopped.
PROGRESS_STOP_STATUSES = ("done", "blocked")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class BundleError(Exception):
    """A bundle/todo mutation was refused, with a reason."""


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _check_slug(slug: str, what: str = "slug"):
    if not _SLUG_RE.match(slug or ""):
        raise BundleError(
            f"bad {what} {slug!r}: lowercase letters, "
            f"digits, hyphens; must start with a letter "
            f"or digit")


# ----------------------------------------------------------------
# Todo ids: ULID-shaped — `t-` + 26 Crockford chars whose
# high bits are the creation millisecond, so ids sort in
# creation order (§3.2's form, §3.4's timestamp-ordered
# rule). Monotonic within the process: a same-millisecond
# id increments the random part instead of re-rolling.
# ----------------------------------------------------------------

_last_id_value = 0


def _new_id_value() -> int:
    global _last_id_value
    ms = int(time.time() * 1000)
    value = (ms << 80) | secrets.randbits(80)
    if value <= _last_id_value:
        value = _last_id_value + 1
    _last_id_value = value
    return value


def generate_todo_id(existing_ids) -> str:
    """A fresh repo-unique todo id, collision-checked
    against `existing_ids` (the whole repo's set)."""
    while True:
        value = _new_id_value()
        chars = []
        v = value
        for _ in range(26):
            chars.append(_CROCKFORD[v & 31])
            v >>= 5
        todo_id = "t-" + "".join(reversed(chars))
        if todo_id not in existing_ids:
            return todo_id


def slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-",
                  (title or "").lower()).strip("-")
    return slug[:50].strip("-") or "todo"


# ----------------------------------------------------------------
# Bundle resolution
# ----------------------------------------------------------------

def _bundle_dirs(plans_dir: Path, *, archived: bool):
    base = plans_dir / "finished" if archived else plans_dir
    if not base.is_dir():
        return
    for d in sorted(base.iterdir()):
        if d.is_dir() and (archived or d.name != "finished"):
            yield d


def find_bundle_dir(plans_dir, bundle_ref: str, *,
                    archived: bool = False) -> Path | None:
    """Resolve a bundle reference (full bundle id, slug,
    or id with a finished/ prefix) to its directory."""
    plans_dir = Path(plans_dir)
    ref = (bundle_ref or "").removesuffix("/")
    if ref.startswith("finished/"):
        archived = True
        ref = ref[len("finished/"):]
    for d in _bundle_dirs(plans_dir, archived=archived):
        if d.name == ref \
                or bundle_parser.bundle_slug(d.name) == ref:
            return d
    return None


def _all_bundle_dirs(plans_dir: Path):
    yield from _bundle_dirs(plans_dir, archived=False)
    yield from _bundle_dirs(plans_dir, archived=True)


# ----------------------------------------------------------------
# Bundle creation (§3.4)
# ----------------------------------------------------------------

def _plan_skeleton(slug: str, *, feature=None,
                   today: str) -> str:
    title = slug.replace("-", " ").title()
    lines = [
        f"# {title}",
        "",
        "Status: draft",
        f"Created: {today}",
    ]
    if feature:
        lines.append(f"Feature: {feature}")
    lines += ["", "## Steps", ""]
    return "\n".join(lines)


def create_bundle(plans_dir, slug, *, plan: bool = False,
                  feature=None, today: str = None) -> dict:
    """Create `.plans/<date>-<slug>/` (+ todos/, +
    plan.md skeleton with the house header when
    plan=True). Refuses when the slug already exists as
    a bundle (active or finished, any date)."""
    _check_slug(slug)
    today = today or _today()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", today):
        raise BundleError(f"bad date {today!r}: YYYY-MM-DD")
    plans_dir = Path(plans_dir)
    for d in _all_bundle_dirs(plans_dir):
        if bundle_parser.bundle_slug(d.name) == slug:
            raise BundleError(
                f"bundle slug {slug!r} already exists: "
                f"{d.name}")
    bundle_id = f"{today}-{slug}"
    bundle_dir = plans_dir / bundle_id
    if bundle_dir.exists():
        raise BundleError(
            f"bundle already exists: {bundle_id}")
    (bundle_dir / "todos").mkdir(parents=True)
    plan_written = False
    if plan:
        write_text(
            bundle_dir / "plan.md",
            _plan_skeleton(slug, feature=feature,
                           today=today))
        plan_written = True
    return {
        "id": bundle_id,
        "slug": slug,
        "path": str(bundle_dir),
        "plan": plan_written,
        "feature": feature,
    }


# ----------------------------------------------------------------
# Goal contracts (goal-prompt contract plan, 2026-11-12)
# ----------------------------------------------------------------

def _check_contract_gate(plans_dir, bundle_dir) -> None:
    """The arming gate for contract-carrying bundles:
    a bundle with a contract.md arms only when the
    contract is complete. An incomplete contract
    refuses the arm, naming the first empty field —
    the raise happens before any write, like every
    validation in the writers. A bundle carrying no
    contract is not a programme bundle and arms as
    before."""
    contract = bundle_parser.parse_contract(bundle_dir)
    if contract is None or contract["complete"]:
        return
    missing = contract["missing"]
    extra = (f" (also empty: {', '.join(missing[1:])})"
             if len(missing) > 1 else "")
    raise BundleError(
        f"goal contract incomplete: {missing[0]} is "
        f"empty — arming refused (bundle "
        f"{bundle_dir.name}){extra}")


def set_bundle_contract(plans_dir, bundle_ref, *,
                        programme, objective,
                        complete_when, work_record) -> dict:
    """Write a bundle's goal contract (contract.md):
    the four per-programme fields filled, the three
    fixed clauses verbatim from the template. The
    start gate applies at the write too — a contract
    with an empty filled field is not written."""
    filled = {
        "Programme": programme,
        "Objective": objective,
        "Complete when": complete_when,
        "Work record": work_record,
    }
    for field in bundle_parser.CONTRACT_FILLED_FIELDS:
        value = filled[field]
        if value is None or not str(value).strip():
            raise BundleError(
                f"goal contract field {field} is empty "
                f"— the contract is not written")
        if "\n" in str(value):
            raise BundleError(
                f"goal contract field {field} must be "
                f"one line")
    plans_dir = Path(plans_dir)
    bundle_dir = find_bundle_dir(plans_dir, bundle_ref)
    if bundle_dir is None:
        raise BundleError(
            f"unknown bundle: {bundle_ref!r} "
            f"(no such bundle under {plans_dir})")
    write_text(
        bundle_dir / bundle_parser.CONTRACT_FILE,
        bundle_parser.render_contract(
            programme.strip(), objective.strip(),
            complete_when.strip(), work_record.strip()))
    return {
        "bundle": bundle_dir.name,
        "contract": bundle_parser.parse_contract(
            bundle_dir),
    }


# ----------------------------------------------------------------
# Todo creation (§3.4)
# ----------------------------------------------------------------

_FRONT_MATTER_ORDER = ("id", "title", "status", "feature",
                       "plan", "plan_step", "worktree",
                       "created", "updated",
                       "progress_check", "progress_armed")


def _check_progress(progress, status, *,
                    no_progress=False):
    """Validate an arming request: a cadence the parser
    accepts, never armed onto a status whose move would
    disarm it in the same write, and never combined
    with the opt-out — a move declares a cadence, the
    opt-out, or neither (the automatic default)."""
    if no_progress and progress is not None:
        raise BundleError(
            "conflicting progress options: pass a "
            "cadence or the opt-out, not both")
    if progress is None:
        return
    if bundle_parser.parse_cadence(progress) is None:
        raise BundleError(
            f"bad progress cadence {progress!r}: "
            f"expected a cadence like 30m or 2h")
    if status in PROGRESS_STOP_STATUSES:
        raise BundleError(
            f"cannot arm a progress schedule on a move "
            f"to {status}: the schedule stops at that "
            f"status")


def _render_todo(fields: dict, body: str) -> str:
    lines = ["---"]
    for key in _FRONT_MATTER_ORDER:
        value = fields.get(key)
        if value is not None and value != "":
            lines.append(f"{key}: {value}")
    for key, value in fields.items():
        if key not in _FRONT_MATTER_ORDER \
                and value is not None and value != "":
            lines.append(f"{key}: {value}")
    lines.append("---")
    text = "\n".join(lines) + "\n"
    if body and body.strip():
        text += "\n" + body.strip("\n") + "\n"
    return text


def _bundle_feature(bundle_dir: Path):
    plan_file = bundle_dir / "plan.md"
    if plan_file.is_file():
        doc = parse_plan(
            plan_file.read_text(encoding="utf-8"))
        return doc["fields"].get("Feature") \
            or doc["fields"].get("feature")
    return None


def create_todo(plans_dir, bundle_ref, title, *, step=None,
                worktree=None, plan=None, feature=None,
                status: str = "todo", body: str = "",
                created: str = None,
                updated: str = None,
                progress: str = None,
                no_progress: bool = False,
                armed_at: str = None) -> dict:
    """Write one todo file into a bundle's todos/ dir,
    with complete §3.2 front-matter. The id is assigned
    here (timestamp-ordered, collision-checked across
    the WHOLE repo's bundles). Refuses a duplicate title
    in the bundle. Defaults: plan → the bundle's plan.md
    when it has one; feature → the bundle plan's Feature
    header when it declares one. Progress schedules:
    `progress` arms at creation with that cadence;
    `no_progress` records the explicit opt-out; and a
    todo created straight into `doing` with neither is
    armed at the default cadence — monitored by
    default, like the doing move in set_todo_status.
    """
    if not title or not title.strip() \
            or "\n" in title:
        raise BundleError(
            "todo title must be a single non-empty line")
    title = title.strip()
    if status not in TODO_STATUSES:
        raise BundleError(
            f"todo status must be one of {TODO_STATUSES}")
    _check_progress(progress, status,
                    no_progress=no_progress)
    if no_progress:
        progress_value = bundle_parser.PROGRESS_OPT_OUT
        armed_value = None
    elif progress is not None:
        progress_value = progress
        armed_value = armed_at or now_iso()
    elif status == "doing":
        progress_value = \
            bundle_parser.PROGRESS_DEFAULT_CADENCE
        armed_value = armed_at or now_iso()
    else:
        progress_value = None
        armed_value = None
    if step is not None and (not isinstance(step, int)
                             or step < 1):
        raise BundleError(
            f"plan step must be a positive integer, "
            f"got {step!r}")
    plans_dir = Path(plans_dir)
    bundle_dir = find_bundle_dir(plans_dir, bundle_ref)
    if bundle_dir is None:
        raise BundleError(
            f"unknown bundle: {bundle_ref!r} "
            f"(no such bundle under {plans_dir})")
    existing = bundle_parser.list_todos(
        plans_dir, bundle=bundle_dir.name)
    wanted = " ".join(title.lower().split())
    for t in existing:
        if t["title"] and " ".join(
                t["title"].lower().split()) == wanted:
            raise BundleError(
                f"duplicate todo title in bundle "
                f"{bundle_dir.name}: {title!r} already "
                f"exists as {t['id']}")
    if armed_value is not None:
        # This create arms: a contract-carrying bundle
        # arms only under a complete contract.
        _check_contract_gate(plans_dir, bundle_dir)
    if plan is None and (bundle_dir / "plan.md").is_file():
        plan = "plan.md"
    if feature is None:
        feature = _bundle_feature(bundle_dir)
    today = _today()
    fields = {
        "id": generate_todo_id(
            bundle_parser.all_todo_ids(plans_dir)),
        "title": title,
        "status": status,
        "feature": feature,
        "plan": plan,
        "plan_step": step,
        "worktree": worktree,
        "created": created or today,
        "updated": updated or created or today,
        "progress_check": progress_value,
        "progress_armed": armed_value,
    }
    todos_dir = bundle_dir / "todos"
    todos_dir.mkdir(exist_ok=True)
    filename = f"{fields['id']}-{slugify_title(title)}.md"
    todo_path = todos_dir / filename
    if todo_path.exists():
        raise BundleError(
            f"todo file already exists: {todo_path}")
    write_text(todo_path, _render_todo(fields, body))
    rel = todo_path.relative_to(plans_dir).as_posix()
    result = bundle_parser.parse_todo(
        todo_path.read_text(encoding="utf-8"), path=rel)
    result["bundle"] = bundle_dir.name
    result["file"] = str(todo_path)
    # The armed todo's scheduler entry is derived state,
    # synced in the same call (lib/progress/schedule.py);
    # its outcome never fails this write.
    result["progress_entry"] = \
        progress_schedule_mod.sync_todo(plans_dir, result)
    # The same arming writes the todo's owner-attention
    # row (lib/progress/attention.py): supervision
    # attaches at work start, beside the schedule.
    result["attention_row"] = \
        attention_mod.sync_todo(plans_dir, result)
    return result


# ----------------------------------------------------------------
# Todo status moves (§3.4)
# ----------------------------------------------------------------

def _find_todo_file(plans_dir: Path, todo_id: str):
    """(path, bundle_dir, archived) for a todo id,
    searched across the whole repo's bundles."""
    for archived in (False, True):
        for bundle_dir in _bundle_dirs(plans_dir,
                                       archived=archived):
            todos_dir = bundle_dir / "todos"
            if not todos_dir.is_dir():
                continue
            for f in sorted(todos_dir.glob("*.md")):
                parsed = bundle_parser.parse_todo(
                    f.read_text(encoding="utf-8"))
                if parsed["id"] == todo_id:
                    return f, bundle_dir, archived
    return None


def set_todo_status(plans_dir, todo_id, status, *,
                    note: str = None,
                    today: str = None,
                    progress: str = None,
                    no_progress: bool = False,
                    armed_at: str = None) -> dict:
    """Move one todo's status (todo|doing|blocked|done
    only — anything else refused), stamping `updated:`.
    An optional note is appended to the body (deploy
    records and blocker reasons live there). The rewrite
    is surgical: front-matter lines keep their order and
    unknown fields, the body is preserved verbatim.

    Progress schedules: arming is AUTOMATIC on a move
    to `doing` — a todo that declares neither a cadence
    nor the opt-out is armed at the default cadence in
    the same write, so work never runs unmonitored for
    want of a flag. `progress` (a cadence) overrides:
    it arms or re-arms at that cadence, stamping
    `progress_armed:` from `armed_at` or now. An
    existing cadence or opt-out rides through a doing
    move untouched; `no_progress` writes the opt-out
    (progress_check: off, no armed stamp), disarming a
    live schedule. A move to a stop status
    (done/blocked) clears both progress fields in the
    same write. Arming onto a stop status is refused."""
    if status not in TODO_STATUSES:
        raise BundleError(
            f"todo status must be one of {TODO_STATUSES}, "
            f"got {status!r}")
    _check_progress(progress, status,
                    no_progress=no_progress)
    plans_dir = Path(plans_dir)
    found = _find_todo_file(plans_dir, todo_id)
    if found is None:
        raise BundleError(f"unknown todo id: {todo_id!r}")
    todo_path, bundle_dir, archived = found
    text = todo_path.read_text(encoding="utf-8")
    fields, body, fm_lines = \
        bundle_parser.split_front_matter(text)
    if fields is None:
        raise BundleError(
            f"todo {todo_id} has no front-matter to "
            f"update: {todo_path}")
    today = today or _today()
    disarm = status in PROGRESS_STOP_STATUSES
    armed_stamp = armed_at or now_iso()
    # Resolve this move's progress write: arm_value is a
    # cadence to stamp, opt_out writes the off marker,
    # and neither means the existing fields ride through.
    current_check = fields.get("progress_check") or None
    arm_value = None
    opt_out = False
    if not disarm:
        if no_progress:
            opt_out = True
        elif progress is not None:
            arm_value = progress
        elif status == "doing" \
                and current_check \
                != bundle_parser.PROGRESS_OPT_OUT \
                and bundle_parser.parse_cadence(
                    current_check) is None:
            # No cadence declared (or an unreadable one):
            # the automatic arm. An existing cadence or
            # the opt-out is a declaration and rides.
            arm_value = \
                bundle_parser.PROGRESS_DEFAULT_CADENCE
    if arm_value is not None:
        # This move arms (a fresh arm or an explicit
        # re-arm): a contract-carrying bundle arms
        # only under a complete contract. A move whose
        # existing cadence rides through is not an arm
        # and is not gated.
        _check_contract_gate(plans_dir, bundle_dir)
    new_lines = []
    seen = set()
    for line in fm_lines:
        key = line.partition(":")[0].strip() \
            if ":" in line else None
        if key == "status":
            new_lines.append(f"status: {status}")
            seen.add("status")
        elif key == "updated":
            new_lines.append(f"updated: {today}")
            seen.add("updated")
        elif key in ("progress_check", "progress_armed"):
            if disarm:
                continue
            if opt_out:
                if key == "progress_check":
                    new_lines.append(
                        f"progress_check: "
                        f"{bundle_parser.PROGRESS_OPT_OUT}")
                    seen.add(key)
                continue
            if arm_value is not None:
                value = arm_value \
                    if key == "progress_check" \
                    else armed_stamp
                new_lines.append(f"{key}: {value}")
                seen.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    if "status" not in seen:
        new_lines.append(f"status: {status}")
    if "updated" not in seen:
        new_lines.append(f"updated: {today}")
    if opt_out and "progress_check" not in seen:
        new_lines.append(
            f"progress_check: "
            f"{bundle_parser.PROGRESS_OPT_OUT}")
    if arm_value is not None:
        if "progress_check" not in seen:
            new_lines.append(
                f"progress_check: {arm_value}")
        if "progress_armed" not in seen:
            new_lines.append(
                f"progress_armed: {armed_stamp}")
    if note:
        body = body.rstrip("\n")
        body = (body + "\n\n" if body else "") \
            + note.strip("\n") + "\n"
    out = "---\n" + "\n".join(new_lines) + "\n---\n"
    if body.strip():
        out += "\n" + body.strip("\n") + "\n"
    write_text(todo_path, out)
    rel = todo_path.relative_to(plans_dir).as_posix()
    result = bundle_parser.parse_todo(
        todo_path.read_text(encoding="utf-8"), path=rel)
    result["bundle"] = bundle_dir.name
    result["archived"] = archived
    result["file"] = str(todo_path)
    # The armed todo's scheduler entry is derived state,
    # synced in the same call (lib/progress/schedule.py);
    # its outcome never fails this write.
    result["progress_entry"] = \
        progress_schedule_mod.sync_todo(plans_dir, result)
    # The same transition writes or retires the todo's
    # owner-attention row (lib/progress/attention.py):
    # a terminal move retires the row in this write.
    result["attention_row"] = \
        attention_mod.sync_todo(plans_dir, result)
    return result


# ----------------------------------------------------------------
# DB-todo import (§3.7)
# ----------------------------------------------------------------

def import_db_todos(plans_dir, db_path, *,
                    bundle_slug: str = "project-zero-starter",
                    today: str = None) -> dict:
    """Import a project's registry-DB todos into a
    starter bundle of file todos, through the SAME
    writer as `wb todo new` (create_bundle/create_todo
    above — not a second path). DB rows are read only
    (lib.registry.list_todos) and never altered. Titles
    already present in the starter bundle are skipped,
    so a re-run imports nothing twice."""
    plans_dir = Path(plans_dir)
    db_todos = reg.list_todos(db_path)
    bundle_dir = find_bundle_dir(plans_dir, bundle_slug)
    if bundle_dir is None:
        created = create_bundle(plans_dir, bundle_slug,
                                today=today)
        bundle_id = created["id"]
        bundle_created = True
    else:
        bundle_id = bundle_dir.name
        bundle_created = False
    imported = []
    skipped = []
    present = {t["title"] for t in bundle_parser.list_todos(
        plans_dir, bundle=bundle_id) if t["title"]}
    for db_todo in db_todos:
        if db_todo["title"] in present:
            skipped.append(db_todo["id"])
            continue
        created_date = (db_todo.get("created_at")
                        or "")[:10] or None
        updated_date = (db_todo.get("updated_at")
                        or "")[:10] or None
        todo = create_todo(
            plans_dir, bundle_id, db_todo["title"],
            status=db_todo["status"],
            body=db_todo.get("notes") or "",
            created=created_date, updated=updated_date)
        imported.append({
            "db_id": db_todo["id"],
            "id": todo["id"],
            "title": todo["title"],
            "status": todo["status"],
        })
        present.add(db_todo["title"])
    bundle_path = find_bundle_dir(plans_dir, bundle_slug)
    return {
        "bundle": bundle_id,
        "bundle_path": str(bundle_path),
        "bundle_created": bundle_created,
        "imported": imported,
        "skipped": skipped,
    }
