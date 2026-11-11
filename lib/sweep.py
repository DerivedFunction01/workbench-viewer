"""The discovery sweep: walk the configured roots, find
projects by their manifests.

Mechanics (context/architecture.md): a directory containing
the manifest file at its top level IS a project — record it
and never descend into it. Pruned names are never entered.
Depth is bounded under each root. No watcher: the sweep runs
when called (server start, explicit rescan, CLI invocation)
and callers may cache briefly.

A manifest that fails to parse does not kill the sweep: it is
reported in `errors` so the failure is visible (the /health
habit — answer "why doesn't it see my repo?" from data).
another workspace repo carries no manifest and is therefore invisible —
excluded by design, not by a special case here.

Project identity is the REPO, not the directory (repo-home
§19 fallout): a linked git worktree carries the same tracked
manifest as its main checkout, so directory-keyed discovery
registered one repo twice under one slug and broke slug-keyed
navigation. Candidates are therefore canonicalized by repo
identity — the resolved git common dir for a checkout root —
and each identity registers at most one project: the main
checkout's. A linked worktree never registers separately; it
stays visible through the main checkout's worktree
derivations (lib/worktrees.py). If only linked worktrees of
a repo are discovered (the main checkout sits outside the
sweep roots), the project still registers ONCE, rooted at
the main checkout, whose manifest is loaded from disk; if
the main checkout carries no manifest there, the identity
registers nothing — never a duplicate, never a phantom.
Non-git manifest dirs and manifests in a repo subdirectory
(not a checkout root) keep the historical behavior: the
directory itself is the project — unless a git checkout
claims the same slug in the same sweep (the export
exclusion below).

Registration hygiene rules ride on top (2026-11-09;
export exclusion 2026-11-11): scratch never registers —
a candidate under a temp root, or under a scratch-marked
component (dot-directory, tmp / scratch name) below its
sweep root, is pruned from the walk, so test fixtures
living in scratch trees inside the workspace never appear
as live projects; slugs are unique — standalone clones
declaring the same slug fold into one project (the most
recently active root wins, the folded roots ride as
`also_at`), because slug-keyed navigation cannot address
two peers; and a checkout outranks a directory copy of
itself — a slug claimed by a git identity excludes
directory-identity claimants of that slug entirely (an
export copy never registers and never rides as
`also_at`), while a directory-identity project still
registers for any slug no checkout claims.
"""

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import util as util_mod
from .manifest import Manifest, ManifestError, load_manifest


def _is_scratch(here: Path, root: Path) -> bool:
    """True when a walked directory is scratch relative
    to its sweep root: carrying a scratch mark
    (dot-directory, tmp / scratch name) in any component
    BELOW the root, or sitting under a temp root BELOW
    the root. Containment is judged root-relative on
    purpose: a temp root that CONTAINS the sweep root
    (a test suite sweeping its own fixture workspace
    inside the system temp) convicts nothing — the
    fixtures are that sweep's whole world — while a
    temp root nested inside a live root (this box's
    disk-backed gate scratch under the workspace) is
    scratch inside it."""
    try:
        rel = here.relative_to(root)
    except ValueError:
        rel = here
    if util_mod.scratch_marked(rel):
        return True
    return any(
        t != root and (t == here or t in here.parents)
        and root in t.parents
        for t in util_mod.temp_roots())

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

DEFAULT_PRUNE = (".git", ".venv", ".venv311", "node_modules",
                 "__pycache__", "var", ".artifacts")


@dataclass
class Project:
    manifest: Manifest
    # Roots folded into this project by the slug fold
    # (standalone copies declaring the same slug): served
    # on the home row so the fold is visible, never a
    # second peer registration.
    also_at: list = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.manifest.slug

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def root(self) -> Path:
        return self.manifest.root

    def sections(self) -> dict:
        """Which viewer sections this project can feed.
        Sections degrade independently: a missing DB file is
        not an error, it is an absent section (the DB is
        created by `wb init` / first `wb add`)."""
        m = self.manifest
        return {
            "entries": m.registry is not None and m.registry.is_file(),
            "todos": m.registry is not None and m.registry.is_file(),
            "plans": m.plans is not None and m.plans.is_dir(),
            "registry_declared": m.registry is not None,
            "plans_declared": m.plans is not None,
        }


@dataclass
class SweepResult:
    projects: list = field(default_factory=list)   # of Project
    errors: list = field(default_factory=list)     # of dict

    def by_slug(self, slug: str) -> Project | None:
        for p in self.projects:
            if p.slug == slug:
                return p
        return None

    def summary(self) -> dict:
        return {
            "projects": [
                {"slug": p.slug, "name": p.name,
                 "root": str(p.root), "sections": p.sections(),
                 "also_at": [str(r) for r in p.also_at]}
                for p in self.projects
            ],
            "errors": self.errors,
        }


# Aggregate wall-clock budget for ONE sweep's git calls
# (wedge fix, 2026-11-10): the per-call timeout bounds a
# single child, but under a storage stall every call burns
# its full timeout in sequence — three identity calls per
# candidate times every candidate — and the sweep that
# should take seconds runs for minutes while every caller
# queues behind it (the 2026-11-10 capture: the sweep's
# git child parked in select, the whole server behind the
# compute lock). The healthy full sweep is ~1–3 s; the
# budget sits an order above it. When it is exhausted,
# remaining identity resolution degrades to directory
# identity (the _git None path) instead of queueing.
GIT_BUDGET_S = 20.0


def _git(root, *args, deadline=None) -> str | None:
    """One read-only git call (same posture as lib/worktrees:
    GIT_OPTIONAL_LOCKS=0, nothing writes). None on any
    failure — a non-git directory is a normal sweep input,
    never an error. With a deadline (the sweep's aggregate
    git budget), an exhausted budget returns None without
    spawning, and the per-call timeout shrinks to whatever
    budget remains, so one sweep's git work is bounded in
    aggregate, not just per call."""
    timeout = 5.0
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        timeout = min(timeout, remaining)
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=timeout,
            env=_GIT_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _repo_identity(root: Path, deadline=None):
    """(common_dir, is_main) if `root` is the top level of a
    git checkout, else None. The common dir is the repo's
    identity: a linked worktree's resolves back to the main
    checkout's .git, while its own git dir sits under
    .git/worktrees/<name> — so git_dir == common_dir exactly
    for the main checkout. A manifest dir that is merely
    INSIDE a repo (show-toplevel != root) returns None and
    keeps directory identity. An exhausted sweep budget
    (deadline) lands on the same None: identity degrades to
    the directory for this sweep only."""
    top = _git(root, "rev-parse", "--show-toplevel",
               deadline=deadline)
    gitdir = _git(root, "rev-parse", "--absolute-git-dir",
                  deadline=deadline)
    common = _git(root, "rev-parse", "--git-common-dir",
                  deadline=deadline)
    if top is None or gitdir is None or common is None:
        return None
    if Path(top.strip()).resolve() != root:
        return None
    common_path = Path(common.strip())
    if not common_path.is_absolute():
        common_path = root / common_path
    common_path = common_path.resolve()
    is_main = Path(gitdir.strip()).resolve() == common_path
    return common_path, is_main


def _main_checkout_root(root: Path, deadline=None) -> Path | None:
    """The main worktree's path for the repo at `root`
    (`worktree list` always lists it first), or None."""
    raw = _git(root, "worktree", "list", "--porcelain",
               deadline=deadline)
    if raw:
        for line in raw.splitlines():
            if line.startswith("worktree "):
                return Path(line[len("worktree "):]).resolve()
    return None


def _canonicalize(candidates, manifest_name: str,
                  result: SweepResult, deadline=None) -> None:
    """Collapse discovered manifests to one project per repo
    identity (see module docstring). The main checkout's
    manifest wins wherever it was discovered; worktree-only
    identities fall back to loading the main checkout's
    manifest from disk."""
    seen_roots = set()
    groups: dict = {}
    order: list = []
    for manifest in candidates:
        if manifest.root in seen_roots:
            continue  # same dir via overlapping sweep roots
        seen_roots.add(manifest.root)
        ident = _repo_identity(manifest.root, deadline=deadline)
        if ident is None:
            key, is_main = ("path", manifest.root), True
        else:
            key, is_main = ("git", ident[0]), ident[1]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((manifest, is_main))
    git_slugs = set()
    dir_projects = []
    for key in order:
        members = groups[key]
        main = next((m for m, is_main in members if is_main),
                    None)
        if main is not None:
            project = Project(main)
            result.projects.append(project)
            if key[0] == "git":
                git_slugs.add(project.slug)
            else:
                dir_projects.append(project)
            continue
        # Only linked worktrees discovered: the project is
        # their main checkout, if it carries a manifest.
        main_root = _main_checkout_root(members[0][0].root,
                                        deadline=deadline)
        if main_root is None:
            continue
        mpath = main_root / manifest_name
        if not mpath.is_file():
            continue
        try:
            manifest = load_manifest(mpath)
        except (ManifestError, OSError) as e:
            if not any(err.get("manifest") == str(mpath)
                       for err in result.errors):
                result.errors.append(
                    {"manifest": str(mpath), "error": str(e)})
        else:
            project = Project(manifest)
            result.projects.append(project)
            git_slugs.add(project.slug)
    # Export exclusion: a directory-identity project whose
    # slug a git identity claims in this same sweep is a
    # copy of that checkout (an export tree carries the
    # tracked manifest but is not the project) — drop it
    # outright, before the fold, so it never registers and
    # never rides on the checkout's `also_at`.
    # Directory-identity projects whose slug no checkout
    # claims are untouched.
    if dir_projects and git_slugs:
        excluded = {id(p) for p in dir_projects
                    if p.slug in git_slugs}
        if excluded:
            result.projects[:] = [
                p for p in result.projects
                if id(p) not in excluded]
    _fold_duplicate_slugs(result)


def _root_activity(root: Path) -> float:
    """A root's last-activity stamp for the slug fold:
    the newest of the manifest's mtime and the root's
    .git mtime (clone and commit activity both land
    there). 0.0 when nothing stats."""
    newest = 0.0
    for path in (root / "workbench.yaml", root / ".git"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            pass
    return newest


def _fold_duplicate_slugs(result: SweepResult) -> None:
    """One project per slug. Canonicalization keys on
    repo identity, so standalone clones of one project
    (each its own repo, each carrying a copy of the
    tracked manifest) still register once per clone
    under the same slug — and slug-keyed navigation
    lands on whichever the enumeration met first. Fold
    them: the most recently active root's project
    survives, and the folded roots ride on it as
    `also_at` — visible, never silent, never a second
    peer. The fold never deletes anything; a copy's
    removal is its owning work's act."""
    by_slug: dict = {}
    for project in result.projects:
        by_slug.setdefault(project.slug, []).append(project)
    survivors = []
    for slug, group in by_slug.items():
        if len(group) == 1:
            survivors.append(group[0])
            continue
        group.sort(key=lambda p: _root_activity(p.root),
                   reverse=True)
        winner = group[0]
        winner.also_at = sorted(
            [p.root for p in group[1:]]
            + [r for p in group[1:] for r in p.also_at],
            key=str)
        survivors.append(winner)
    result.projects[:] = survivors


def sweep(roots, manifest_name: str = "workbench.yaml",
          max_depth: int = 3, prune=DEFAULT_PRUNE,
          git_budget_s: float = GIT_BUDGET_S) -> SweepResult:
    # One aggregate deadline for every git call this sweep
    # makes (canonicalization); see GIT_BUDGET_S.
    deadline = time.monotonic() + git_budget_s
    result = SweepResult()
    prune_set = set(prune)
    candidates = []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            result.errors.append(
                {"root": str(root), "error": "sweep root missing"})
            continue
        base = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            depth = len(here.parts) - base
            if here != root and _is_scratch(here, root):
                # Scratch trees inside a swept root
                # (fixture checkouts under temp roots,
                # hidden or tmp/scratch-named trees)
                # never register: the walk prunes the
                # whole subtree without descending.
                dirnames[:] = []
                continue
            if manifest_name in filenames:
                mpath = here / manifest_name
                try:
                    candidates.append(load_manifest(mpath))
                except (ManifestError, OSError) as e:
                    result.errors.append(
                        {"manifest": str(mpath), "error": str(e)})
                dirnames[:] = []  # never descend into a repo
                continue
            if depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames
                               if d not in prune_set
                               and not d.startswith(".venv")]
    _canonicalize(candidates, manifest_name, result,
                  deadline=deadline)
    result.projects.sort(key=lambda p: p.slug)
    return result
