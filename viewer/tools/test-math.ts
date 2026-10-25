#!/usr/bin/env bun
// test-math.ts — the plan renderer's math + task-list
// pipeline (client/src/sections/plans/math.ts, consumed by
// PlanBody.tsx) against the shared conforming fixture
// (tests/fixtures/conforming-plan.md — the same file the
// parser tests pin): extraction finds exactly the fixture's
// real math (the code-span and price traps stay literal),
// every span renders through the lazy KaTeX import, the
// placeholder swap lands rendered math in marked's HTML,
// unparseable TeX throws (PlanBody then keeps the source
// text), \htmlClass under trust:false applies no class,
// and marked emits disabled checkboxes for the fixture's
// open questions.
//
// DOMPurify is inert without a DOM (isSupported is false
// under bun), so its retention of KaTeX markup is not
// re-proven here: PlanBody sanitizes each fragment and
// keeps the source text unless the fragment still carries
// class="katex — the guard is the proof obligation, and
// this tool pins everything up to it.
//
// Usage: bun viewer/tools/test-math.ts
// Exit 1 on any failure.

import { marked } from "marked";
import { extractMath, mathPlaceholderRe, renderMath } from "../client/src/sections/plans/math";

let failures = 0;
function check(name: string, ok: boolean, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` (${detail})` : ""}`);
  if (!ok) failures += 1;
}

const fixture = await Bun.file(
  new URL("../../tests/fixtures/conforming-plan.md", import.meta.url),
).text();

// -- extraction ------------------------------------------------------------
const { text: extracted, spans } = extractMath(fixture);
check(
  "extracts exactly the fixture's four math spans",
  spans.length === 4,
  `${spans.length} spans`,
);
check(
  "three inline + one display",
  spans.filter((s) => !s.display).length === 3 && spans.filter((s) => s.display).length === 1,
);
check(
  "display span is the weighted-mean formula",
  spans.some((s) => s.display && s.tex.includes("\\frac")),
);
check(
  "code-span and price traps stay literal",
  !spans.some((s) => s.tex.includes("costs") || s.tex.includes("total") || s.tex.includes("$")),
);
check(
  "every span left a placeholder",
  (extracted.match(/data-wb-math=/g) ?? []).length === spans.length,
);

// -- render + swap -----------------------------------------------------------
let html = marked.parse(extracted, { async: false }) as string;
for (let i = 0; i < spans.length; i++) {
  const span = spans[i] as (typeof spans)[number];
  const fragment = await renderMath(span.tex, span.display);
  check(`span ${i} renders KaTeX markup`, fragment.includes('class="katex'));
  html = html.replace(mathPlaceholderRe(i), () => fragment);
}
check("swap leaves no placeholders", !html.includes("data-wb-math"));
check("display math carries katex-display", html.includes("katex-display"));
check(
  "no fetchable references in rendered math",
  !/(src|href)\s*=|url\(/.test(html),
  "the MathML xmlns is an inert namespace identifier, never fetched",
);

// -- degradation + trust -------------------------------------------------------
let threw = false;
try {
  await renderMath("\\frac{1}{", false);
} catch {
  threw = true;
}
check("unparseable TeX throws (caller keeps the source text)", threw);

const untrusted = await renderMath("\\htmlClass{evil}{x}", false);
check(
  "\\htmlClass under trust:false applies no class",
  !untrusted.includes('class="evil"'),
  "the command renders as error-colored source text instead",
);

// -- task lists ------------------------------------------------------------------
const oq = fixture.split("## Open questions")[1]?.split("## Critical files")[0] ?? "";
const oqHtml = marked.parse(oq, { async: false }) as string;
const inputs = oqHtml.match(/<input[^>]*type="checkbox"[^>]*>/g) ?? [];
check("open questions render two checkbox inputs", inputs.length === 2, `${inputs.length} inputs`);
check(
  "every checkbox is disabled (read-only rendering)",
  inputs.every((t) => t.includes('disabled=""')),
);
check(
  "the answered question renders checked",
  inputs.some((t) => t.includes('checked=""')),
);

console.log(`test-math: ${failures} failure(s)`);
process.exit(failures ? 1 : 0);
