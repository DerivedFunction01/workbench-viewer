"""Active-plan resolution (repo-home spec §17).

Activeness is PER-WORKTREE: the main checkout is simply
the default worktree, and each worktree carries its own
`.plans/` (untracked files do not cross worktrees), read
here READ-ONLY for its bundles and its declaration.
Todos never vote — activeness derives from bundles and
plans only.

Resolution order (deterministic, provenance shown):
  1. Declared  — `.plans/active.yaml` in that worktree
     ({bundle, plan?, since}) — a ruling; written only
     through set_active()/clear_active() below (the `wb
     activate` verb is the caller; the one mutation path).
  2. Branch convention — the worktree's branch matches a
     bundle (`build/<slug>` <-> bundle slug; D2 reused).
  3. Unique in-progress plan — exactly one active bundle
     carries a doing-status plan.
  4. Recency — several in-progress: the most recently
     modified plan file wins, labeled "by recency".
  5. None — honest "no active plan"; nothing is guessed.

The showcase holds ONE primary; other in-progress bundles
in the same worktree list beneath it as "also in progress
here" — multiplicity is surfaced, never hidden (§17.3).
A plan-less bundle can be active (declared or by branch):
its showcase is the bundle itself and its todos.
"""

from datetime import date
from pathlib import Path

from .plans import bundles as bundle_parser

DECLARATION_FILE = "active.yaml"

SOURCES = ("declared", "branch", "unique", "recency",
           "none")


class ActiveError(Exception):
    """An active-plan declaration mutation was refused,
    with a reason."""


# ----------------------------------------------------------------
# The declaration (§17.2 step 1): a tiny untracked yaml the
# agent writes when work starts in a worktree. Parsed with
# a flat `key: value` reader — the file carries exactly
# three scalar keys by design, so no yaml dependency.
# ----------------------------------------------------------------

def read_declaration(plans_dir) -> dict | None:
    """The parsed active.yaml, or None when absent. A
    malformed file reads as a declaration with an `error`
    field (honest degradation — the resolver reports it
    and falls through, it never guesses silently)."""
    path = Path(plans_dir) / DECLARATION_FILE
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"unreadable {DECLARATION_FILE}: "
                         f"{e}"}
    fields = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            return {"error": f"{DECLARATION_FILE}: not a "
                             f"key: value line: {line!r}"}
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("'\"")
    if not fields.get("bundle"):
        return {"error": f"{DECLARATION_FILE}: no bundle "
                         f"key"}
    return {"bundle": fields["bundle"],
            "plan": fields.get("plan") or None,
            "since": fields.get("since") or None}


def set_active(plans_dir, bundle_ref, *, plan=None,
               since=None) -> dict:
    """Write active.yaml for a bundle (resolved through
    the bundle parser, so a declaration can only name a
    bundle the feeds can see). `plan`, when given, is a
    plans-dir-relative plan path inside that bundle.
    `since` defaults to today."""
    plans_dir = Path(plans_dir)
    bundle = _find_bundle(plans_dir, bundle_ref)
    if bundle is None:
        raise ActiveError(
            f"unknown bundle: {bundle_ref!r} (no such "
            f"bundle under {plans_dir})")
    if plan is not None:
        known = bundle["plan"]["path"] if bundle["plan"] \
            else None
        if plan != known:
            raise ActiveError(
                f"bundle {bundle['id']} has no plan "
                f"{plan!r}" + (f" (its plan is {known!r})"
                               if known else " (plan-less)"))
    since = since or date.today().isoformat()
    lines = [f"bundle: {bundle['id']}"]
    if plan:
        lines.append(f"plan: {plan}")
    lines.append(f"since: {since}")
    path = plans_dir / DECLARATION_FILE
    path.write_text("\n".join(lines) + "\n",
                    encoding="utf-8")
    return {"bundle": bundle["id"], "plan": plan,
            "since": since, "file": str(path)}


def clear_active(plans_dir) -> dict:
    """Remove the declaration (work ended / moved). A
    missing file is a no-op result, not an error."""
    path = Path(plans_dir) / DECLARATION_FILE
    existed = path.is_file()
    if existed:
        path.unlink()
    return {"cleared": existed, "file": str(path)}


# ----------------------------------------------------------------
# Resolution
# ----------------------------------------------------------------

def _find_bundle(plans_dir, ref) -> dict | None:
    if not ref:
        return None
    ref = str(ref).removesuffix("/")
    for b in bundle_parser.list_bundles(plans_dir):
        if b["archived"]:
            continue
        if ref in (b["id"], b["slug"]):
            return b
    return None


def _plan_view(bundle) -> dict | None:
    plan = bundle["plan"] if bundle else None
    if plan is None:
        return None
    return {"path": plan["path"], "title": plan["title"],
            "status_bucket": plan["status_bucket"],
            "status_raw": plan["status_raw"],
            "modified": plan["modified"],
            "feature": plan["feature"]}


def _bundle_view(bundle) -> dict:
    return {"id": bundle["id"], "slug": bundle["slug"],
            "path": bundle["path"], "kind": bundle["kind"],
            "feature": bundle["feature"],
            "todo_count": bundle["todo_count"],
            "open_count": bundle["open_count"]}


def _result(source, bundle, *, also, declared=None,
            note=None) -> dict:
    return {
        "source": source,
        "bundle": _bundle_view(bundle) if bundle else None,
        "plan": _plan_view(bundle) if bundle else None,
        "also_in_progress": [
            {"bundle": _bundle_view(b),
             "plan": _plan_view(b)} for b in also],
        "declared": declared,
        "note": note,
    }


def resolve_active(plans_dir, *, branch=None) -> dict:
    """The active plan of ONE worktree, from its own
    .plans/ (read-only). `branch` is the worktree's branch
    (step 2's signal); None for a detached/main-less read.
    The result carries provenance (`source`) and every
    other in-progress bundle (`also_in_progress`)."""
    plans_dir = Path(plans_dir)
    bundles = [b for b in bundle_parser.list_bundles(
        plans_dir) if not b["archived"]]
    doing = [b for b in bundles
             if b["plan"] is not None
             and b["plan"]["status_bucket"] == "doing"]

    def others(primary):
        return [b for b in doing if b is not primary]

    # 1. Declared.
    declared = read_declaration(plans_dir)
    declared_error = None
    if declared is not None:
        if declared.get("error"):
            declared_error = declared["error"]
            declared = None
        else:
            bundle = _find_bundle(plans_dir,
                                  declared["bundle"])
            if bundle is None:
                declared_error = (
                    f"active.yaml names unknown bundle "
                    f"{declared['bundle']!r}")
            elif declared.get("plan") and (
                    bundle["plan"] is None
                    or bundle["plan"]["path"]
                    != declared["plan"]):
                declared_error = (
                    f"active.yaml names plan "
                    f"{declared['plan']!r}, not a plan of "
                    f"bundle {bundle['id']}")
            else:
                return _result(
                    "declared", bundle,
                    also=others(bundle), declared=declared)
    note = declared_error

    # 2. Branch convention: build/<slug> (or the bare
    # branch name) matches a bundle slug (D2).
    if branch:
        slug = branch[len("build/"):] \
            if branch.startswith("build/") else branch
        bundle = next(
            (b for b in bundles if b["slug"] == slug), None)
        if bundle is not None:
            return _result("branch", bundle,
                           also=others(bundle), note=note)

    # 3/4. In-progress plans: unique, else recency.
    if len(doing) == 1:
        return _result("unique", doing[0], also=[],
                       note=note)
    if len(doing) > 1:
        top = max(doing,
                  key=lambda b: b["plan"]["modified"])
        return _result("recency", top, also=others(top),
                       note=note)

    # 5. None — honest.
    return _result("none", None, also=[], note=note)


def _plans_rel(root, plans_abs):
    """The plans dir's path relative to a repo root, so a
    worktree's OWN .plans/ can be found at the same
    relative place inside the worktree."""
    try:
        return Path(plans_abs).relative_to(Path(root))
    except (ValueError, TypeError):
        return Path(".plans")


def active_by_worktree(root, plans_dir, worktrees) -> list:
    """Resolve activeness for every worktree of a repo:
    [{path, branch, is_main, active}] — each read from
    THAT worktree's own .plans/ (§17.1). `worktrees` are
    lib/worktrees entries (path/branch/is_main)."""
    rel = _plans_rel(root, plans_dir) \
        if plans_dir is not None else Path(".plans")
    out = []
    for w in worktrees:
        wt_plans = Path(w["path"]) / rel
        try:
            active = resolve_active(wt_plans,
                                    branch=w["branch"])
        except Exception as e:  # contained per worktree
            active = {"source": "none", "bundle": None,
                      "plan": None, "also_in_progress": [],
                      "declared": None,
                      "note": f"resolution failed: "
                              f"{str(e)[:160]}"}
        out.append({"path": w["path"],
                    "branch": w["branch"],
                    "is_main": w["is_main"],
                    "active": active})
    return out
