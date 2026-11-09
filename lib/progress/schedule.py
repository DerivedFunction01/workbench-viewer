"""Scheduler entries for armed progress schedules.

The mechanism behind the progress schedules (the owner's
2026-10-31 commission: armed work must not stall waiting
for an agent to create a schedule by hand). The scheduler
server's registry is local files — one YAML entry per job,
rescanned every tick — so creating a schedule IS writing
a file, and retiring one is deleting it.

This module is that write path, keyed to the todo file as
the record of truth:

- `sync_todo` runs at the end of the harness's todo
  writers (lib/bundles.py — the one mutation path, so the
  CLI and the server get it alike). Armed todo (a
  `progress_check` field on a live, unarchived todo) →
  its entry exists, rendered from its current state.
  Disarmed, terminal, or archived → its entry is gone.
- The entry is a scripted job (classification: a fixed
  command; exit 0 = on track / disarmed / gone, exit 3 =
  stalled, and when it speaks is fully determined by that
  exit code) whose argv runs `wb progress-check <id>` in
  the project root at the todo's own cadence. A stall
  exits non-zero, so the scheduler's failure report
  carries the stall line as a ping.
- `sync_all` reconciles the whole registry against the
  swept armed set (the `wb progress --sync-entries`
  backfill); the doctor's entry checks flag any drift
  that survives — the todo files rule, entries are
  derived state.

Location seam: the jobs dir is the sibling scheduler
repo's `jobs/` under the workspace root, overridable by
the WB_SCHEDULER_JOBS_DIR env var. No jobs dir → every
sync is a silent no-op (a machine without the scheduler
still gets the full harness). A second seam keeps test
suites out of the live registry: WB_TMP_ROOT names the
machine's temp roots (this box's 512 MB tmpfs, the
disk-backed gate scratch, the system temp), and a project
root under one of them is scratch — its syncs no-op and
its renders carry no ${WS} anchor (the anchor cannot
express a temp path). The workspace root itself
(this repo's parent, matching the scheduler's ${WS}
definition) is overridable by WB_WORKSPACE_ROOT, and
this repo's root as that anchor sees it by
WB_VIEWER_ROOT. Entry
paths use the scheduler's ${WS} anchor, never absolute
paths. A sync failure NEVER fails the todo write it
rides: the outcome rides the writer's result dict as
`progress_entry`, and the doctor surfaces persistent
divergence.

Admission posture (the owner's 2026-11-08 ruling):
harness-rendered entries are born admitted — the
render carries migrated: true with migrated_at set to
the todo's arming date. The scheduler repo's admission
flow (validate + proof run, then the flip) governs
hand-written entries; this machine-rendered family is
exempt by ruling, its one fixed template being what a
proof run would vet. The doctor's unscheduled check
still convicts a pre-ruling render (migrated: false)
until a sync re-renders it, and still requires the
server's next-due table to carry the entry.

Classification (the classified-catalog plan, Step 4):
every render carries its class — a catalog block
(origin: machine; generality: deployment-specific, the
writer owning the lifecycle; use_case: work-tracking)
and a machine-form source stamp (writer, project,
todo, source_class). The source class derives from
the same temp-root determination as the live-registry
refusal above: a scratch project's entry is
fixture-classed, and the scheduler's loader holds a
fixture-classed machine entry out of the live registry
entirely — the classification-layer backstop to this
module's own refusal, which fires first.
"""

import json
import os
import re
from datetime import date
from pathlib import Path

from . import report as progress_mod
from .. import util as util_mod
from ..plans import bundles as bundle_parser
from ..util import write_text

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

ENTRY_PREFIX = "wb-progress-"
STOP_STATUSES = ("done", "blocked")
CHECK_TIMEOUT_SECS = 120

_CLASSIFICATION = (
    "fixed command (wb progress-check <todo-id>); exit 0 "
    "on track, disarmed, or gone, exit 3 stalled with the "
    "stall line as output; when it speaks is fully "
    "determined by the exit code, no content judgment")
_OWNER_REASON = (
    "Machine-written by the workbench harness for one "
    "armed todo; the todo file is the record of truth and "
    "this entry is its derived schedule.")
_SELF_REMOVAL = (
    "the harness deletes this entry in the same writer "
    "call that disarms the todo (a move to done or "
    "blocked, or the bundle's archival); the workbench "
    "doctor flags any entry that outlives its todo")


def _workspace_root():
    override = os.environ.get("WB_WORKSPACE_ROOT")
    if override:
        return Path(override)
    return REPO_ROOT.parent


def _harness_root():
    """This repo's root as the scheduler's ${WS} anchor
    sees it: the physical repo root, overridable by
    WB_VIEWER_ROOT (a fixture workspace lays the tree
    out differently than this machine does)."""
    override = os.environ.get("WB_VIEWER_ROOT")
    if override:
        return Path(override)
    return REPO_ROOT


def jobs_dir():
    """The scheduler registry dir, or None when this
    machine has no scheduler repo (the sync no-ops)."""
    override = os.environ.get("WB_SCHEDULER_JOBS_DIR")
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    candidate = _workspace_root() / "scheduler" / "jobs"
    return candidate if candidate.is_dir() else None


def entry_id(project_slug: str, todo_id: str) -> str:
    return f"{ENTRY_PREFIX}{project_slug}-{todo_id.lower()}"


def is_armed(todo) -> bool:
    """The entry-existence predicate: an armed todo is a
    live one — a cadence (not the opt-out value) in
    progress_check, not at a stop status, not in an
    archived bundle (arming that outlives its work is
    the doctor's orphan case, and it carries no
    schedule)."""
    return bundle_parser.parse_cadence(
        todo.get("progress_check")) is not None \
        and todo.get("status") not in STOP_STATUSES \
        and not todo.get("archived")


_MIGRATED_RE = re.compile(r"^migrated:\s*(\S+)\s*$",
                          re.MULTILINE)


def _admitted(entry_text: str) -> bool:
    """An entry carrying the admission mark (migrated:
    true) — born that way under the owner's 2026-11-08
    ruling for harness renders, or flipped by the
    scheduler repo's admission flow for entries that
    predate it. The engine schedules only migrated:true
    entries."""
    match = _MIGRATED_RE.search(entry_text)
    return bool(match) and match.group(1) == "true"


def entry_migrated(path: Path):
    """The entry file's migrated flag: True / False, or
    None when the file cannot be read or carries no such
    line (the scheduler's own validation owns malformed
    entries)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _MIGRATED_RE.search(text)
    if not match:
        return None
    return match.group(1) == "true"


def scheduled_ids(directory=None):
    """The ids in the scheduler server's next-due table
    (state/next_due.json beside the registry's jobs/
    dir) — the server's own record of what it will
    actually fire. None when the table is absent or
    unreadable: no server state, no verdict."""
    directory = directory or jobs_dir()
    if directory is None:
        return None
    state = directory.parent / "state" / "next_due.json"
    try:
        data = json.loads(state.read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return set(data)


def _project_root(plans_dir):
    """Walk up from a project's plans dir to the dir
    carrying its workbench.yaml (the project root)."""
    current = Path(plans_dir)
    for candidate in (current, *current.parents):
        if (candidate / "workbench.yaml").is_file():
            return candidate
    return None


def _ws_relative(path):
    """`path` relative to the workspace root (this repo's
    parent — the scheduler's ${WS} anchor), or None when
    the path escapes it."""
    try:
        return path.resolve().relative_to(
            _workspace_root().resolve()).as_posix()
    except ValueError:
        return None


def _platform_temp_roots():
    """The platform temp roots (lib.util owns the
    determination; kept under this module's historical
    name for its callers and tests)."""
    return util_mod.platform_temp_roots()


def _temp_roots():
    """The temp roots incl. the WB_TMP_ROOT seam
    (lib.util owns the determination)."""
    return util_mod.temp_roots()


def _under_temp(path) -> bool:
    """True when the resolved path sits under a temp
    root — scratch state (test fixtures, gate scratch),
    whose projects are not the live workspace's and
    must never reach the live registry."""
    return util_mod.under_temp_root(path)


def _live_jobs_dir():
    """The live registry dir on THIS machine, from the
    module's own location — never from the (redirect-
    able) workspace-root seam: the repo's parent is the
    machine's workspace, and its scheduler/jobs is the
    registry the real server scans. A seam-redirected
    workspace has a different parent, so its jobs dir
    never compares equal."""
    return (REPO_ROOT.parent / "scheduler"
            / "jobs").resolve()


def _entry_live(directory) -> bool:
    """An entry written into `directory` is LIVE — it
    will fire against real work — exactly when the
    directory is this machine's real registry."""
    return Path(directory).resolve() == _live_jobs_dir()


def _project_arg(root):
    """The project root as the entry's --root argv item:
    ${WS}-anchored for a live project, or the absolute
    path when the root escapes the anchor — a workspace
    root itself redirected under a temp root (a test
    seam) or a project outside the workspace. The entry
    then lives wherever the sync's jobs dir points and
    is only ever read back by its own fixture."""
    rel = _ws_relative(root)
    if rel is not None and not _under_temp(root) \
            and not _under_temp(_workspace_root()):
        return f"${{WS}}/{rel}"
    return Path(root).resolve().as_posix()


def _quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _title_text(todo) -> str:
    raw = re.sub(r"[^A-Za-z0-9 .,;:()\-]", " ",
                 (todo.get("title") or "").strip())
    return re.sub(r"\s+", " ", raw).strip()[:80]


def _armed_date(todo) -> str:
    """The todo's arming date — a born-admitted entry's
    admission date: the date part of the progress_armed
    timestamp, or today when the todo carries none."""
    armed = todo.get("progress_armed") or ""
    if len(armed) >= 10 and armed[4] == "-" \
            and armed[7] == "-":
        return armed[:10]
    return date.today().isoformat()


def _source_class(root) -> str:
    """The rendered entry's source class (the scheduler
    registry's SOURCE_CLASSES): `fixture` for a scratch
    project — its root under a temp root, the same
    determination the live-registry refusal keys on — and
    `project` for a real one. The class is declared on
    the entry so the scheduler's loader can hold a
    fixture-classed entry out of the live registry as a
    backstop; the harness's own refusal fires first, so
    in practice only project-classed entries are ever
    rendered into it."""
    return "fixture" if _under_temp(root) else "project"


def render_entry(project_slug: str, project_arg: str,
                 repo_rel: str, todo, source_class: str
                 = "project") -> str:
    """One registry entry in the scheduler's strict YAML
    subset (schema: the scheduler repo's jobs/README.md).
    The project is selected by a --root argv item, never
    a cwd field: the scheduler's loader expands anchors
    in argv and state_paths only, so an anchored cwd
    reaches the spawn literally and fails (diagnosed
    2026-11-08, when the first admission proofs ran the
    executor by hand). The entry is born admitted (the
    owner's 2026-11-08 ruling): migrated: true with
    migrated_at set to the arming date."""
    eid = entry_id(project_slug, todo["id"])
    title = (f"Progress check - {project_slug}: "
             f"{_title_text(todo)} ({todo['id']})")
    lines = [
        f"id: {eid}",
        f"title: {_quoted(title)}",
        "kind: scripted",
        "status: active",
        "cadence:",
        "  type: interval",
        f"  every: {todo['progress_check']}",
        "owner: none",
        f"owner_reason: {_quoted(_OWNER_REASON)}",
        "run:",
        "  argv:",
        f"    - ${{WS}}/{repo_rel}/.venv/bin/python",
        f"    - ${{WS}}/{repo_rel}/wb",
        "    - --root",
        f"    - {project_arg}",
        "    - progress-check",
        f"    - {todo['id']}",
        f"timeout_secs: {CHECK_TIMEOUT_SECS}",
        "report:",
        "  when: on_failure",
        "  ok_exit_codes:",
        "    - 0",
        f"classification: {_quoted(_CLASSIFICATION)}",
        "lifetime: until_complete",
        f"self_removal: {_quoted(_SELF_REMOVAL)}",
        "migrated: true",
        f"migrated_at: {_armed_date(todo)}",
        "catalog:",
        "  origin: machine",
        "  generality: deployment-specific",
        "  use_case: work-tracking",
        "source:",
        "  writer: workbench-harness",
        f"  project: {project_slug}",
        f"  todo: {todo['id']}",
        f"  source_class: {source_class}",
    ]
    return "\n".join(lines) + "\n"


_MIGRATED_AT_RE = re.compile(r"^migrated_at:[ \t]*(\S+)[ \t]*$",
                             re.MULTILINE)


def _carry_migrated_at(existing: str, render: str) -> str:
    """The fresh render with the existing entry's
    migrated_at carried over: the date on disk is the
    admission record, while every other line follows
    the todo's current state."""
    match = _MIGRATED_AT_RE.search(existing)
    if not match:
        return render
    return _MIGRATED_AT_RE.sub(
        f"migrated_at: {match.group(1)}", render, count=1)


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.parent / (path.name + ".tmp")
    write_text(tmp, text)
    os.replace(tmp, path)


def _sync_todo(plans_dir, todo) -> dict:
    directory = jobs_dir()
    if directory is None:
        return {"action": "skipped",
                "reason": "no scheduler jobs dir"}
    root = _project_root(plans_dir)
    if root is None:
        return {"action": "skipped",
                "reason": "project root not found"}
    if _under_temp(root) and _entry_live(directory):
        # The leak this guards: a test run arms a fixture
        # todo while the jobs dir resolves to the LIVE
        # registry (no seam set); the fixture's tempdir
        # dies with the run and the entry crashes every
        # cycle on a manifest that no longer exists.
        return {"action": "skipped",
                "reason": "scratch project, live jobs dir"}
    repo_rel = _ws_relative(_harness_root())
    if _ws_relative(root) is None \
            and _entry_live(directory):
        # Outside the workspace the ${WS} anchor cannot
        # express the root — and an entry landing in the
        # live registry would fire against a project
        # that is not there. (Into a non-live jobs dir
        # the absolute form serves: a fixture's own
        # registry, read back by its own tests.)
        return {"action": "skipped",
                "reason": "project outside the workspace root"}
    if repo_rel is None:
        return {"action": "skipped",
                "reason": "project outside the workspace root"}
    slug = root.name
    eid = entry_id(slug, todo["id"])
    path = directory / f"{eid}.yaml"
    if is_armed(todo):
        text = render_entry(
            slug,
            _project_arg(root),
            repo_rel, todo,
            source_class=_source_class(root))
        if path.is_file():
            existing = path.read_text(encoding="utf-8")
            if existing == text:
                return {"action": "unchanged",
                        "entry": eid}
            if _admitted(existing):
                # An admitted entry (born admitted, or
                # flipped by the scheduler repo's
                # admission flow): carry its migrated_at
                # — the admission record — over the fresh
                # render, while the rest of the entry
                # follows the todo's current state.
                text = _carry_migrated_at(existing, text)
                if text == existing:
                    return {"action": "unchanged",
                            "entry": eid,
                            "admitted": True}
        _write_atomic(path, text)
        return {"action": "written", "entry": eid}
    if path.is_file():
        path.unlink()
        return {"action": "removed", "entry": eid}
    return {"action": "unchanged", "entry": eid}


def sync_todo(plans_dir, todo) -> dict:
    """Bring one todo's scheduler entry in line with its
    post-write state. Never raises: the todo file is the
    record of truth and the entry is derived state, so a
    sync failure rides the result, it never fails the
    write (the doctor flags persistent divergence)."""
    try:
        return _sync_todo(plans_dir, todo)
    except Exception as e:
        return {"action": "error", "error": str(e)}


def sync_all(projects) -> dict:
    """Reconcile the registry against the swept armed
    set: write or refresh every armed todo's entry and
    delete every wb-progress entry whose todo is gone,
    terminal, disarmed, or archived. `projects` are sweep
    project objects (slug + manifest.plans)."""
    directory = jobs_dir()
    if directory is None:
        return {"skipped": "no scheduler jobs dir",
                "written": [], "removed": [], "kept": 0}
    wanted = {}
    for project in projects:
        plans_dir = project.manifest.plans
        if plans_dir is None:
            continue
        for todo in bundle_parser.list_todos(plans_dir):
            if is_armed(todo):
                wanted[entry_id(project.slug,
                                todo["id"])] = (plans_dir,
                                                 todo)
    written, kept = [], 0
    for eid, (plans_dir, todo) in sorted(wanted.items()):
        outcome = sync_todo(plans_dir, todo)
        if outcome["action"] == "written":
            written.append(eid)
        elif outcome["action"] == "unchanged":
            kept += 1
    removed = []
    for path in sorted(directory.glob(
            f"{ENTRY_PREFIX}*.yaml")):
        if path.stem not in wanted:
            path.unlink()
            removed.append(path.stem)
    return {"written": written, "removed": removed,
            "kept": kept}


def parse_entry_todo_id(path: Path):
    """The canonical todo id a wb-progress entry checks,
    read from its argv (the last argv item), or None when
    the file does not parse as one of ours."""
    try:
        lines = path.read_text(
            encoding="utf-8").splitlines()
    except OSError:
        return None
    in_argv = False
    items = []
    for line in lines:
        if line.strip() == "argv:":
            in_argv = True
            continue
        if in_argv:
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())
            elif stripped:
                break
    if len(items) >= 4 and items[-2] == "progress-check":
        return items[-1]
    return None


def check_todo(plans_dir, todo_id, *, now=None):
    """The `wb progress-check` verdict: (exit_code, line).
    Exit 0 — on track, not armed, terminal, or not found
    (a missing todo means an orphaned entry, which the
    doctor reconciles; pinging about it every cadence
    would only spam). Exit 3 — stalled, with the stall
    line the scheduler's failure report carries."""
    for todo in bundle_parser.list_todos(plans_dir):
        if todo.get("id") != todo_id:
            continue
        block = progress_mod.todo_progress(todo, now=now)
        if block is None:
            return 0, f"{todo_id}: not armed"
        if todo.get("status") in STOP_STATUSES:
            return 0, (f"{todo_id}: {todo['status']} — "
                       f"schedule stopped")
        if block["stalled"]:
            return 3, (
                f"STALLED {todo.get('bundle')}/{todo_id} "
                f"({todo.get('title') or ''}): "
                f"{block['missed_checks']} missed checks "
                f"at {block['cadence']} cadence, last "
                f"activity {block['last_activity']}")
        return 0, (f"{todo_id}: on track "
                   f"({block['missed_checks']} missed "
                   f"checks)")
    return 0, (f"{todo_id}: not found — entry orphaned "
               f"(the doctor reconciles)")
