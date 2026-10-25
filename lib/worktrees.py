"""Worktree + git-state derivations (repo-home spec §6).

Derivation only, and read-only by construction: every git
invocation runs with GIT_OPTIONAL_LOCKS=0 and no command
writes (no index updates, no worktree create/remove/prune —
the viewer NEVER manages worktrees, §6). A locked, missing,
or mid-rebase worktree degrades its own entry only; the
other worktrees of the same repo still derive.

Attribution (decision D2): branch naming convention first
(the label IS the branch name, e.g. `build/05-shell`); a
plan whose header carries a `worktree: <branch>` line
overrides with an explicit plan link — plans are read with
the house parser, nothing new is parsed here.

The stale flag ("likely done") is DERIVED, never ruled:
branch merged into its base OR head commit untouched for
stale_days. It is computed for non-main worktrees only —
the main checkout is the repo itself, not a work stream.
"""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .plans import parser as plan_parser
from .util import parse_iso

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


class WorktreeError(Exception):
    """A git derivation failed, with a human-readable
    reason (carried on the degraded entry, never raised
    past list_worktrees for a single worktree)."""


def _git(cwd, *args, timeout=5) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, timeout=timeout,
            env=_GIT_ENV)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise WorktreeError(f"git {args[0]} failed: {e}")
    if out.returncode != 0:
        reason = (out.stderr or out.stdout).strip()
        raise WorktreeError(
            f"git {' '.join(args[:2])}: {reason[:160]}")
    return out.stdout


def _git_ok(cwd, *args) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, timeout=5,
            env=_GIT_ENV)
        return out.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def plan_worktree_links(plans_dir) -> dict:
    """{branch: plan rel-path} from `worktree:` header lines
    in the project's top-level plans (D2 override). A plan
    that fails to parse contributes no link, never an
    error — links are an override, not a gate."""
    links = {}
    if not plans_dir or not Path(plans_dir).is_dir():
        return links
    for f in sorted(Path(plans_dir).glob("*.md")):
        try:
            doc = plan_parser.parse_plan(
                f.read_text(encoding="utf-8"), path=f.name)
        except (OSError, UnicodeDecodeError):
            continue
        for key, value in doc["fields"].items():
            if key.lower() == "worktree":
                branch = value.strip().split("\n")[0].strip()
                if branch:
                    links[branch] = f.name
    return links


def _porcelain(root) -> list:
    """Raw `worktree list --porcelain` entries:
    {path, head, branch|None, bare}."""
    raw = _git(root, "worktree", "list", "--porcelain")
    entries, cur = [], None
    for line in raw.splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[9:], "head": None,
                   "branch": None, "bare": False}
            entries.append(cur)
        elif cur is not None and line.startswith("HEAD "):
            cur["head"] = line[5:]
        elif cur is not None and line.startswith("branch "):
            ref = line[7:]
            cur["branch"] = ref[len("refs/heads/"):] \
                if ref.startswith("refs/heads/") else ref
        elif cur is not None and line == "bare":
            cur["bare"] = True
    return entries


def _base_ref(path, branch, main_branch):
    """(base_ref, base_name) for ahead/behind + merged: the
    branch's upstream when set, else the repo's default
    branch (origin/HEAD when present, else the main
    worktree's branch). base_ref None when the worktree IS
    the base."""
    try:
        upstream = _git(
            path, "rev-parse", "--abbrev-ref",
            "--symbolic-full-name", "@{upstream}").strip()
        if upstream:
            return upstream, upstream
    except WorktreeError:
        pass
    if branch is None or branch == main_branch:
        return None, main_branch
    try:
        origin_head = _git(
            path, "symbolic-ref", "--short",
            "refs/remotes/origin/HEAD").strip()
        if origin_head:
            return origin_head, origin_head
    except WorktreeError:
        pass
    return main_branch, main_branch


def _derive_one(root, raw, *, main_branch, links, stale_days,
                now) -> dict:
    path = raw["path"]
    branch = raw["branch"]
    entry = {
        "path": path,
        "branch": branch,
        "head": raw["head"],
        "head_short": (raw["head"] or "")[:7] or None,
        "is_main": Path(path) == Path(root),
        "base": None, "ahead": None, "behind": None,
        "dirty": None, "changed_count": None,
        "last_commit_at": None, "untouched_days": None,
        "merged": False, "likely_done": False,
        "rebase_in_progress": False,
        "degraded": False, "reason": None,
        "attribution": {
            "label": branch,
            "plan": links.get(branch) if branch else None,
            "source": "plan" if branch in links
                      else "convention",
        },
    }
    if raw["bare"]:
        entry["degraded"] = True
        entry["reason"] = "bare worktree"
        return entry
    if not Path(path).is_dir():
        entry["degraded"] = True
        entry["reason"] = "worktree path missing (prunable)"
        return entry
    try:
        gitdir = _git(path, "rev-parse",
                      "--absolute-git-dir").strip()
        if (Path(gitdir) / "rebase-merge").exists() \
                or (Path(gitdir) / "rebase-apply").exists():
            entry["rebase_in_progress"] = True
            entry["degraded"] = True
            entry["reason"] = "rebase in progress"
        status = _git(path, "status", "--porcelain")
        lines = [ln for ln in status.splitlines() if ln]
        entry["changed_count"] = len(lines)
        entry["dirty"] = bool(lines)
        base_ref, base_name = _base_ref(path, branch,
                                        main_branch)
        entry["base"] = base_name
        if base_ref is not None:
            counts = _git(path, "rev-list", "--left-right",
                          "--count",
                          f"{base_ref}...HEAD").split()
            entry["behind"] = int(counts[0])
            entry["ahead"] = int(counts[1])
            if branch is not None:
                entry["merged"] = _git_ok(
                    path, "merge-base", "--is-ancestor",
                    "HEAD", base_ref)
        else:
            entry["ahead"] = 0
            entry["behind"] = 0
        last = _git(path, "log", "-1", "--format=%cI",
                    "HEAD").strip()
        if last:
            entry["last_commit_at"] = last
            delta = now - parse_iso(last)
            entry["untouched_days"] = delta.days
    except WorktreeError as e:
        entry["degraded"] = True
        entry["reason"] = str(e)
    if not entry["is_main"]:
        entry["likely_done"] = bool(
            entry["merged"] or (
                entry["untouched_days"] is not None
                and entry["untouched_days"] >= stale_days))
    return entry


def list_worktrees(root, *, plans_dir=None, stale_days=14,
                   now=None) -> dict:
    """All worktrees of the repo at `root`, each derived
    independently. A non-git root is available=False, not
    an exception — the home feed degrades per project."""
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    try:
        raws = _porcelain(root)
    except WorktreeError as e:
        return {"available": False, "worktrees": [],
                "reason": str(e)}
    main_branch = None
    for raw in raws:
        if Path(raw["path"]) == root and raw["branch"]:
            main_branch = raw["branch"]
            break
    links = plan_worktree_links(plans_dir)
    return {
        "available": True,
        "worktrees": [
            _derive_one(root, raw, main_branch=main_branch,
                        links=links, stale_days=stale_days,
                        now=now)
            for raw in raws
        ],
    }
