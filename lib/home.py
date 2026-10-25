"""The workspace home feed (repo-home spec §4).

One row per swept project, assembled from the derivations
that already exist — plans via the house parser, todos via
the bundle parser, triage/stale via export + staleness,
git via lib/worktrees, active plans via lib/active (§17)
— each section contained per project: a locked registry
or a broken repo degrades only its own fields (`degraded`
+ `reasons`), never the feed.

Todo counts read BUNDLE todo files (live-work-tracking
spec §3.7: file todos supersede the registry DB), behind
this same row shape. The registry table is read ONLY as
the §3.7 fallback — a project with DB todos and no file
todos shows its DB counts until imported; the moment
file todos exist they are the source. (This closes the
seam this module carried while Subplan 07 was landing.)

Each worktree entry carries its own active-plan
resolution (§17: per-worktree, from that worktree's own
.plans/), and the row's `showcase` is the main worktree's
resolution — the Overview's pinned primary.

Sort (§4): projects with an in-progress plan first, then
most recent activity, then name. Activity = the latest of
plan mtimes, todo updates, and the main worktree's last
commit.
"""

from datetime import datetime, timezone

from . import active as active_mod
from . import export as export_mod
from . import registry as reg
from . import staleness
from . import worktrees as wt_mod
from .plans import bundles as bundle_parser
from .plans import parser as plan_parser
from .util import now_iso, parse_iso


def _git_block(project, stale_days, now):
    result = wt_mod.list_worktrees(
        project.root, plans_dir=project.manifest.plans,
        stale_days=stale_days, now=now)
    if not result["available"]:
        # No .git at all = git simply unavailable (not a
        # degradation); a .git that fails to derive IS.
        hard = (project.root / ".git").exists()
        return None, [], result["reason"], None, hard
    main = next((w for w in result["worktrees"]
                 if w["is_main"]), None)
    git = None
    activity = None
    if main is not None:
        git = {"branch": main["branch"], "head": main["head"],
               "head_short": main["head_short"]}
        if main["last_commit_at"]:
            activity = parse_iso(main["last_commit_at"])
    return git, result["worktrees"], None, activity, False


def _plans_block(project):
    m = project.manifest
    if m.plans is None or not m.plans.is_dir():
        return {"available": False, "counts": {},
                "in_progress": None, "total": 0}, None
    summaries = plan_parser.list_plans(m.plans)
    counts = {"todo": 0, "doing": 0, "done": 0}
    for s in summaries:
        counts[s["status_bucket"]] = counts.get(
            s["status_bucket"], 0) + 1
    doing = [s for s in summaries
             if s["status_bucket"] == "doing"]
    in_progress = None
    activity = None
    if doing:
        top = max(doing, key=lambda s: s["modified"])
        in_progress = {"title": top["title"],
                       "path": top["path"]}
    if summaries:
        activity = datetime.fromtimestamp(
            max(s["modified"] for s in summaries),
            tz=timezone.utc)
    return {"available": True, "counts": counts,
            "in_progress": in_progress,
            "total": len(summaries)}, activity


def _todos_block(project):
    """Counts from bundle todo FILES (§3.7), with the
    registry DB as the fallback for a project that has DB
    todos and no file todos yet. Same precedence as the
    server's todos feed — one read model, two surfaces."""
    m = project.manifest
    if m.plans is not None and m.plans.is_dir():
        file_todos = []
        for b in bundle_parser.list_bundles(m.plans):
            file_todos.extend(b["todos"])
        if file_todos:
            counts = {}
            activity = None
            total = 0
            for t in file_todos:
                if not t["valid"] or not t["status"]:
                    continue
                counts[t["status"]] = counts.get(
                    t["status"], 0) + 1
                total += 1
                if t.get("updated"):
                    ts = parse_iso(t["updated"])
                    if ts.tzinfo is None:
                        ts = ts.replace(
                            tzinfo=timezone.utc)
                    if activity is None or ts > activity:
                        activity = ts
            return {"available": True, "counts": counts,
                    "total": total,
                    "source": "files"}, activity
    if m.registry is None or not m.registry.is_file():
        return {"available": False, "counts": {},
                "total": 0, "source": "files"}, None
    todos = reg.list_todos(m.registry)
    counts = {}
    activity = None
    for t in todos:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
        if t.get("updated_at"):
            ts = parse_iso(t["updated_at"])
            if activity is None or ts > activity:
                activity = ts
    return {"available": True, "counts": counts,
            "total": len(todos),
            "source": "db-fallback"}, activity


def _review_block(project):
    """Triage + stale counts from the same derivation the
    Mockups feed uses (export fold + staleness)."""
    m = project.manifest
    if m.registry is None or not m.registry.is_file():
        return {"available": False, "triage_count": 0,
                "stale_count": 0}
    data = export_mod.build_export(m.registry,
                                   project=project.slug)
    triage = 0
    stale = 0
    for e in data["entries"]:
        if e["archived"]:
            continue
        if e["derived"].get("stale"):
            stale += 1
        reasons = staleness.triage_reasons(
            e, e["derived"],
            reg.latest_review(m.registry, e["id"]))
        if reasons:
            triage += 1
    return {"available": True, "triage_count": triage,
            "stale_count": stale}


def project_row(project, *, stale_days=14, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    row = {"slug": project.slug, "name": project.name,
           "root": str(project.root), "degraded": False,
           "reasons": []}
    activities = []

    def contain(fn, key, fallback):
        try:
            value, activity = fn()
            row[key] = value
            if activity is not None:
                activities.append(activity)
            return value
        except Exception as e:  # per-section containment
            row["degraded"] = True
            row["reasons"].append(
                f"{key}: {str(e)[:160]}")
            row[key] = fallback
            return fallback

    git, worktrees, wt_reason, git_activity = (None, [],
                                               None, None)
    try:
        git, worktrees, wt_reason, git_activity, hard = \
            _git_block(project, stale_days, now)
        if wt_reason and hard:
            row["degraded"] = True
            row["reasons"].append(f"git: {wt_reason}")
        if git_activity is not None:
            activities.append(git_activity)
    except Exception as e:
        row["degraded"] = True
        row["reasons"].append(f"git: {str(e)[:160]}")
    row["git"] = git
    # Active-plan resolution per worktree (§17), contained
    # like every other block: a broken .plans/ in one
    # worktree degrades only that worktree's `active`.
    try:
        actives = active_mod.active_by_worktree(
            project.root, project.manifest.plans, worktrees)
        by_path = {a["path"]: a["active"] for a in actives}
        for w in worktrees:
            w["active"] = by_path.get(w["path"])
    except Exception as e:
        row["degraded"] = True
        row["reasons"].append(f"active: {str(e)[:160]}")
        for w in worktrees:
            w["active"] = None
    row["worktrees"] = worktrees
    row["has_extra_worktrees"] = any(
        not w["is_main"] for w in worktrees)
    main_wt = next((w for w in worktrees if w["is_main"]),
                   None)
    if main_wt is not None:
        row["showcase"] = main_wt["active"]
    elif project.manifest.plans is not None:
        # No git worktree list (not a repo): the checkout
        # itself is the default worktree (§17.1) — resolve
        # its .plans/ directly so the showcase still pins.
        try:
            row["showcase"] = active_mod.resolve_active(
                project.manifest.plans, branch=None)
        except Exception as e:
            row["degraded"] = True
            row["reasons"].append(
                f"active: {str(e)[:160]}")
            row["showcase"] = None
    else:
        row["showcase"] = None

    contain(lambda: _plans_block(project), "plans",
            {"available": False, "counts": {},
             "in_progress": None, "total": 0})
    contain(lambda: _todos_block(project), "todos",
            {"available": False, "counts": {}, "total": 0,
             "source": "files"})
    try:
        row["review"] = _review_block(project)
    except Exception as e:
        row["degraded"] = True
        row["reasons"].append(f"review: {str(e)[:160]}")
        row["review"] = {"available": False,
                         "triage_count": 0, "stale_count": 0}
    row["last_activity"] = max(activities).isoformat() \
        if activities else None
    return row


def home_feed(projects, *, stale_days=14, now=None) -> dict:
    """The home rows for a sweep result's projects, sorted
    per §4. Sorting never raises: rows missing activity
    sort last within their group."""
    rows = [project_row(p, stale_days=stale_days, now=now)
            for p in projects]
    # Stable multi-pass sort, least significant key first:
    # name asc, then activity desc (ISO strings sort
    # chronologically), then in-progress-plan group first.
    rows.sort(key=lambda r: r["name"])
    rows.sort(key=lambda r: r["last_activity"] or "",
              reverse=True)
    rows.sort(key=lambda r: 0 if r["plans"].get(
        "in_progress") else 1)
    return {"projects": rows, "captured_at": now_iso()}
