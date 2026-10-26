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
directory itself is the project.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import Manifest, ManifestError, load_manifest

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

DEFAULT_PRUNE = (".git", ".venv", ".venv311", "node_modules",
                 "__pycache__", "var", ".artifacts")


@dataclass
class Project:
    manifest: Manifest

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
            "mockups": m.registry is not None and m.registry.is_file(),
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
                 "root": str(p.root), "sections": p.sections()}
                for p in self.projects
            ],
            "errors": self.errors,
        }


def _git(root, *args) -> str | None:
    """One read-only git call (same posture as lib/worktrees:
    GIT_OPTIONAL_LOCKS=0, nothing writes). None on any
    failure — a non-git directory is a normal sweep input,
    never an error."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=5,
            env=_GIT_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _repo_identity(root: Path):
    """(common_dir, is_main) if `root` is the top level of a
    git checkout, else None. The common dir is the repo's
    identity: a linked worktree's resolves back to the main
    checkout's .git, while its own git dir sits under
    .git/worktrees/<name> — so git_dir == common_dir exactly
    for the main checkout. A manifest dir that is merely
    INSIDE a repo (show-toplevel != root) returns None and
    keeps directory identity."""
    top = _git(root, "rev-parse", "--show-toplevel")
    gitdir = _git(root, "rev-parse", "--absolute-git-dir")
    common = _git(root, "rev-parse", "--git-common-dir")
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


def _main_checkout_root(root: Path) -> Path | None:
    """The main worktree's path for the repo at `root`
    (`worktree list` always lists it first), or None."""
    raw = _git(root, "worktree", "list", "--porcelain")
    if raw:
        for line in raw.splitlines():
            if line.startswith("worktree "):
                return Path(line[len("worktree "):]).resolve()
    return None


def _canonicalize(candidates, manifest_name: str,
                  result: SweepResult) -> None:
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
        ident = _repo_identity(manifest.root)
        if ident is None:
            key, is_main = ("path", manifest.root), True
        else:
            key, is_main = ("git", ident[0]), ident[1]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((manifest, is_main))
    for key in order:
        members = groups[key]
        main = next((m for m, is_main in members if is_main),
                    None)
        if main is not None:
            result.projects.append(Project(main))
            continue
        # Only linked worktrees discovered: the project is
        # their main checkout, if it carries a manifest.
        main_root = _main_checkout_root(members[0][0].root)
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
            result.projects.append(Project(manifest))


def sweep(roots, manifest_name: str = "workbench.yaml",
          max_depth: int = 3, prune=DEFAULT_PRUNE) -> SweepResult:
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
    _canonicalize(candidates, manifest_name, result)
    result.projects.sort(key=lambda p: p.slug)
    return result
