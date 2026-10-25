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
"""

import re
from datetime import date
from pathlib import Path

from .parser import parse_plan, status_bucket

TODO_STATUSES = ("todo", "doing", "blocked", "done")
REQUIRED_TODO_FIELDS = ("id", "title", "status",
                        "created", "updated")
TODO_ID_RE = re.compile(r"^t-[0-9A-HJKMNP-TV-Z]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BUNDLE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")


def _valid_date(value: str) -> bool:
    if not _DATE_RE.match(value or ""):
        return False
    try:
        date.fromisoformat(value)
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
    return {
        "id": todo_id,
        "title": fields.get("title") or None,
        "status": status,
        "feature": fields.get("feature") or None,
        "plan": fields.get("plan") or None,
        "plan_step": plan_step,
        "worktree": fields.get("worktree") or None,
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
            "worktree": None, "created": None,
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
        "todos": todos,
        "errors": errors,
        "todo_count": len(todos),
        "open_count": sum(
            1 for t in todos
            if t["valid"] and t["status"] != "done"),
    }


def _flat_bundle(plan_path: Path, rel: str,
                 archived: bool) -> dict:
    plan = _plan_summary(plan_path, rel, archived)
    return {
        "kind": "flat-plan",
        "id": plan_path.name,
        "slug": plan_path.stem,
        "path": rel,
        "archived": archived,
        "feature": plan["feature"],
        "plan": plan,
        "todos": [],
        "errors": [],
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
