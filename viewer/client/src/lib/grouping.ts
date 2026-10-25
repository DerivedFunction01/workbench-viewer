// Grouped worktree presentation (repo-home spec §19,
// the owner's ruling): wherever worktrees are listed, a repo
// renders as a GROUP — the repo item itself is the main
// checkout, linked worktrees nest UNDER it as children; a
// repo with no linked worktrees is its own single item,
// never an empty group shell.
//
// This is presentation only, shaped here in the client
// from the project -> worktrees relation the /api/home
// payload already carries (row.worktrees[].path against
// each swept project's root). The lib derivations, the
// endpoints, and the sweep itself are unchanged: the
// sweep still lists a worktree copy that carries a
// manifest as its own project (the flat-sibling
// anti-pattern §19 names) — grouping is what the reader
// sees, and it keys on ROOTS, not slugs, because a repo
// and its worktree copy can share a slug.

import type { HomeRow, ProjectSummary } from "./api";

export interface ProjectGroup {
  project: ProjectSummary;
  /** Swept projects that are this repo's linked worktrees. */
  children: ProjectSummary[];
}

export function groupProjects(
  projects: ProjectSummary[],
  homeRows: HomeRow[] | null,
): ProjectGroup[] {
  const flat = () => projects.map((project) => ({ project, children: [] }));
  if (!homeRows) return flat();
  const parentRootByWorktreePath = new Map<string, string>();
  for (const row of homeRows) {
    for (const worktree of row.worktrees) {
      if (!worktree.is_main) {
        parentRootByWorktreePath.set(worktree.path, row.root);
      }
    }
  }
  const roots = new Set(projects.map((p) => p.root));
  const childrenOf = new Map<string, ProjectSummary[]>();
  const childRoots = new Set<string>();
  for (const project of projects) {
    const parentRoot = parentRootByWorktreePath.get(project.root);
    if (parentRoot && parentRoot !== project.root && roots.has(parentRoot)) {
      childRoots.add(project.root);
      childrenOf.set(parentRoot, [...(childrenOf.get(parentRoot) ?? []), project]);
    }
  }
  if (childRoots.size === 0) return flat();
  return projects
    .filter((project) => !childRoots.has(project.root))
    .map((project) => ({
      project,
      children: childrenOf.get(project.root) ?? [],
    }));
}
