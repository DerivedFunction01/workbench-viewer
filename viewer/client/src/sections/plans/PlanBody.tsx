// Plan body rendering: structured blocks from the server's
// parsed document. Markdown blocks render through marked +
// DOMPurify (the decided degraded-rendering pair, used here
// for every markdown block so no content is ever dropped);
// mermaid fences render as diagrams through the LAZY
// mermaid chunk — a plan with no fence never loads it, and
// a broken diagram falls back to its source block, never a
// hole (founding Step 6). Tables inside a section's
// markdown gain their structural anchor (plans/anchors.ts)
// before sanitizing; DOMPurify keeps data-* attributes.
// Math ($...$ / $$...$$, plan syntax standard) follows the
// mermaid arrangement: extracted before marked runs
// (plans/math.ts), rendered through the LAZY KaTeX chunk,
// and a span that fails keeps its source text.

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useEffect, useId, useMemo, useState } from "react";
import type { PlanBlock, PlanStep } from "../../lib/api";
import { highlightCode, highlightWithLanguage } from "../../lib/highlight";
import { anchor } from "./anchors";
import { codePlaceholderRe, extractCode } from "./codefences";
import { extractMath, mathPlaceholderRe, renderMath } from "./math";

const proseStyle: React.CSSProperties = {
  fontSize: "var(--wb-font-size-base)",
  lineHeight: "var(--wb-line-height-lg)",
  maxWidth: "68ch",
};

const codeStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-12) var(--wb-space-16)",
  fontFamily: "var(--wb-font-mono)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  overflowX: "auto",
  whiteSpace: "pre",
};

export function MarkdownBlock({ text, sectionHeading }: { text: string; sectionHeading: string }) {
  const prepared = useMemo(() => {
    const codeExtracted = extractCode(text);
    const extracted = extractMath(codeExtracted.text);
    const raw = marked.parse(extracted.text, { async: false }) as string;
    let tableIndex = 0;
    const anchored = raw.replace(/<table>/g, () => {
      tableIndex += 1;
      return `<table data-anchor="${anchor.table(sectionHeading, tableIndex)}">`;
    });
    return {
      html: DOMPurify.sanitize(anchored),
      spans: extracted.spans,
      codeSpans: codeExtracted.spans,
    };
  }, [text, sectionHeading]);
  const [html, setHtml] = useState(prepared.html);
  useEffect(() => {
    setHtml(prepared.html);
    if (prepared.spans.length === 0 && prepared.codeSpans.length === 0) return;
    let live = true;
    (async () => {
      let out = prepared.html;
      for (let i = 0; i < prepared.spans.length; i++) {
        const span = prepared.spans[i] as (typeof prepared.spans)[number];
        try {
          const fragment = DOMPurify.sanitize(await renderMath(span.tex, span.display));
          // If sanitizing ever stripped the rendered math,
          // keep the placeholder (its text is the source) —
          // a visible formula beats a hole.
          if (!fragment.includes('class="katex')) continue;
          out = out.replace(mathPlaceholderRe(i), () => fragment);
        } catch {
          // Unparseable math keeps its source text, the
          // degradation the syntax standard specifies.
        }
      }
      for (let i = 0; i < prepared.codeSpans.length; i++) {
        const span = prepared.codeSpans[i] as (typeof prepared.codeSpans)[number];
        const inner = span.lang
          ? ((await highlightWithLanguage(span.code, span.lang)) ??
            (await highlightCode(span.code)))
          : await highlightCode(span.code);
        // No highlight (unknown grammar, below the
        // relevance floor): the placeholder stays — its
        // text is the source.
        if (inner == null) continue;
        const fragment = DOMPurify.sanitize(
          `<pre class="wb-codeblock"><code>${inner}</code></pre>`,
        );
        if (!fragment.includes("wb-codeblock")) continue;
        out = out.replace(codePlaceholderRe(i), () => fragment);
      }
      if (live) setHtml(out);
    })();
    return () => {
      live = false;
    };
  }, [prepared]);
  return (
    // biome-ignore lint/security/noDangerouslySetInnerHtml: html is DOMPurify-sanitized immediately above — the one place plan HTML enters the DOM
    <div className="wb-prose" style={proseStyle} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

function MermaidDiagram({
  source,
  sectionHeading,
  index,
}: {
  source: string;
  sectionHeading: string;
  index: number;
}) {
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const rawId = useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        const styles = getComputedStyle(document.documentElement);
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          themeVariables: {
            background: styles.getPropertyValue("--wb-surface-sunken").trim(),
            primaryColor: styles.getPropertyValue("--wb-surface-2").trim(),
            primaryTextColor: styles.getPropertyValue("--wb-content-primary").trim(),
            primaryBorderColor: styles.getPropertyValue("--wb-border-strong").trim(),
            lineColor: styles.getPropertyValue("--wb-content-secondary").trim(),
            fontFamily: styles.getPropertyValue("--wb-font-ui").trim(),
          },
        });
        const out = await mermaid.render(`wb-diagram-${rawId}`, source);
        if (live)
          setSvg(DOMPurify.sanitize(out.svg, { USE_PROFILES: { svg: true, svgFilters: true } }));
      } catch {
        if (live) setFailed(true);
      }
    })();
    return () => {
      live = false;
    };
  }, [source, rawId]);

  if (failed) {
    return (
      <figure data-anchor={anchor.diagram(sectionHeading, index)}>
        <pre style={codeStyle}>{source}</pre>
        <figcaption style={{ color: "var(--wb-content-muted)" }}>
          Diagram source — the diagram could not be drawn.
        </figcaption>
      </figure>
    );
  }
  return (
    <figure
      data-anchor={anchor.diagram(sectionHeading, index)}
      style={{
        background: "var(--wb-surface-sunken)",
        border: "1px solid var(--wb-border-default)",
        borderRadius: "var(--wb-radius-md)",
        padding: "var(--wb-space-16)",
        margin: 0,
        overflowX: "auto",
      }}
    >
      {svg ? (
        // biome-ignore lint/security/noDangerouslySetInnerHtml: svg is DOMPurify-sanitized (svg profile) at render time above
        <div dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <p style={{ color: "var(--wb-content-muted)" }}>Drawing diagram…</p>
      )}
    </figure>
  );
}

/** A structured code block from the parsed document,
 * with the shared highlight treatment (the block's own
 * declared language first, auto-detect behind it); a
 * block that cannot be highlighted renders plain — never
 * a hole. */
function CodeBlock({ text, lang }: { text: string; lang?: string }) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    setHtml(null);
    let live = true;
    (async () => {
      const out = lang
        ? ((await highlightWithLanguage(text, lang)) ?? (await highlightCode(text)))
        : await highlightCode(text);
      if (live) setHtml(out);
    })();
    return () => {
      live = false;
    };
  }, [text, lang]);
  if (html == null) return <pre style={codeStyle}>{text}</pre>;
  // biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js escapes the source text itself; its output is span markup only (the shared highlight pattern)
  return <pre style={codeStyle} dangerouslySetInnerHTML={{ __html: html }} />;
}

export function BlockView({
  block,
  sectionHeading,
  diagramIndex,
}: {
  block: PlanBlock;
  sectionHeading: string;
  diagramIndex: number;
}) {
  if (block.type === "mermaid") {
    return (
      <MermaidDiagram
        source={block.source ?? ""}
        sectionHeading={sectionHeading}
        index={diagramIndex}
      />
    );
  }
  if (block.type === "code") {
    return <CodeBlock text={block.text ?? ""} lang={block.lang} />;
  }
  return <MarkdownBlock text={block.text ?? ""} sectionHeading={sectionHeading} />;
}

const subBlockLabel: React.CSSProperties = {
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--wb-content-secondary)",
};

export function StepBlock({ step }: { step: PlanStep }) {
  return (
    <article
      data-anchor={anchor.step(step.n)}
      style={{
        background: "var(--wb-surface-2)",
        border: "1px solid var(--wb-border-default)",
        borderRadius: "var(--wb-radius-md)",
        padding: "var(--wb-card-padding)",
        marginBottom: "var(--wb-space-12)",
      }}
    >
      <h3 style={{ margin: "0 0 var(--wb-space-8)", fontSize: "var(--wb-font-size-base)" }}>
        <span className="num" style={{ color: "var(--wb-content-secondary)" }}>
          {step.n}.
        </span>{" "}
        {step.title}
      </h3>
      {step.body ? <MarkdownBlock text={step.body} sectionHeading={`step ${step.n}`} /> : null}
      {(
        [
          ["Files", step.files],
          ["Verify", step.verify],
          ["Done when", step.done_when],
        ] as const
      ).map(([label, value]) =>
        value ? (
          <div key={label} style={{ marginTop: "var(--wb-space-8)" }}>
            <div style={subBlockLabel}>{label}</div>
            <div
              className="mono"
              style={{
                fontSize: "var(--wb-font-size-sm)",
                lineHeight: "var(--wb-line-height-sm)",
                whiteSpace: "pre-wrap",
              }}
            >
              {value}
            </div>
          </div>
        ) : null,
      )}
    </article>
  );
}
