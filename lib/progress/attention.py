"""Owner-attention armed rows for progress schedules.

The staffing-absorption link (owner-attention plan
2026-11-11, section Arming; commission from main
2026-11-11 23:24 EST): the harness already arms a
todo's progress schedule at its `doing` transition —
this module extends that same transition so the armed
work item is also visible to owner-attention's
supervision evaluator from the moment work starts.

- `sync_todo` runs at the end of the harness's todo
  writers (lib/bundles.py — the one mutation path, so
  the CLI and the server get it alike), beside the
  scheduler-entry sync. Armed todo (a cadence in
  `progress_check` — the declared opt-out writes no
  row) → its row exists, rendered from its current
  state. Disarmed, terminal, or archived → its row is
  gone.
- The row is one JSON file per armed work item under
  the attention service's runtime state
  (`var/armed/` in that repo — runtime state is never
  tracked there). Its evaluator supervises armed rows;
  this module is only the write/retire link.
- `sync_all` reconciles the whole directory against
  the swept armed set (it rides `wb progress
  --sync-entries` beside the scheduler reconcile).

Row shape (coordinated with the attention thread,
which owns the registry build): handle, programme,
project, todo, title, bundle, cadence,
cadence_minutes, armed_at, status, and a source stamp
(writer + source class, the schedule entry's stamp
form). `programme` and `project` are the todo's
project slug. `handle` is the work item's own handle —
its todo id: harness todos record no posting lane, and
the harness does not guess a lane from a project
(several posting handles share one project).

Location seam: the armed dir is the sibling
owner-attention repo's `var/armed/` under the
workspace root, overridable by the
WB_ATTENTION_ARMED_DIR env var. No owner-attention
repo on the machine → every sync is a silent no-op
(a machine without the attention service still gets
the full harness). The temp-root leak guard mirrors
the scheduler seam: a scratch (temp-root) project's
sync never writes into the LIVE armed dir, and its
rows carry the fixture source class wherever they do
land. A sync failure NEVER fails the todo write it
rides: the outcome rides the writer's result dict as
`attention_row`.
"""

import json
import os
from pathlib import Path

from .. import util as util_mod
from ..plans import bundles as bundle_parser
from ..util import write_text
from . import schedule as schedule_mod

REPO_ROOT = schedule_mod.REPO_ROOT

ROW_PREFIX = "wb-armed-"


def _workspace_root():
    override = os.environ.get("WB_WORKSPACE_ROOT")
    if override:
        return Path(override)
    return REPO_ROOT.parent


def armed_dir():
    """The attention armed-rows dir, or None when this
    machine has no owner-attention repo (the sync
    no-ops). The env override names the dir directly;
    it is created on first write, since var/armed is
    this link's own runtime directory."""
    override = os.environ.get("WB_ATTENTION_ARMED_DIR")
    if override:
        return Path(override)
    root = _workspace_root() / "owner-attention"
    if not root.is_dir():
        return None
    return root / "var" / "armed"


def _live_armed_dir():
    """The live armed dir on THIS machine, from the
    module's own location — never from the (redirect-
    able) workspace-root seam."""
    return (REPO_ROOT.parent / "owner-attention"
            / "var" / "armed").resolve()


def _dir_live(directory) -> bool:
    return Path(directory).resolve() == _live_armed_dir()


def row_id(project_slug: str, todo_id: str) -> str:
    return f"{ROW_PREFIX}{project_slug}-{todo_id.lower()}"


def render_row(project_slug: str, todo,
               source_class: str = "project") -> dict:
    """One armed work item's registry row, as data.
    The cadence is the todo's declared cadence — the
    writers arm a doing todo at the 15-minute default
    when it declares none, so an armed todo always
    carries one."""
    cadence = todo.get("progress_check")
    delta = bundle_parser.parse_cadence(cadence)
    return {
        "handle": todo["id"],
        "programme": project_slug,
        "project": project_slug,
        "todo": todo["id"],
        "title": todo.get("title") or "",
        "bundle": todo.get("bundle"),
        "cadence": cadence,
        "cadence_minutes": (
            int(delta.total_seconds() // 60)
            if delta is not None else None),
        "armed_at": todo.get("progress_armed"),
        "status": todo.get("status"),
        "source": {
            "writer": "workbench-harness",
            "project": project_slug,
            "todo": todo["id"],
            "source_class": source_class,
        },
    }


def _row_text(project_slug: str, todo,
              source_class: str) -> str:
    return json.dumps(
        render_row(project_slug, todo,
                   source_class=source_class),
        indent=2, sort_keys=True) + "\n"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    write_text(tmp, text)
    os.replace(tmp, path)


def _sync_todo(plans_dir, todo) -> dict:
    directory = armed_dir()
    if directory is None:
        return {"action": "skipped",
                "reason": "no owner-attention repo"}
    root = schedule_mod._project_root(plans_dir)
    if root is None:
        return {"action": "skipped",
                "reason": "project root not found"}
    if util_mod.under_temp_root(root) \
            and _dir_live(directory):
        # The scheduler seam's leak, mirrored: a test
        # run arms a fixture todo while the armed dir
        # resolves to the LIVE directory (no seam set);
        # the fixture's tempdir dies with the run and
        # the row would supervise work that never was.
        return {"action": "skipped",
                "reason": "scratch project, live armed dir"}
    slug = root.name
    rid = row_id(slug, todo["id"])
    path = directory / f"{rid}.json"
    if schedule_mod.is_armed(todo):
        source_class = (
            "fixture" if util_mod.under_temp_root(root)
            else "project")
        text = _row_text(slug, todo, source_class)
        if path.is_file():
            if path.read_text(encoding="utf-8") == text:
                return {"action": "unchanged", "row": rid}
        _write_atomic(path, text)
        return {"action": "written", "row": rid}
    if path.is_file():
        path.unlink()
        return {"action": "removed", "row": rid}
    return {"action": "unchanged", "row": rid}


def sync_todo(plans_dir, todo) -> dict:
    """Bring one todo's attention row in line with its
    post-write state. Never raises: the todo file is
    the record of truth and the row is derived state,
    so a sync failure rides the result, it never fails
    the write."""
    try:
        return _sync_todo(plans_dir, todo)
    except Exception as e:
        return {"action": "error", "error": str(e)}


def sync_all(projects) -> dict:
    """Reconcile the armed dir against the swept armed
    set: write or refresh every armed todo's row and
    delete every wb-armed row whose todo is gone,
    terminal, disarmed, or archived. `projects` are
    sweep project objects (slug + manifest.plans)."""
    directory = armed_dir()
    if directory is None:
        return {"skipped": "no owner-attention repo",
                "written": [], "removed": [], "kept": 0}
    wanted = {}
    for project in projects:
        plans_dir = project.manifest.plans
        if plans_dir is None:
            continue
        for todo in bundle_parser.list_todos(plans_dir):
            if schedule_mod.is_armed(todo):
                wanted[row_id(project.slug,
                              todo["id"])] = (plans_dir,
                                               todo)
    written, kept = [], 0
    for rid, (plans_dir, todo) in sorted(wanted.items()):
        outcome = sync_todo(plans_dir, todo)
        if outcome["action"] == "written":
            written.append(rid)
        elif outcome["action"] == "unchanged":
            kept += 1
    removed = []
    if directory.is_dir():
        for path in sorted(directory.glob(
                f"{ROW_PREFIX}*.json")):
            if path.stem not in wanted:
                path.unlink()
                removed.append(path.stem)
    return {"written": written, "removed": removed,
            "kept": kept}
