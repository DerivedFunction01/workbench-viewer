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
another-project carries no manifest and is therefore invisible —
excluded by design, not by a special case here.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import Manifest, ManifestError, load_manifest

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


def sweep(roots, manifest_name: str = "workbench.yaml",
          max_depth: int = 3, prune=DEFAULT_PRUNE) -> SweepResult:
    result = SweepResult()
    prune_set = set(prune)
    seen_roots = set()
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
                    manifest = load_manifest(mpath)
                except (ManifestError, OSError) as e:
                    result.errors.append(
                        {"manifest": str(mpath), "error": str(e)})
                else:
                    if manifest.root not in seen_roots:
                        seen_roots.add(manifest.root)
                        result.projects.append(Project(manifest))
                dirnames[:] = []  # never descend into a repo
                continue
            if depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames
                               if d not in prune_set
                               and not d.startswith(".venv")]
    result.projects.sort(key=lambda p: p.slug)
    return result
