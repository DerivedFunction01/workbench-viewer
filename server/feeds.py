"""Feed builders: the read-side payload assembly.

One slice of the companion server: entry detail and
the mockups, artifacts, todos, plans, board, home,
worktrees, and diff feeds. Pure reads over lib/ — a locked or broken
project degrades only its own payload (common.degraded),
never the request.
"""

import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))  # for lib/
sys.path.insert(0, str(HERE))        # for config (flat, donor-style)

from lib import active as active_mod  # noqa: E402
from lib import diffs as diff_mod  # noqa: E402
from lib import export as export_mod  # noqa: E402
from lib import files as files_mod  # noqa: E402
from lib import home as home_mod  # noqa: E402
from lib import registry as reg  # noqa: E402
from lib import staleness  # noqa: E402
from lib import validators as val_mod  # noqa: E402
from lib import worktrees as wt_mod  # noqa: E402
from lib.plans import bundles as bundle_parser  # noqa: E402
from lib.plans import parser as plan_parser  # noqa: E402
from lib.util import now_iso  # noqa: E402

from common import (CFG, ApiError, degraded,  # noqa: E402
                    get_sweep, layout_of)

# ----------------------------------------------------------------
# Feed builders (reads; each contained per project)
# ----------------------------------------------------------------

def entry_detail(db_path, entry_id) -> dict:
    entry = reg.get_entry(db_path, entry_id)
    latest = reg.latest_review(db_path, entry_id)
    thresholds = staleness.load_thresholds(db_path)
    return {
        "entry": entry,
        "derived": staleness.entry_staleness(
            entry, thresholds=thresholds),
        "approval": staleness.approval_coverage(entry, latest),
        "latest_review": latest,
        "history": reg.history_for(db_path, entry_id),
        "files": files_mod.list_entry_files(entry),
    }


DESIGN_KINDS = tuple(k for k in reg.KINDS if k != "artifact")
ARTIFACT_KINDS = ("artifact",)


def _entries_feed(project, *, archived: bool, kinds) -> dict:
    """One collection's feed over the shared registry: the
    collection boundary is the kind filter — entries and
    triage serve only the given kinds, while the export and
    the reconcile block stay whole-store (entry dirs share
    one tree)."""
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False}
    if m.registry is None:
        return {**base, "available": False,
                "reason": "no registry declared in manifest",
                "entries": [], "triage": [],
                "reconcile": None}
    if not m.registry.is_file():
        return {**base, "available": False,
                "reason": "registry not initialized yet "
                          "(wb init creates it)",
                "entries": [], "triage": [],
                "reconcile": None}
    try:
        data = export_mod.build_export(m.registry,
                                       project=project.slug)
        entries = [e for e in data["entries"]
                   if bool(e["archived"]) == archived
                   and e["kind"] in kinds]
        triage = []
        for e in data["entries"]:
            if e["archived"] or e["kind"] not in kinds:
                continue
            reasons = staleness.triage_reasons(
                e, e["derived"],
                reg.latest_review(m.registry, e["id"]))
            if reasons:
                triage.append({"id": e["id"], "title": e["title"],
                               "kind": e["kind"],
                               "reasons": reasons})
        return {**base, "available": True, "entries": entries,
                "triage": triage,
                "reconcile": val_mod.reconcile(
                    m.registry, layout_of(project))}
    except Exception as e:
        return degraded({**base, "available": True,
                         "entries": [], "triage": [],
                         "reconcile": None}, e)


def mockups_feed(project, *, archived: bool) -> dict:
    return _entries_feed(project, archived=archived,
                         kinds=DESIGN_KINDS)


def artifacts_feed(project, *, archived: bool) -> dict:
    return _entries_feed(project, archived=archived,
                         kinds=ARTIFACT_KINDS)


def _attach_work_staleness(bundles,
                           threshold_days: int) -> list:
    """Attach the lib/staleness work derivations in place:
    `derived` on each bundle row, on its plan summary, and
    on each of its todos (stale-work-warnings plan —
    derived at read time, never stored)."""
    for bundle in bundles:
        bundle["derived"] = staleness.bundle_staleness(
            bundle, threshold_days=threshold_days)
        if bundle.get("plan") is not None:
            bundle["plan"]["derived"] = \
                staleness.plan_staleness(
                    bundle["plan"],
                    threshold_days=threshold_days)
        for todo in bundle["todos"]:
            todo["derived"] = staleness.todo_staleness(
                todo, threshold_days=threshold_days)
    return bundles


def todos_feed(project) -> dict:
    """Todos read from bundle todo FILES (live-work spec
    §3.7: file todos supersede the registry DB). The DB is
    read ONLY as the §3.7 fallback — a project with DB
    todos and no file todos shows its DB todos until they
    are imported; the moment file todos exist they are the
    source and the DB rows are not merged in. Invalid
    front-matter todos stay in the list, flagged, and their
    parser errors ride on the feed — never a silent skip."""
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False,
            "stale_warning_days": CFG["stale_warning_days"]}
    file_todos, errors = [], []
    if m.plans is not None and m.plans.is_dir():
        try:
            bundles = _attach_work_staleness(
                bundle_parser.list_bundles(m.plans),
                CFG["stale_warning_days"])
            for bundle in bundles:
                errors.extend(bundle["errors"])
                file_todos.extend(bundle["todos"])
        except Exception as e:
            return degraded({**base, "available": True,
                             "source": "files", "todos": [],
                             "errors": errors}, e)
    if file_todos:
        return {**base, "available": True, "source": "files",
                "todos": file_todos, "errors": errors}
    if m.registry is not None and m.registry.is_file():
        try:
            db_todos = reg.list_todos(m.registry)
        except Exception as e:
            return degraded({**base, "available": True,
                             "source": "db-fallback",
                             "todos": [], "errors": errors}, e)
        if db_todos:
            rows = []
            for t in db_todos:
                row = {**t, "source": "db", "bundle": None,
                       "feature": None, "worktree": None,
                       "valid": True, "errors": []}
                # Uniform shape: DB rows carry no `created`
                # frontmatter date, so the derivation reads
                # age None and never flags.
                row["derived"] = staleness.todo_staleness(
                    row,
                    threshold_days=CFG["stale_warning_days"])
                rows.append(row)
            return {**base, "available": True,
                    "source": "db-fallback",
                    "todos": rows,
                    "errors": errors}
        return {**base, "available": True, "source": "files",
                "todos": [], "errors": errors}
    if m.plans is not None and m.plans.is_dir():
        return {**base, "available": True, "source": "files",
                "todos": [], "errors": errors}
    return {**base, "available": False, "source": "files",
            "todos": [], "errors": errors}


def plans_feed(project) -> dict:
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False,
            "stale_warning_days": CFG["stale_warning_days"]}
    if m.plans is None or not m.plans.is_dir():
        return {**base, "available": False, "plans": [],
                "bundles": []}
    try:
        threshold = CFG["stale_warning_days"]
        plans = plan_parser.list_plans(m.plans)
        for summary in plans:
            summary["derived"] = staleness.plan_staleness(
                summary, threshold_days=threshold)
        bundles = _attach_work_staleness(
            bundle_parser.list_bundles(m.plans), threshold)
        return {**base, "available": True,
                "plans": plans,
                "bundles": bundles}
    except Exception as e:
        return degraded({**base, "available": True,
                         "plans": [], "bundles": []}, e)


def board_feed() -> dict:
    result = get_sweep()
    lanes = {"todo": [], "doing": [], "blocked": [],
             "done": []}
    plan_cards = {"todo": [], "doing": [], "done": []}
    review_queue = []
    errors = []
    for project in result.projects:
        tf = todos_feed(project)
        if tf["degraded"]:
            errors.append({"slug": project.slug,
                           "reason": tf["reason"]})
        for err in tf.get("errors", []):
            errors.append({"slug": project.slug, **err})
        for todo in tf["todos"]:
            if not todo.get("valid", True) \
                    or todo.get("status") not in lanes:
                continue  # invalid todos surface as errors
            lanes[todo["status"]].append(
                {**todo, "project": project.slug,
                 "project_name": project.name})
        pf = plans_feed(project)
        for bundle in pf.get("bundles", []):
            plan = bundle.get("plan")
            if plan is None:
                continue  # plan-less bundle: no plan card
            plan_cards[plan["status_bucket"]].append(
                {**plan, "bundle": bundle["id"],
                 "bundle_kind": bundle["kind"],
                 "feature": bundle.get("feature"),
                 "project": project.slug,
                 "project_name": project.name})
        for feed in (mockups_feed(project, archived=False),
                     artifacts_feed(project, archived=False)):
            if feed["degraded"]:
                errors.append({"slug": project.slug,
                               "reason": feed["reason"]})
            # The two collections' kinds are disjoint, so the
            # union cannot double-count an item.
            for item in feed.get("triage", []):
                review_queue.append(
                    {**item, "project": project.slug,
                     "project_name": project.name})
    return {"todos": lanes, "plans": plan_cards,
            "review_queue": review_queue, "errors": errors,
            "sweep_errors": result.errors}


# ----------------------------------------------------------------
# Home feed cache (the repos-feed idiom, repos_feed.py):
# the home derivation walks every swept project —
# registry counts, plan summaries, git state — and
# costs seconds (under load, tens of seconds), so it
# is computed at most once per TTL window (repos_ttl_s,
# the client's poll cadence), served stale past it
# while one background thread refreshes, and only a
# never-filled cache computes on the request path
# (single-flighted). Writes that change what the feed
# derives (registry curation, a guarded repo save)
# invalidate — and the generation counter keeps a
# payload computed across an invalidation from being
# stored.
# ----------------------------------------------------------------

_home_cache = {"at": 0.0, "result": None}
_home_state_lock = threading.Lock()
_home_compute_lock = threading.Lock()
_home_refreshing = False
_home_generation = 0


def _home_invalidate_cache() -> None:
    global _home_generation
    with _home_state_lock:
        _home_generation += 1
        _home_cache.update(at=0.0, result=None)


def _home_store(result, generation: int) -> None:
    with _home_state_lock:
        if generation == _home_generation:
            _home_cache.update(at=time.monotonic(),
                               result=result)


def _compute_home_feed() -> dict:
    """GET /api/home (repo-home §4): one row per swept
    project, from lib/home derivations."""
    result = get_sweep()
    feed = home_mod.home_feed(
        result.projects,
        stale_days=CFG["worktree_stale_days"])
    feed["sweep_errors"] = result.errors
    feed["captured_at"] = now_iso()
    return feed


def _home_refresh_background() -> None:
    global _home_refreshing
    try:
        with _home_state_lock:
            generation = _home_generation
        _home_store(_compute_home_feed(), generation)
    except Exception as e:
        # The stale payload keeps serving; the next stale
        # request kicks another refresh.
        print(f"workbench-viewer: home feed refresh "
              f"failed: {e}", file=sys.stderr)
    finally:
        with _home_state_lock:
            _home_refreshing = False


def _home_kick_refresh() -> None:
    global _home_refreshing
    with _home_state_lock:
        if _home_refreshing:
            return
        _home_refreshing = True
    threading.Thread(target=_home_refresh_background,
                     daemon=True).start()


def home_feed() -> dict:
    """GET /api/home: the cached home payload (see the
    cache note above); captured_at is when the payload
    was computed, not when it was served."""
    cached = _home_cache["result"]
    if cached is not None:
        if time.monotonic() - _home_cache["at"] \
                < CFG["repos_ttl_s"]:
            return cached
        _home_kick_refresh()
        return cached
    with _home_compute_lock:
        # The startup warm or a racing request may have
        # filled the cache while this one waited.
        cached = _home_cache["result"]
        if cached is not None:
            return cached
        with _home_state_lock:
            generation = _home_generation
        result = _compute_home_feed()
        _home_store(result, generation)
        return result


def worktrees_feed(project) -> dict:
    """GET /api/projects/<slug>/worktrees (repo-home §6):
    the project's worktrees, derived read-only, each with
    its active-plan resolution attached (§17 — resolved in
    lib from that worktree's own .plans/)."""
    result = wt_mod.list_worktrees(
        project.root, plans_dir=project.manifest.plans,
        stale_days=CFG["worktree_stale_days"])
    if result["available"]:
        actives = active_mod.active_by_worktree(
            project.root, project.manifest.plans,
            result["worktrees"])
        by_path = {a["path"]: a["active"] for a in actives}
        for w in result["worktrees"]:
            w["active"] = by_path.get(w["path"])
    return {"slug": project.slug, "name": project.name,
            "captured_at": now_iso(), **result}


def diff_feed(project, query: dict) -> dict:
    """GET /api/projects/<slug>/diff (repo-home §18.5,
    B2): the anchored diff, structured by lib/diffs — this
    layer only translates query params. `?peek=<path>`
    answers the §18.4 peek for one untracked/ignored file
    in the anchored worktree instead. Unanchored or
    unknown requests are honest 4xx (DiffError carries
    the status)."""
    plans_dir = project.manifest.plans
    try:
        if query.get("peek"):
            peek = diff_mod.peek_file(
                project.root,
                worktree=query.get("worktree") or None,
                path=query["peek"])
            return {"slug": project.slug,
                    "name": project.name,
                    "captured_at": now_iso(), "peek": peek}
        result = diff_mod.get_diff(
            project.root,
            worktree=query.get("worktree") or None,
            mode=query.get("mode") or "working",
            base=query.get("base") or None,
            target=query.get("target") or None,
            bundle=query.get("bundle") or None,
            plans_dir=plans_dir,
            all_files=query.get("all") == "1")
    except diff_mod.DiffError as e:
        raise ApiError(e.status, e.message)
    return {"slug": project.slug, "name": project.name,
            "captured_at": now_iso(), **result}
