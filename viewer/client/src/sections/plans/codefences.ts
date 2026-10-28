// Fenced code blocks in plan markdown get the shared
// highlight treatment (lib/highlight). Extraction pulls
// each fence out before marked runs — marked's own fence
// rendering is plain — and leaves a placeholder div whose
// content is the escaped source; PlanBody swaps each
// placeholder for highlighted markup once the lazy
// highlight.js chunk arrives. A fence that cannot be
// highlighted keeps its source text — the placeholder IS
// the degradation, the same contract math spans get.
// Extraction runs BEFORE math extraction, so a `$` inside
// a fence stays literal code, never a formula.

export interface CodeSpan {
  code: string;
  /** The fence's info string (first word), or null. */
  lang: string | null;
  /** The full source span, fences included. */
  raw: string;
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
};

function escapeHtml(text: string): string {
  return text.replace(/[&<>]/g, (c) => HTML_ESCAPES[c] ?? c);
}

/** The placeholder extractCode leaves for span `index`.
 * Its content is the escaped source with newlines encoded
 * as character references, so the placeholder is a single
 * line marked cannot split into blocks; before (or
 * without) highlighting the code still reads as written,
 * line breaks collapsed until the swap. */
export function codePlaceholder(index: number, raw: string): string {
  const body = escapeHtml(raw).replace(/\n/g, "&#10;");
  return `<div data-wb-code="${index}">${body}</div>`;
}

/** Matches one placeholder in marked + sanitized HTML.
 * The content can contain no markup (it was HTML-escaped
 * at extraction), so the first `</div>` closes it. */
export function codePlaceholderRe(index: number): RegExp {
  return new RegExp(`<div data-wb-code="${index}">[\\s\\S]*?</div>`);
}

const FENCE_OPEN = /^ {0,3}(`{3,}|~{3,})[ \t]*(.*)$/;

export function extractCode(text: string): { text: string; spans: CodeSpan[] } {
  const spans: CodeSpan[] = [];
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const open = FENCE_OPEN.exec(lines[i] as string);
    if (!open) {
      out.push(lines[i] as string);
      i += 1;
      continue;
    }
    const marker = open[1] as string;
    const ch = marker[0] as string;
    const info = (open[2] ?? "").trim().split(/\s+/)[0] ?? "";
    const closeRe = new RegExp(`^ {0,3}${ch === "`" ? "`" : "~"}{${marker.length},}[ \\t]*$`);
    const body: string[] = [];
    let j = i + 1;
    let closed = false;
    while (j < lines.length) {
      if (closeRe.test(lines[j] as string)) {
        closed = true;
        break;
      }
      body.push(lines[j] as string);
      j += 1;
    }
    const rawLines = lines.slice(i, closed ? j + 1 : lines.length);
    const raw = rawLines.join("\n");
    spans.push({ code: body.join("\n"), lang: info || null, raw });
    out.push("", codePlaceholder(spans.length - 1, raw), "");
    i = closed ? j + 1 : lines.length;
  }
  return { text: out.join("\n"), spans };
}
