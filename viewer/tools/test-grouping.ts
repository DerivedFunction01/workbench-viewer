#!/usr/bin/env bun
// test-grouping.ts — the Plans-list grouping derivation
// (client/src/sections/plans/grouping.ts, repo-home
// spec §21) against the fixture family the feed tests
// pin (tests/test_plan_grouping.py), plus the cycle and
// self-declaration families. Every case asserts the
// entry shape the list renders: top-level membership,
// nested children in declaration order, missing rows,
// and the resolved count each row carries.
//
// Usage: bun viewer/tools/test-grouping.ts
// Exit 1 on any failure.

import type { BundleItem, PlanSummary } from "../client/src/lib/api";
import { groupBundles, type PlanGrouping } from "../client/src/sections/plans/grouping";

function bundle(path: string, subplans: string[], archived = false): BundleItem {
  const plan: PlanSummary = {
    path,
    title: `Plan ${path}`,
    status_raw: archived ? "complete" : "in progress",
    status_bucket: archived ? "done" : "doing",
    conforming: true,
    step_count: 0,
    open_questions_count: 0,
    subplans,
    subplans_count: subplans.length,
    mermaid_count: 0,
    archived,
    modified: 0,
  };
  return {
    kind: "flat-plan",
    id: path,
    slug: path.replace(/\.md$/, ""),
    path,
    archived,
    feature: null,
    plan,
    todos: [],
    errors: [],
    todo_count: 0,
    open_count: 0,
  };
}

let failures = 0;
function check(name: string, ok: boolean, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${ok ? "" : ` (${detail})`}`);
  if (!ok) failures += 1;
}

function topPaths(g: PlanGrouping): string[] {
  return g.topLevel.map((e) => e.bundle.plan?.path ?? e.bundle.path);
}

function childPaths(g: PlanGrouping, parentPath: string): string[] {
  const entry = g.byPlanPath.get(parentPath);
  return (entry?.children ?? []).map((c) => c.plan?.path ?? c.path);
}

// The fixture family: a declaring parent (active child,
// finished child, missing path, self), a nested child
// with its own subplan, and a rival parent declaring
// the same child second.
const family = [
  bundle("parent.md", ["child.md", "finished/fin-child.md", "gone.md", "parent.md"]),
  bundle("child.md", ["grandchild.md"]),
  bundle("grandchild.md", []),
  bundle("rival.md", ["child.md"]),
  bundle("finished/fin-child.md", [], true),
];
const g = groupBundles(family);

check(
  "parent is top-level; claimed children and grandchild are not",
  JSON.stringify(topPaths(g)) === JSON.stringify(["parent.md", "rival.md"]),
  `topLevel=${topPaths(g)}`,
);
check(
  "children nest in declaration order, finished child included",
  JSON.stringify(childPaths(g, "parent.md")) ===
    JSON.stringify(["child.md", "finished/fin-child.md"]),
  `children=${childPaths(g, "parent.md")}`,
);
const parent = g.byPlanPath.get("parent.md");
check(
  "missing row names the vanished path; self is not missing",
  JSON.stringify(parent?.missing) === JSON.stringify(["gone.md"]),
  `missing=${parent?.missing}`,
);
check(
  "parent count excludes self and the missing path",
  parent?.resolvedCount === 2,
  `resolvedCount=${parent?.resolvedCount}`,
);
const child = g.byPlanPath.get("child.md");
check(
  "nested child carries its own count but nests nothing (one level)",
  child?.resolvedCount === 1 && child?.children.length === 0,
  `child count=${child?.resolvedCount} children=${child?.children.length}`,
);
const rival = g.byPlanPath.get("rival.md");
check(
  "two-parent child nests under the first declaring parent only",
  rival?.resolvedCount === 1 && rival?.children.length === 0 && rival?.missing.length === 0,
  `rival count=${rival?.resolvedCount} children=${rival?.children.length}`,
);
check(
  "finished child nests with its archived status intact",
  g.byPlanPath.get("finished/fin-child.md")?.bundle.archived === true,
);

// Cycle family: a declares b, b declares a. Feed order
// breaks it — a stays top-level, b nests, nothing lost.
const cycle = groupBundles([bundle("a.md", ["b.md"]), bundle("b.md", ["a.md"])]);
check(
  "cycle breaks at the already-nested node",
  JSON.stringify(topPaths(cycle)) === JSON.stringify(["a.md"]) &&
    JSON.stringify(childPaths(cycle, "a.md")) === JSON.stringify(["b.md"]),
  `topLevel=${topPaths(cycle)} children=${childPaths(cycle, "a.md")}`,
);
check(
  "cycle member counts its resolvable declaration without nesting it",
  cycle.byPlanPath.get("b.md")?.resolvedCount === 1,
  `b count=${cycle.byPlanPath.get("b.md")?.resolvedCount}`,
);

// Self-only family: a plan declaring only itself is a
// plain single item — no group shell, no count.
const solo = groupBundles([bundle("solo.md", ["solo.md"])]);
const soloEntry = solo.byPlanPath.get("solo.md");
check(
  "self-declaration renders as a single item",
  solo.topLevel.length === 1 &&
    soloEntry?.resolvedCount === 0 &&
    soloEntry?.children.length === 0 &&
    soloEntry?.missing.length === 0,
  `top=${solo.topLevel.length} count=${soloEntry?.resolvedCount}`,
);

console.log(`test-grouping: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
