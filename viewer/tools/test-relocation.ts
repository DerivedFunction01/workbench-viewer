#!/usr/bin/env bun
// test-relocation.ts — the client re-location mirror
// (client/src/sections/plans/relocation.ts) against the
// SHARED fixtures the lib is pinned by
// (tests/fixtures/relocation.json): same cases, same
// assertions as tests/test_annotations.py's
// TestRelocateFixtures — status equality, and for located
// cases the span's normalized text equals the normalized
// quote. One algorithm, two implementations (spec §12).
//
// Usage: bun viewer/tools/test-relocation.ts
// Exit 1 on any failure.

import fixtures from "../../tests/fixtures/relocation.json";
import type { TextSelection } from "../client/src/lib/api";
import { locateInText, normalizeText } from "../client/src/sections/plans/relocation";

interface FixtureCase {
  name: string;
  expect: string;
  selection: TextSelection;
  source: string;
}

const cases = (fixtures as { cases: FixtureCase[] }).cases;
let failures = 0;
for (const c of cases) {
  const result = locateInText(c.source, c.selection);
  let ok = result.status === c.expect;
  let detail = `status ${result.status}`;
  if (ok && c.expect === "located") {
    const matched = normalizeText(c.source.slice(result.start, result.end));
    const want = normalizeText(c.selection.quote ?? "");
    ok = matched === want;
    detail += ok ? "" : `; span text "${matched}" != quote "${want}"`;
  }
  console.log(`${ok ? "PASS" : "FAIL"} ${c.name} (${detail})`);
  if (!ok) failures += 1;
}
console.log(`test-relocation: ${cases.length} cases, ${failures} failure(s)`);
process.exit(failures ? 1 : 0);
