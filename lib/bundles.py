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

from . import registry as reg
from .plans import bundles as bundle_parser
from .plans.parser import parse_plan
from .util import write_text

TODO_STATUSES = bundle_parser.TODO_STATUSES

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
# Todo creation (§3.4)
# ----------------------------------------------------------------

_FRONT_MATTER_ORDER = ("id", "title", "status", "feature",
                       "plan", "plan_step", "worktree",
                       "created", "updated")


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
                updated: str = None) -> dict:
    """Write one todo file into a bundle's todos/ dir,
    with complete §3.2 front-matter. The id is assigned
    here (timestamp-ordered, collision-checked across
    the WHOLE repo's bundles). Refuses a duplicate title
    in the bundle. Defaults: plan → the bundle's plan.md
    when it has one; feature → the bundle plan's Feature
    header when it declares one."""
    if not title or not title.strip() \
            or "\n" in title:
        raise BundleError(
            "todo title must be a single non-empty line")
    title = title.strip()
    if status not in TODO_STATUSES:
        raise BundleError(
            f"todo status must be one of {TODO_STATUSES}")
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
                    today: str = None) -> dict:
    """Move one todo's status (todo|doing|blocked|done
    only — anything else refused), stamping `updated:`.
    An optional note is appended to the body (deploy
    records and blocker reasons live there). The rewrite
    is surgical: front-matter lines keep their order and
    unknown fields, the body is preserved verbatim."""
    if status not in TODO_STATUSES:
        raise BundleError(
            f"todo status must be one of {TODO_STATUSES}, "
            f"got {status!r}")
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
        else:
            new_lines.append(line)
    if "status" not in seen:
        new_lines.append(f"status: {status}")
    if "updated" not in seen:
        new_lines.append(f"updated: {today}")
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
