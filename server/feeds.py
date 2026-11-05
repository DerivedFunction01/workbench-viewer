"""Feed builders: the read-side payload assembly.

One slice of the companion server: entry detail and
the mockups, artifacts, todos, plans, board, home,
worktrees, and diff feeds. Pure reads over lib/ — a locked or broken
project degrades only its own payload (common.degraded),
never the request.
"""

import hashlib
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

import feedcache  # noqa: E402
from common import (CFG, ApiError,  # noqa: E402
                    combined_fingerprint, degraded,
                    get_fingerprints, get_sweep, layout_of)

# ----------------------------------------------------------------
# Fingerprint-keyed feed caches (cache-refresh plan,
# 2026-11-05): the file-derived per-project feeds (todos,
# plans, board portions) serve from these keyed SWR
# caches, fresh-tested against the project's sweep
# fingerprint (common.get_fingerprints) instead of a
# wall-clock TTL — an untouched corpus serves cache
# indefinitely, and any write in it recomputes exactly
# that project's feeds on the next read. A project the
# sweep does not know (a unit-test fixture) has no
# fingerprint and computes directly, uncached.
# ----------------------------------------------------------------

_todos_cache = feedcache.KeyedFeedCache()
_plans_cache = feedcache.KeyedFeedCache()
_board_cache = feedcache.KeyedFeedCache()

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


def todos_feed(project, *, bundles=None) -> dict:
    """The project's todos feed, fingerprint-cached (see
    the cache note at the top of this module). A caller
    passing a shared bundles parse (the board portion)
    bypasses the cache and computes directly."""
    if bundles is not None:
        return _todos_feed_compute(project, bundles)
    fp = get_fingerprints().get(project.slug)
    if fp is None:
        return _todos_feed_compute(project)
    return _todos_cache.get(
        project.slug, fp,
        lambda: _todos_feed_compute(project))


def _todos_feed_compute(project, bundles=None) -> dict:
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
            "degraded": False, "captured_at": now_iso(),
            "stale_warning_days": CFG["stale_warning_days"]}
    file_todos, errors = [], []
    if m.plans is not None and m.plans.is_dir():
        try:
            if bundles is None:
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


def plans_feed(project, *, bundles=None) -> dict:
    """The project's plans feed, fingerprint-cached (see
    the cache note at the top of this module). A caller
    passing a shared bundles parse (the board portion)
    bypasses the cache and computes directly."""
    if bundles is not None:
        return _plans_feed_compute(project, bundles)
    fp = get_fingerprints().get(project.slug)
    if fp is None:
        return _plans_feed_compute(project)
    return _plans_cache.get(
        project.slug, fp,
        lambda: _plans_feed_compute(project))


def _plans_feed_compute(project, bundles=None) -> dict:
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False, "captured_at": now_iso(),
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
        if bundles is None:
            bundles = _attach_work_staleness(
                bundle_parser.list_bundles(m.plans), threshold)
        return {**base, "available": True,
                "plans": plans,
                "bundles": [_plans_bundle(b)
                            for b in bundles]}
    except Exception as e:
        return degraded({**base, "available": True,
                         "plans": [], "bundles": []}, e)


# ----------------------------------------------------------------
# Plans feed bundle projection (heavy-feed batching
# follow-up, 2026-11-03): the board-portion treatment
# applied to the Plans section's own feed. A bundle's
# todos ride the feed as CHECKLIST CARDS — the fields
# the plan list and the reader's checklist strip render,
# plus the served staleness derivation this feed is
# contract for — never as full todo records: the raw
# frontmatter
# dict (`fields`) duplicates the parsed keys, and
# `markdown` duplicates the whole todo file, so neither
# rides. The todo body is rendered in exactly one
# place, the Finished list's expander, so it rides only
# on archived bundles' cards. Full todo records stay in
# the Todos section feed; full plan records stay on the
# plan detail route — the reader already loads its
# document there. Plan summaries (and the feed's
# standalone `plans` list) ride whole: they are small
# and their questions are contract (plan-questions).
# The projection copies — a caller-shared bundles list
# (the board portion's) is never mutated.
# ----------------------------------------------------------------

_PLANS_TODO_KEYS = ("id", "title", "status", "valid",
                    "path", "bundle", "archived", "derived")


def _plans_todo_card(todo, *, archived: bool) -> dict:
    card = {k: todo.get(k) for k in _PLANS_TODO_KEYS}
    if archived:
        card["body"] = todo.get("body")
    return card


def _plans_bundle(bundle) -> dict:
    out = dict(bundle)
    out["todos"] = [
        _plans_todo_card(t, archived=bundle["archived"])
        for t in bundle["todos"]]
    return out


# ----------------------------------------------------------------
# Board portions (heavy-feed batching, 2026-11-01): the board
# screen is assembled client-side from ONE PORTION PER
# PROJECT — the large-scale pattern of one API call per
# portion instead of one monolith that re-derives every
# project before its first byte. A portion carries CARD
# PROJECTIONS (only the fields the board cards render;
# bodies, raw markdown, and step lists stay in the section
# feeds) and its DONE lanes are paginated: the response
# carries the first page plus the lane totals, and further
# pages ride the same endpoint via done_offset/done_limit.
# Portions are fingerprint-cached per done-page (the
# cache note at the top of this module), and one
# project's degradation lands in its own portion's errors,
# never in another portion's payload.
# ----------------------------------------------------------------

_TODO_CARD_KEYS = ("id", "title", "status", "bundle",
                   "feature", "worktree", "path", "source",
                   "valid")
_PLAN_CARD_KEYS = ("title", "path", "step_count")


def _todo_card(todo, project) -> dict:
    card = {k: todo.get(k) for k in _TODO_CARD_KEYS}
    card["project"] = project.slug
    card["project_name"] = project.name
    return card


def _plan_card(plan, bundle, project) -> dict:
    card = {k: plan.get(k) for k in _PLAN_CARD_KEYS}
    card["bundle"] = bundle["id"]
    card["bundle_kind"] = bundle["kind"]
    card["feature"] = bundle.get("feature")
    card["project"] = project.slug
    card["project_name"] = project.name
    return card


def _page_arg(query, key, default):
    try:
        return int(query.get(key, default))
    except (TypeError, ValueError):
        return default


def _registry_state(project) -> str:
    """A stat-shape hash of the project's registry store
    (the DB, its WAL, and the sibling export): the board
    portion's review queue derives from the registry, NOT
    from the .plans corpus the fingerprint covers, so a
    registry write (a review, a status ruling — through
    the viewer or the wb CLI) must move the board cache's
    freshness signal or the queue would serve stale
    indefinitely."""
    m = project.manifest
    if m.registry is None:
        return ""
    h = hashlib.sha256()
    candidates = [m.registry,
                  Path(f"{m.registry}-wal"),
                  m.registry.parent / "registry.json"]
    for path in candidates:
        try:
            st = path.stat()
        except OSError:
            continue
        h.update(f"{path.name}\0{st.st_size}\0"
                 f"{st.st_mtime_ns}\n".encode("utf-8"))
    return h.hexdigest()


def board_project_feed(project, query=None) -> dict:
    """One project's board portion, fingerprint-cached
    per normalized done-page (see the cache note at the
    top of this module): the cache key carries the page
    because the payload's done lanes are sliced by it,
    plus the registry state (see _registry_state): a
    registry write changes the key, so the next read
    computes fresh on the request path rather than
    serving the pre-review queue stale."""
    query = query or {}
    offset = max(0, _page_arg(query, "done_offset", 0))
    limit = _page_arg(query, "done_limit",
                      CFG["board_done_page"])
    limit = max(1, min(limit, 500))
    fp = get_fingerprints().get(project.slug)
    if fp is None:
        return _board_project_feed_compute(project, offset,
                                           limit)
    return _board_cache.get(
        (project.slug, offset, limit,
         _registry_state(project)), fp,
        lambda: _board_project_feed_compute(project, offset,
                                            limit))


def _board_project_feed_compute(project, offset,
                                limit) -> dict:
    errors = []
    lanes = {"todo": [], "doing": [], "blocked": [],
             "done": []}
    # One bundle parse per portion, shared by the todos
    # and plans feeds below (each used to parse the same
    # tree for itself). A parse failure leaves shared
    # None: each feed then re-derives — and degrades —
    # exactly as it did before the dedupe.
    shared = None
    m = project.manifest
    if m.plans is not None and m.plans.is_dir():
        try:
            shared = _attach_work_staleness(
                bundle_parser.list_bundles(m.plans),
                CFG["stale_warning_days"])
        except Exception:
            shared = None
    tf = _todos_feed_compute(project, bundles=shared)
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
            _todo_card(todo, project))
    plan_cards = {"todo": [], "doing": [], "done": []}
    pf = _plans_feed_compute(project, bundles=shared)
    if pf.get("degraded"):
        errors.append({"slug": project.slug,
                       "reason": pf["reason"]})
    for bundle in pf.get("bundles", []):
        plan = bundle.get("plan")
        if plan is None:
            continue  # plan-less bundle: no plan card
        plan_cards[plan["status_bucket"]].append(
            _plan_card(plan, bundle, project))
    review = []
    for feed in (mockups_feed(project, archived=False),
                 artifacts_feed(project, archived=False)):
        if feed["degraded"]:
            errors.append({"slug": project.slug,
                           "reason": feed["reason"]})
        for item in feed.get("triage", []):
            review.append({**item, "project": project.slug,
                           "project_name": project.name})
    counts = {
        "todos": {k: len(v) for k, v in lanes.items()},
        "plans": {k: len(v) for k, v in plan_cards.items()},
        "review_queue": len(review),
    }
    return {
        "slug": project.slug, "name": project.name,
        "degraded": False, "captured_at": now_iso(),
        "todos": {**lanes,
                  "done": lanes["done"][offset:offset + limit]},
        "plans": {**plan_cards,
                  "done": plan_cards["done"][offset:offset + limit]},
        "review_queue": review, "counts": counts,
        "done_page": {"offset": offset, "limit": limit},
        "errors": errors,
    }


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
# stored. The combined sweep fingerprint is a second,
# external-write invalidation source: the payload also
# records the fingerprint it was computed under, and a
# read that finds it moved serves stale and refreshes
# exactly as a TTL expiry does.
# ----------------------------------------------------------------

_home_cache = {"at": 0.0, "result": None, "fp": None}
_home_state_lock = threading.Lock()
_home_compute_lock = threading.Lock()
_home_refreshing = False
_home_generation = 0


def _home_invalidate_cache() -> None:
    global _home_generation
    with _home_state_lock:
        _home_generation += 1
        _home_cache.update(at=0.0, result=None, fp=None)


def _home_store(result, generation: int, fp) -> None:
    with _home_state_lock:
        if generation == _home_generation:
            _home_cache.update(at=time.monotonic(),
                               result=result, fp=fp)


def _compute_home_feed() -> dict:
    """GET /api/home (repo-home §4): one row per swept
    project, from lib/home derivations."""
    result = get_sweep()
    feed = home_mod.home_feed(
        result.projects,
        stale_days=CFG["worktree_stale_days"],
        workers=CFG["feed_pool_workers"])
    feed["sweep_errors"] = result.errors
    feed["captured_at"] = now_iso()
    return feed


def _home_refresh_background() -> None:
    global _home_refreshing
    try:
        with _home_state_lock:
            generation = _home_generation
        fp = combined_fingerprint()
        _home_store(_compute_home_feed(), generation, fp)
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
    was computed, not when it was served. Fresh means
    BOTH inside the TTL and computed under the current
    combined fingerprint (cache-refresh plan, 2026-11-05):
    any project's corpus moving makes the payload stale
    on the next read, however much TTL remains — it still
    serves stale while the refresh runs behind it."""
    cached = _home_cache["result"]
    if cached is not None:
        if time.monotonic() - _home_cache["at"] \
                < CFG["repos_ttl_s"] \
                and _home_cache["fp"] \
                == combined_fingerprint():
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
        fp = combined_fingerprint()
        result = _compute_home_feed()
        _home_store(result, generation, fp)
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
