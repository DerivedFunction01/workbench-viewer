// Math in plan markdown (plan syntax standard: `$...$`
// inline, `$$...$$` display — no other delimiter forms).
// Extraction is a small scanner over a markdown block's
// text: inline code spans and `\$` are never math, and the
// inline heuristic (no surrounding spaces, no digit right
// after the closing `$`) keeps prices like "$5 and $10"
// literal. Extracted spans become placeholder <span>s in
// the text marked parses; PlanBody swaps each placeholder
// for KaTeX output once the lazy chunk arrives. A span that
// fails to render keeps its source text — the placeholder's
// content IS the source — the same degradation mermaid
// diagrams get (founding Step 6).

export interface MathSpan {
  tex: string;
  display: boolean;
  /** The full source span, delimiters included. */
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

/** The placeholder extractMath leaves for span `index`. Its
 * text content is the escaped source span, so before (or
 * without) KaTeX the formula still reads as written. */
export function mathPlaceholder(index: number, raw: string): string {
  return `<span data-wb-math="${index}">${escapeHtml(raw)}</span>`;
}

/** Matches one placeholder in marked + sanitized HTML. The
 * content can contain no markup (it was HTML-escaped at
 * extraction), so the first `</span>` closes it. */
export function mathPlaceholderRe(index: number): RegExp {
  return new RegExp(`<span data-wb-math="${index}">[\\s\\S]*?</span>`);
}

export function extractMath(text: string): { text: string; spans: MathSpan[] } {
  const spans: MathSpan[] = [];
  let out = "";
  let i = 0;
  while (i < text.length) {
    const ch = text[i] as string;
    if (ch === "\\" && text[i + 1] === "$") {
      out += "\\$";
      i += 2;
      continue;
    }
    if (ch === "`") {
      let n = 1;
      while (text[i + n] === "`") n += 1;
      const ticks = "`".repeat(n);
      const close = text.indexOf(ticks, i + n);
      if (close === -1) {
        out += ticks;
        i += n;
      } else {
        out += text.slice(i, close + n);
        i = close + n;
      }
      continue;
    }
    if (ch === "$" && text[i + 1] === "$") {
      const close = text.indexOf("$$", i + 2);
      const tex = close === -1 ? "" : text.slice(i + 2, close);
      if (close !== -1 && tex.trim()) {
        const raw = text.slice(i, close + 2);
        out += mathPlaceholder(spans.length, raw);
        spans.push({ tex, display: true, raw });
        i = close + 2;
      } else {
        out += "$$";
        i += 2;
      }
      continue;
    }
    if (ch === "$") {
      const lineEnd = text.indexOf("\n", i);
      const bound = lineEnd === -1 ? text.length : lineEnd;
      const close = text.indexOf("$", i + 1);
      const tex = close === -1 ? "" : text.slice(i + 1, close);
      const after = close === -1 ? "" : (text[close + 1] ?? "");
      if (
        close !== -1 &&
        close < bound &&
        tex !== "" &&
        !/^\s/.test(tex) &&
        !/\s$/.test(tex) &&
        !/[0-9]/.test(after)
      ) {
        const raw = text.slice(i, close + 1);
        out += mathPlaceholder(spans.length, raw);
        spans.push({ tex, display: false, raw });
        i = close + 1;
      } else {
        out += "$";
        i += 1;
      }
      continue;
    }
    out += ch;
    i += 1;
  }
  return { text: out, spans };
}

/** Render one span with KaTeX, loaded lazily through a
 * dynamic import — a plan with no math never loads the
 * chunk, exactly the mermaid arrangement. trust stays off
 * (plan text gets no \htmlClass-style escapes) and errors
 * throw, so the caller falls back to the source text. */
export async function renderMath(tex: string, display: boolean): Promise<string> {
  const katex = (await import("katex")).default;
  return katex.renderToString(tex, {
    displayMode: display,
    throwOnError: true,
    trust: false,
    strict: "ignore",
  });
}
