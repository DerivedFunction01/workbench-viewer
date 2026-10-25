// relocation.ts — the CLIENT mirror of lib/annotations.py
// (repo-home spec §12): ONE algorithm, two
// implementations, pinned identical by the shared
// fixtures in tests/fixtures/relocation.json (run:
// bun viewer/tools/test-relocation.ts). Given a stored
// selection payload and the text of its enclosing
// component, find the quote again after edits: the text
// is whitespace-normalized (every whitespace run —
// newlines, NBSP — collapses to one space, ends trimmed;
// matching is case-sensitive) and duplicate hits are
// disambiguated by the stored prefix/suffix context. A
// tie at the best score is "ambiguous"; zero hits is
// "orphan"; both surface as anchor-moved — never a
// guessed position, never a dropped annotation. Status
// is derived at read, never stored.

import type { TextSelection } from "../../lib/api";

export type RelocationStatus = "located" | "orphan" | "ambiguous";

export interface RelocationResult {
  status: RelocationStatus;
  /** Raw-text offsets of the located span (located only):
   * start = the quote's first character, end = just past
   * its last character. */
  start: number;
  end: number;
}

export function normalizeText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

interface NormMap {
  norm: string;
  /** map[i] = raw offset at which normalized char i
   * begins (a collapsed whitespace run maps to its FIRST
   * raw character). Aligned 1:1 with norm — no sentinel. */
  map: number[];
}

/** Normalize with a raw-offset map (mirrors the lib's
 * _normalize_with_map exactly: a pending-space model —
 * leading/trailing runs emit nothing). */
export function normalizeWithMap(text: string): NormMap {
  const out: string[] = [];
  const map: number[] = [];
  let pending: number | null = null;
  for (let i = 0; i < text.length; i++) {
    const ch = text.charAt(i);
    if (/\s/.test(ch)) {
      if (out.length > 0 && pending === null) pending = i;
      continue;
    }
    if (pending !== null) {
      out.push(" ");
      map.push(pending);
      pending = null;
    }
    out.push(ch);
    map.push(i);
  }
  return { norm: out.join(""), map };
}

function occurrences(haystack: string, needle: string): number[] {
  const out: number[] = [];
  if (!needle) return out;
  let idx = haystack.indexOf(needle);
  while (idx !== -1) {
    out.push(idx);
    idx = haystack.indexOf(needle, idx + 1);
  }
  return out;
}

/** Context score (the lib's rule verbatim): prefix AND
 * suffix = 3, prefix only = 2, suffix only = 1, bare =
 * 0. The match tolerates the single separator space
 * normalization leaves at the boundary: the stored
 * context is end-trimmed by normalizeText, so one space
 * is stripped from the SOURCE side before the exact
 * comparison. */
function contextScore(
  norm: string,
  start: number,
  quoteLength: number,
  nprefix: string,
  nsuffix: string,
): number {
  let before = norm.slice(0, start);
  if (before.endsWith(" ")) before = before.slice(0, -1);
  let after = norm.slice(start + quoteLength);
  if (after.startsWith(" ")) after = after.slice(1);
  const pre = nprefix !== "" && before.endsWith(nprefix);
  const suf = nsuffix !== "" && after.startsWith(nsuffix);
  return pre && suf ? 3 : pre ? 2 : suf ? 1 : 0;
}

/** Locate the selection's quote inside ONE text (the
 * enclosing component's text). Mirrors the lib's relocate
 * over a single region. */
export function locateInText(text: string, selection: TextSelection): RelocationResult {
  const miss: RelocationResult = { status: "orphan", start: 0, end: 0 };
  const quote = normalizeText(selection.quote ?? "");
  if (!quote) return miss;
  const { norm, map } = normalizeWithMap(text);
  const nprefix = normalizeText(selection.prefix ?? "");
  const nsuffix = normalizeText(selection.suffix ?? "");
  const hits = occurrences(norm, quote);
  if (hits.length === 0) return miss;
  let best = -1;
  let winners: number[] = [];
  for (const at of hits) {
    const score = contextScore(norm, at, quote.length, nprefix, nsuffix);
    if (score > best) {
      best = score;
      winners = [at];
    } else if (score === best) {
      winners.push(at);
    }
  }
  if (winners.length !== 1) return { status: "ambiguous", start: 0, end: 0 };
  const at = winners[0] as number;
  const end = at + quote.length;
  return {
    status: "located",
    start: map[at] as number,
    end: (map[end - 1] as number) + 1,
  };
}

/** The scoped lookup (mirrors the lib's scoping rule):
 * try the stated component first; when the component id
 * is ABSENT, widen once to the whole document and flag
 * componentMissing. A present component with no hit does
 * NOT widen. */
export function relocateInComponents(
  components: { id: string; text: string }[],
  selection: TextSelection,
): RelocationResult & { componentMissing: boolean } {
  const scoped = components.find((c) => c.id === selection.component_id);
  if (scoped) {
    return { ...locateInText(scoped.text, selection), componentMissing: false };
  }
  const joined = components.map((c) => c.text).join("\n");
  return { ...locateInText(joined, selection), componentMissing: true };
}
