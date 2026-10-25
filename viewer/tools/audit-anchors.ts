#!/usr/bin/env bun
// audit-anchors.ts — the §14 anchor leg for the Plans
// and Mockups sections (annotation plan step 8): every
// component an annotation can name must actually render
// its data-anchor id — plan sections, step blocks,
// tables, diagrams, the exhibit stage, and every
// drill-in card. The audit enumerates the anchor sites
// in the section sources and asserts the required set;
// a missing site fails the audit (fix by ADDING the
// anchor via the kit `anchor` prop / anchors.ts — never
// by exempting the component here).
//
// Usage: bun viewer/tools/audit-anchors.ts
// Exit 1 on any failure.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel: string) => readFileSync(join(here, "..", "client", "src", rel), "utf8");

const PLANS = read("sections/Plans.tsx");
const PLAN_BODY = read("sections/plans/PlanBody.tsx");
const MOCKUPS = read("sections/Mockups.tsx");
const DETAIL = read("sections/mockups/MockupDetail.tsx");

/** Required anchor sites: [description, source, pattern]. */
const REQUIRED: [string, string, RegExp][] = [
  ["plan list", PLANS, /data-anchor=\{anchor\.planList\}/],
  ["plan reader root", PLANS, /data-anchor=\{anchor\.planReader\}/],
  ["plan header table", PLANS, /data-anchor=\{anchor\.planHeader\}/],
  ["plan section (per heading)", PLANS, /data-anchor=\{sectionAnchor\}/],
  ["step block", PLAN_BODY, /data-anchor=\{anchor\.step\(step\.n\)\}/],
  [
    "table in markdown",
    PLAN_BODY,
    /<table data-anchor="\$\{anchor\.table\(sectionHeading, tableIndex\)\}">/,
  ],
  ["diagram figure", PLAN_BODY, /data-anchor=\{anchor\.diagram\(sectionHeading, index\)\}/],
  ["mockups triage lane", MOCKUPS, /data-anchor="mockups\/triage-lane"/],
  ["mockups storyboard grid", MOCKUPS, /data-anchor="mockups\/storyboard-grid"/],
  ["mockups contact sheet", MOCKUPS, /data-anchor="mockups\/contact-sheet"/],
  ["entry sheet", DETAIL, /data-anchor="mockups\/entry-sheet"/],
  ["exhibit stage (Frame)", DETAIL, /anchor="mockups\/exhibit-stage"/],
  ["disposition card", DETAIL, /anchor="mockups\/disposition"/],
  ["metadata card", DETAIL, /anchor="mockups\/metadata-card"/],
  ["state card / controls", DETAIL, /anchor="mockups\/state-card"/],
  ["approval card", DETAIL, /anchor="mockups\/approval-card"/],
  ["lifecycle card", DETAIL, /anchor="mockups\/lifecycle-card"/],
  ["annotations card", DETAIL, /anchor="mockups\/annotations-card"/],
  ["files card", DETAIL, /data-anchor="mockups\/files-card"/],
  ["review log card", DETAIL, /data-anchor="mockups\/review-log-card"/],
  ["history card", DETAIL, /data-anchor="mockups\/history-card"/],
];

let failures = 0;
for (const [name, source, pattern] of REQUIRED) {
  const ok = pattern.test(source);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}`);
  if (!ok) failures += 1;
}

// Every component id the drill-in renders must have a
// display label in COMPONENT_LABELS (the stored label
// snapshot an annotation carries) — except the
// annotations card, which is annotation UI itself and
// can never be selected.
const labelBlock = DETAIL.match(/COMPONENT_LABELS[^}]*}/s)?.[0] ?? "";
const rendered = new Set(
  [...DETAIL.matchAll(/(?:data-anchor|anchor)="(mockups\/[a-z-]+)"/g)].map((m) => m[1] as string),
);
for (const id of rendered) {
  if (id === "mockups/annotations-card") continue;
  const ok = labelBlock.includes(`"${id}"`);
  console.log(`${ok ? "PASS" : "FAIL"} label for ${id}`);
  if (!ok) failures += 1;
}

console.log(
  `audit-anchors: ${REQUIRED.length} required sites, ` +
    `${rendered.size} drill-in component ids enumerated, ${failures} failure(s)`,
);
process.exit(failures ? 1 : 0);
