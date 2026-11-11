#!/usr/bin/env bun
// verify-contrast.mjs — the contrast discipline, rerunnable.
//
// Part 1 (Subplan-02): every status TEXT token must hold
// >= 4.5:1 (WCAG AA, normal text) against EVERY surface
// token, in both palettes x both modes. Status hues (glyph
// + border) are graphical and are NOT text-verified — the
// shipped set establishes exactly this split (e.g. stale's
// orange hue sits at ~2.3:1 on white while its text variant
// holds 5.3:1+). Alias texts (var(--wb-status-<other>-text))
// resolve to their target before checking.
//
// Part 2 (scanner rule 1 of the 2026-11-10 entries critic
// pass): the CONTENT tokens join the net. --wb-content-
// primary and --wb-content-secondary are the essential-
// content voices and must hold >= 4.5:1 against every
// surface token, both palettes x both modes — that bar is
// FATAL. --wb-content-muted is the declared META-ONLY voice
// (ui-context: meta only, never essential content alone):
// its pairs are REPORTED with their measured ratios, and
// the only muted failure is a drop below a minimum the
// fundamentals actually document — 3.4:1 on surface-1 in
// light mode (ui-context records muted as 3.4:1 / 4.4:1 on
// surface-1). Pairs with no documented claim behind them —
// the light-mode sunken pairs included (measured 2.91:1
// olive, 2.96:1 teal) — are recorded as measured ratios
// with no claimed minimum, report-only, never fatal. The
// role split is the rule: essential content must never sit
// in a voice the checker itself grades as meta-only.
// (Grading ratified by the parent under q1 +
// Fundamentals-First, 2026-11-10: no invented floor.)
//
// Usage: bun viewer/tools/verify-contrast.mjs [--verbose]
// Exit 1 on any failure.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tokens = JSON.parse(readFileSync(join(here, "..", "..", "tokens", "tokens.json"), "utf8"));
const verbose = process.argv.includes("--verbose");
const SURFACES = ["canvas", "1", "2", "3", "sunken"];

function lin(channel) {
  const c = channel / 255;
  return c > 0.04045 ? ((c + 0.055) / 1.055) ** 2.4 : c / 12.92;
}

function luminance(hex) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function ratio(fg, bg) {
  let [l1, l2] = [luminance(fg), luminance(bg)];
  if (l1 < l2) [l1, l2] = [l2, l1];
  return (l1 + 0.05) / (l2 + 0.05);
}

// Resolve a status text $value to a hex: literal, a DTCG
// alias into primitive/status, or a var(--wb-status-*-text)
// reference to another status's same-mode text.
function resolveText(raw, mode, seen = new Set()) {
  if (raw.startsWith("#")) return raw;
  const alias = raw.match(/^var\(--wb-status-([a-z-]+)-text\)$/);
  if (alias) {
    if (seen.has(alias[1])) throw new Error(`alias loop: ${raw}`);
    seen.add(alias[1]);
    return resolveText(tokens.status[alias[1]].text[mode].$value, mode, seen);
  }
  const dtcg = raw.match(/^\{(.+)\}$/);
  if (dtcg) {
    let node = tokens;
    for (const part of dtcg[1].split(".")) node = node[part];
    return resolveText(node.$value, mode, seen);
  }
  throw new Error(`cannot resolve status text value: ${raw}`);
}

let failures = 0;
let checked = 0;
for (const [name, st] of Object.entries(tokens.status)) {
  if (name === "chart") continue;
  for (const mode of ["light", "dark"]) {
    const text = resolveText(st.text[mode].$value, mode);
    for (const palette of Object.keys(tokens.semantic)) {
      for (const surface of SURFACES) {
        const bg = tokens.semantic[palette][mode].surface[surface].$value;
        const r = ratio(text, bg);
        checked += 1;
        const ok = r >= 4.5;
        if (!ok) failures += 1;
        if (verbose || !ok) {
          console.log(
            `${ok ? "PASS" : "FAIL"} status-${name} text ${text} on ` +
              `${palette}/${mode}/surface-${surface} ${bg}: ${r.toFixed(2)}:1`,
          );
        }
      }
    }
  }
}
// Part 2 — content tokens x surfaces (scanner rule 1).
// Essential voices (primary, secondary) are content and
// hold the AA bar on every surface, fatally. Muted is
// meta-only: every pair is reported with its measured
// ratio; a pair fails ONLY below a documented minimum.
// The fundamentals document exactly one muted minimum:
// 3.4:1 on surface-1 in light mode (both palettes share
// the documented surface-1 reading). Every other muted
// pair — sunken included — carries no claimed minimum
// and is report-only.
const ESSENTIAL_VOICES = ["primary", "secondary"];
const MUTED_DOCUMENTED_MINIMA = { "light/1": 3.4 };
let contentChecked = 0;
let contentFailures = 0;
for (const palette of Object.keys(tokens.semantic)) {
  for (const mode of ["light", "dark"]) {
    const content = tokens.semantic[palette][mode].content;
    for (const voice of [...ESSENTIAL_VOICES, "muted"]) {
      const text = content[voice].$value;
      for (const surface of SURFACES) {
        const bg = tokens.semantic[palette][mode].surface[surface].$value;
        const r = ratio(text, bg);
        contentChecked += 1;
        if (voice === "muted") {
          const minimum = MUTED_DOCUMENTED_MINIMA[`${mode}/${surface}`];
          if (minimum === undefined) {
            console.log(
              `REPORT content-muted (meta-only) ${text} on ` +
                `${palette}/${mode}/surface-${surface} ${bg}: ${r.toFixed(2)}:1 ` +
                `(measured; no claimed minimum; report-only)`,
            );
          } else {
            const ok = r >= minimum;
            if (!ok) contentFailures += 1;
            console.log(
              `${ok ? "PASS" : "FAIL"} content-muted (meta-only) ${text} on ` +
                `${palette}/${mode}/surface-${surface} ${bg}: ${r.toFixed(2)}:1 ` +
                `(documented minimum ${minimum}:1 on surface-1 light)`,
            );
          }
        } else {
          const ok = r >= 4.5;
          if (!ok) contentFailures += 1;
          if (verbose || !ok) {
            console.log(
              `${ok ? "PASS" : "FAIL"} content-${voice} ${text} on ` +
                `${palette}/${mode}/surface-${surface} ${bg}: ${r.toFixed(2)}:1`,
            );
          }
        }
      }
    }
  }
}

console.log(
  `verify-contrast: ${checked} status-text/surface pairs checked, ` +
    `${contentChecked} content/surface pairs checked, ` +
    `${failures + contentFailures} failure(s)`,
);
process.exit(failures || contentFailures ? 1 : 0);
