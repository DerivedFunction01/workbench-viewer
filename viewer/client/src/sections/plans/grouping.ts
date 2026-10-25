// grouping.ts — plan grouping for the Plans list
// (repo-home spec §21): presentation derived at read
// from the parent's `## Subplans` declaration, never
// stored. A plan that declares at least one resolvable
// subplan renders as a group — its children nested one
// level beneath it; a plan with no subplans renders as
// its own item; a declared child never also renders as
// a top-level row. One level only: a nested child's own
// subplans are counted on its row and reachable from
// its reader, not nested further here.
//
// Claiming (which parent a child nests under) follows
// feed order: the first declaring parent wins. A plan
// declaring itself is ignored. A declaration that
// would close a cycle is not claimed — it stays a
// plain reference in the declaring plan's reader. A
// declared path that resolves to no plan in the set
// is the parent's missing child row, never dropped.

import type { BundleItem } from "../../lib/api";

export interface PlanGroupEntry {
  bundle: BundleItem;
  /** The plan paths this bundle's plan declares, in
   * declaration order ([] when it has no plan or no
   * `## Subplans` section). */
  declared: string[];
  /** Declared paths — self excluded — that resolve to
   * a plan in the set: the subplan count a row carries. */
  resolvedCount: number;
  /** Child bundles nested under this one in the list.
   * Top-level entries only; a nested entry's children
   * stay empty (one level of nesting). */
  children: BundleItem[];
  /** Declared paths resolving to nothing, in
   * declaration order. Top-level entries only. */
  missing: string[];
}

export interface PlanGrouping {
  /** One entry per bundle, in feed order. */
  entries: PlanGroupEntry[];
  /** Entries no plan claims as a subplan — the rows
   * the list renders at the top level, feed order. */
  topLevel: PlanGroupEntry[];
  /** Entry lookup by plan path (plan-less bundles are
   * absent). */
  byPlanPath: Map<string, PlanGroupEntry>;
}

function declaredOf(bundle: BundleItem): string[] {
  return bundle.plan?.subplans ?? [];
}

export function groupBundles(bundles: BundleItem[]): PlanGrouping {
  const byPlanPath = new Map<string, BundleItem>();
  for (const bundle of bundles) {
    if (bundle.plan) byPlanPath.set(bundle.plan.path, bundle);
  }

  // Claiming: parents in feed order, declarations in
  // their own order; the first claim wins.
  const claimedBy = new Map<string, string>();
  for (const bundle of bundles) {
    const own = bundle.plan?.path;
    if (!own) continue;
    for (const target of declaredOf(bundle)) {
      if (target === own) continue; // self: ignored
      if (!byPlanPath.has(target)) continue; // missing
      if (claimedBy.has(target)) continue; // first wins
      // Cycle check: claiming closes a loop when the
      // target is already an ancestor of this plan.
      let cycle = false;
      let cursor = claimedBy.get(own);
      while (cursor !== undefined) {
        if (cursor === target) {
          cycle = true;
          break;
        }
        cursor = claimedBy.get(cursor);
      }
      if (cycle) continue;
      claimedBy.set(target, own);
    }
  }

  const entries: PlanGroupEntry[] = bundles.map((bundle) => {
    const own = bundle.plan?.path;
    const declared = declaredOf(bundle);
    // A path declared twice is one subplan: the count,
    // the nested rows, and the missing rows are built
    // from distinct declarations (first occurrence
    // wins); `declared` itself stays faithful.
    const distinct = [...new Set(declared)];
    const resolvedCount = distinct.filter((t) => t !== own && byPlanPath.has(t)).length;
    const claimed = own !== undefined && claimedBy.has(own);
    const entry: PlanGroupEntry = {
      bundle,
      declared,
      resolvedCount,
      children: [],
      missing: [],
    };
    if (!claimed && own !== undefined) {
      for (const target of distinct) {
        if (claimedBy.get(target) === own) {
          const child = byPlanPath.get(target);
          if (child) entry.children.push(child);
        }
        if (target !== own && !byPlanPath.has(target)) {
          entry.missing.push(target);
        }
      }
    }
    return entry;
  });

  const entryByPlanPath = new Map<string, PlanGroupEntry>();
  for (const entry of entries) {
    if (entry.bundle.plan) {
      entryByPlanPath.set(entry.bundle.plan.path, entry);
    }
  }
  return {
    entries,
    topLevel: entries.filter((e) => !e.bundle.plan || !claimedBy.has(e.bundle.plan.path)),
    byPlanPath: entryByPlanPath,
  };
}
