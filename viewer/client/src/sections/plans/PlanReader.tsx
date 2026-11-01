// The plan reader: renders the server-parsed document
// — header field table, structured step blocks,
// rulings band, lazy mermaid with a source fallback —
// under a source-format banner when the plan does not
// conform (whole source as formatted markdown; content
// is never dropped). A Raw toggle swaps to the source
// view (highlight.js, lazy). Structural anchors are
// derived at render time (plans/anchors.ts, §14.5). The
// reader also carries the §12 annotation machinery and
// D7's anchored comment box for the open plan, under
// the checklist strip.

import { useQuery } from "@tanstack/react-query";
import { memo, useEffect, useRef, useState } from "react";
import { Badge } from "../../components/Badge";
import { DegradedBanner as KitBanner } from "../../components/DegradedBanner";
import { SegmentedControl } from "../../components/SegmentedControl";
import { api } from "../../lib/api";
import type { BundleItem, PlanDoc, PlanSummary, TextSelection } from "../../lib/api-types";
import { highlightWithLanguage } from "../../lib/highlight";
import { planBucketLabel } from "../../lib/labels";
import { useIsPhone } from "../../lib/responsive";
import { sectionHref } from "../../lib/routing";
import {
  AnnotationComposer,
  AnnotationList,
  type AnnotationThread,
  AnnotationThreadCard,
  clearAnnotationMarks,
  highlightSelectionInElement,
  SelectionTintStyle,
  useAnnotationThreads,
} from "../Annotations";
import { AnchoredComment } from "../inbox/AnchoredComment";
import { ErrorWell, listRowStyle, metaStyle, SkeletonWell } from "../shared";
import { anchor } from "./anchors";
import { ChangesPanel } from "./ChangesPanel";
import { ChecklistStrip } from "./ChecklistStrip";
import { BlockView, MarkdownBlock, StepBlock } from "./PlanBody";
import { QuestionsPanel } from "./QuestionsPanel";
import { sectionPresentation } from "./questions";
import { normalizeText } from "./relocation";

// The Questions card, memoized on its content props
// (the owner's answering ruling): the reader's chrome
// state — view switching, annotation arming, thread
// status — re-renders PlanReader without ever
// re-rendering the card, and the card's staged values
// live inside it alone. The two share a render pass
// only when the document itself changes (a swap), which
// is the one moment both must move.
const MemoQuestionsPanel = memo(QuestionsPanel);

/** Stable content key for a block (never its list index). */
function blockKey(raw: string): string {
  let hash = 0;
  for (let i = 0; i < raw.length; i++) {
    hash = (hash * 31 + raw.charCodeAt(i)) | 0;
  }
  return `b${(hash >>> 0).toString(36)}-${raw.length}`;
}

/** The reader's `## Subplans` section (§21): every
 * declared entry as a navigation row — title + status
 * when the path resolves against the project's plans,
 * a muted missing row naming the path when it does
 * not. Grouped or not, the links work; a self or cycle
 * reference is a plain row like any other. A path
 * declared twice renders once. */
function SubplanRows({
  slug,
  declared,
  planIndex,
}: {
  slug: string;
  declared: string[];
  planIndex: Map<string, PlanSummary>;
}) {
  const isPhone = useIsPhone();
  const distinct = [...new Set(declared)];
  const rowStyle: React.CSSProperties = isPhone
    ? { ...listRowStyle, flexWrap: "wrap" }
    : listRowStyle;
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {distinct.map((declaredPath) => {
        const target = planIndex.get(declaredPath);
        if (!target) {
          return (
            <li key={declaredPath}>
              <div style={{ ...rowStyle, color: "var(--wb-content-muted)" }}>
                <span
                  className="mono"
                  style={isPhone ? { flex: "1 1 100%", overflowWrap: "anywhere" } : { flex: 1 }}
                >
                  {declaredPath}
                </span>
                <span style={metaStyle}>missing</span>
              </div>
            </li>
          );
        }
        return (
          <li key={declaredPath}>
            <a href={sectionHref(slug, "plans", target.path)} style={rowStyle}>
              <span style={isPhone ? { flex: "1 1 100%" } : { flex: 1 }}>
                {target.title || target.path}
              </span>
              <span style={metaStyle}>{planBucketLabel(target.status_bucket)}</span>
              {target.derived?.stale && target.derived.age_days != null ? (
                <Badge kind="stale" text={`Stale · ${target.derived.age_days}d`} />
              ) : null}
            </a>
          </li>
        );
      })}
    </ul>
  );
}

function SourceView({ source }: { source: string }) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    void highlightWithLanguage(source, "markdown").then((out) => {
      if (live) setHtml(out);
    });
    return () => {
      live = false;
    };
  }, [source]);
  const style: React.CSSProperties = {
    background: "var(--wb-surface-sunken)",
    border: "1px solid var(--wb-border-default)",
    borderRadius: "var(--wb-radius-md)",
    padding: "var(--wb-space-16)",
    fontFamily: "var(--wb-font-mono)",
    fontSize: "var(--wb-font-size-sm)",
    lineHeight: "var(--wb-line-height-sm)",
    overflowX: "auto",
    whiteSpace: "pre",
  };
  if (html == null) return <pre style={style}>{source}</pre>;
  // biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js escapes the source text itself; its output is span markup only
  return <pre style={style} dangerouslySetInnerHTML={{ __html: html }} />;
}

interface ArmedSelection {
  selection: TextSelection;
  /** The block the composer renders under (and margin
   * threads render beside): the component itself for
   * steps/sections, the enclosing section for
   * tables/diagrams, the header/reader for their own
   * anchors. */
  hostAnchor: string;
  /** The plan the selection was made in — a stale armed
   * selection never renders (or posts) against another
   * plan after navigation. */
  forPath: string;
}

function hostAnchorForId(componentId: string, doc: PlanDoc): string {
  const nested = componentId.match(/^plans\/(?:table|diagram)-(.+)-\d+$/);
  if (nested) {
    const section = doc.sections.find(
      (s) => anchor.section(s.heading) === `plans/section-${nested[1]}`,
    );
    if (section) return anchor.section(section.heading);
  }
  return componentId;
}

function componentLabelFor(el: HTMLElement, componentId: string): string {
  if (componentId === anchor.planHeader) return "Plan header";
  const step = componentId.match(/^plans\/step-(\d+)$/);
  if (step) return `Step ${step[1]}`;
  const table = componentId.match(/^plans\/table-(.+)-\d+$/);
  if (table) return `table · ${table[1]}`;
  const diagram = componentId.match(/^plans\/diagram-(.+)-\d+$/);
  if (diagram) return `diagram · ${diagram[1]}`;
  if (componentId === anchor.planReader) return "Plan";
  return el.querySelector("h3")?.textContent?.trim() ?? componentId;
}

function sectionHeadingFor(el: HTMLElement): string | undefined {
  const heading = el.closest("section[data-anchor]")?.querySelector("h3")?.textContent?.trim();
  return heading || undefined;
}

export function PlanReader({
  slug,
  projectName,
  path,
  bundle,
  planIndex,
}: {
  slug: string;
  projectName: string;
  path: string;
  bundle: BundleItem | null;
  /** Every plan in the project by path — the reader's
   * `## Subplans` resolution set (§21). */
  planIndex: Map<string, PlanSummary>;
}) {
  const [view, setView] = useState<"formatted" | "changes" | "source">("formatted");
  const isPhone = useIsPhone();
  const query = useQuery({
    queryKey: ["plan", slug, path],
    queryFn: () => api.getPlan({ slug, path }),
  });
  // Annotation state (§12): the plan's threads, the armed
  // (selected, not yet commented) selection, and each text
  // thread's derived re-location status.
  const readerRef = useRef<HTMLDivElement | null>(null);
  const { threads, count } = useAnnotationThreads(slug, path);
  const [armed, setArmed] = useState<ArmedSelection | null>(null);
  const [statusById, setStatusById] = useState<Record<number, "located" | "moved">>({});
  useEffect(() => {
    const rootEl = readerRef.current;
    if (!rootEl || view !== "formatted" || query.isPending) return;
    clearAnnotationMarks(rootEl);
    const next: Record<number, "located" | "moved"> = {};
    for (const t of threads) {
      const sel = t.root.selection;
      if (sel?.kind !== "text") {
        next[t.root.id] = "located";
        continue;
      }
      const el = rootEl.querySelector(`[data-anchor="${sel.component_id}"]`);
      next[t.root.id] =
        el && highlightSelectionInElement(el as HTMLElement, sel) === "located"
          ? "located"
          : "moved";
    }
    setStatusById(next);
  }, [query.isPending, threads, view]);
  if (query.isPending) return <SkeletonWell label={`plan ${path}`} />;
  if (query.isError || !query.data.payload) {
    return (
      <ErrorWell section="Plans" message={query.data?.error ?? "the plan could not be loaded."} />
    );
  }
  const doc = query.data.payload as unknown as PlanDoc;
  const fieldEntries = Object.entries(doc.fields);
  let stepsRendered = false;

  // Arm a composer from the live DOM selection: it must
  // sit inside ONE component (a selection crossing a
  // component boundary is refused quietly, §12), inside
  // the formatted reader, outside the annotation UI
  // itself. Quote/prefix/suffix come from the component's
  // RENDERED text (the stored provenance; re-location
  // normalizes whitespace on both sides).
  function armFromSelection() {
    if (view !== "formatted") return;
    const rootEl = readerRef.current;
    const winSel = window.getSelection();
    if (!rootEl || !winSel || winSel.isCollapsed || winSel.rangeCount === 0) return;
    const range = winSel.getRangeAt(0);
    const cac = range.commonAncestorContainer;
    const cacEl = cac.nodeType === Node.ELEMENT_NODE ? (cac as Element) : cac.parentElement;
    if (!cacEl || cacEl.closest("[data-annotation-ui]") || !rootEl.contains(cac)) return;
    const elementOf = (node: Node): Element | null =>
      node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
    const startEl = elementOf(range.startContainer)?.closest<HTMLElement>("[data-anchor]");
    const endEl = elementOf(range.endContainer)?.closest<HTMLElement>("[data-anchor]");
    if (!startEl || startEl !== endEl || !rootEl.contains(startEl)) return;
    const componentId = startEl.dataset.anchor as string;
    const text = startEl.textContent ?? "";
    const pre = document.createRange();
    pre.selectNodeContents(startEl);
    pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    const quote = range.toString();
    // Oversize quotes are refused, never truncated (the
    // store's cap, enforced identically at create).
    if (!quote || normalizeText(quote) === "" || quote.length > 500) return;
    if (text.slice(start, start + quote.length) !== quote) return;
    const sectionHeading = sectionHeadingFor(startEl);
    setArmed({
      forPath: path,
      hostAnchor: hostAnchorForId(componentId, doc),
      selection: {
        kind: "text",
        component_id: componentId,
        component_label: componentLabelFor(startEl, componentId),
        ...(sectionHeading ? { section_heading: sectionHeading } : {}),
        quote,
        prefix: text.slice(Math.max(0, start - 120), start),
        suffix: text.slice(start + quote.length, start + quote.length + 120),
      },
    });
  }

  const activeArmed = armed?.forPath === path ? armed : null;
  const composer = activeArmed ? (
    <AnnotationComposer
      key={`${activeArmed.selection.component_id}:${activeArmed.selection.quote}`}
      slug={slug}
      anchorType="text"
      anchorRef={path}
      selection={activeArmed.selection}
      quote={activeArmed.selection.quote}
      onClose={() => setArmed(null)}
      onSent={() => setArmed(null)}
    />
  ) : null;

  const railThreads = (hostAnchor: string): AnnotationThread[] =>
    threads.filter((t) => {
      const sel = t.root.selection;
      return (
        sel?.kind === "text" &&
        statusById[t.root.id] !== "moved" &&
        hostAnchorForId(sel.component_id, doc) === hostAnchor
      );
    });
  const railAside = (hostAnchor: string) => {
    const here = railThreads(hostAnchor);
    if (here.length === 0) return null;
    return (
      <aside
        style={{
          // Phone (§20): there is no margin — the thread
          // stack goes full width and the enclosing flex
          // row turns column, so the stack renders directly
          // under its step/section block.
          width: isPhone ? "100%" : "300px",
          flexShrink: 0,
          display: "grid",
          gap: "var(--wb-space-8)",
          alignContent: "start",
        }}
      >
        {here.map((t) => (
          <AnnotationThreadCard key={t.root.id} slug={slug} thread={t} />
        ))}
      </aside>
    );
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: the reader root only OBSERVES text selection to arm the annotation composer; it has no activation behavior of its own and is not an interactive control
    <div
      data-anchor={anchor.planReader}
      data-annotation-scope="true"
      ref={readerRef}
      onMouseUp={armFromSelection}
      onKeyUp={armFromSelection}
    >
      <SelectionTintStyle />
      <p style={{ color: "var(--wb-content-secondary)" }}>
        <a href={sectionHref(slug, "plans")} style={{ color: "var(--wb-accent)" }}>
          All plans
        </a>{" "}
        · <span className="mono">{doc.path}</span>
      </p>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--wb-space-16)",
          // Phone: the title takes its own line and the
          // Annotations count + view switch wrap under it
          // (the mockup carries the count in the top bar;
          // the reader header keeps it here, wrapped).
          flexWrap: isPhone ? "wrap" : undefined,
        }}
      >
        <h2 style={{ margin: 0, minWidth: 0, overflowWrap: "anywhere" }}>
          {doc.title || doc.path}
        </h2>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-8)",
            // Phone: the cluster may shrink below its
            // max-content so the view switch wraps inside
            // the header instead of painting past it.
            minWidth: isPhone ? 0 : undefined,
            flexWrap: isPhone ? "wrap" : undefined,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--wb-space-4)",
              height: "24px",
              padding: "0 var(--wb-space-8)",
              border: "1px solid var(--wb-border-strong)",
              borderRadius: "var(--wb-radius-pill)",
              fontSize: "var(--wb-font-size-xs)",
              color: "var(--wb-content-secondary)",
              whiteSpace: "nowrap",
            }}
          >
            <span aria-hidden="true" style={{ color: "var(--wb-accent)" }}>
              ✎
            </span>
            Annotations · <span className="num">{count}</span>
          </span>
          <SegmentedControl
            ariaLabel="Plan view"
            options={[
              { value: "formatted", label: "Formatted" },
              { value: "changes", label: "Changes" },
              { value: "source", label: "Raw" },
            ]}
            value={view}
            onChange={setView}
          />
        </div>
      </div>
      {bundle ? <ChecklistStrip todos={bundle.todos} /> : null}
      {/* D7's second compose surface: a comment box anchored
          to the open plan (the Overview showcase mount is the
          same box on the same anchor). */}
      <div style={{ marginTop: "var(--wb-space-8)" }}>
        <AnchoredComment slug={slug} projectName={projectName} anchorType="plan" anchorRef={path} />
      </div>
      {!doc.conforming ? (
        <div style={{ margin: "var(--wb-space-16) 0" }}>
          <KitBanner
            tone="source-format"
            message="Source format — this plan does not follow the house format, so it renders whole as formatted markdown."
            detail="No content is dropped; the Raw view shows the exact source."
          />
        </div>
      ) : null}
      {view === "changes" ? (
        <div style={{ marginTop: "var(--wb-space-16)" }}>
          <ChangesPanel slug={slug} bundle={bundle?.id ?? null} />
        </div>
      ) : view === "source" ? (
        <SourceView source={doc.markdown} />
      ) : !doc.conforming ? (
        <MarkdownBlock text={doc.markdown} sectionHeading="source" />
      ) : (
        <>
          {fieldEntries.length > 0 ? (
            <table
              data-anchor={anchor.planHeader}
              style={{
                borderCollapse: "collapse",
                margin: "var(--wb-space-16) 0",
                background: "var(--wb-surface-2)",
                border: "1px solid var(--wb-border-default)",
                borderRadius: "var(--wb-radius-md)",
              }}
            >
              <tbody>
                {fieldEntries.map(([key, value]) => (
                  <tr key={key}>
                    <th
                      style={{
                        textAlign: "left",
                        padding: "var(--wb-space-8) var(--wb-space-16)",
                        color: "var(--wb-content-secondary)",
                        borderBottom: "1px solid var(--wb-border-default)",
                        whiteSpace: "nowrap",
                        verticalAlign: "top",
                      }}
                    >
                      {key}
                    </th>
                    <td
                      style={{
                        padding: "var(--wb-space-8) var(--wb-space-16)",
                        borderBottom: "1px solid var(--wb-border-default)",
                        whiteSpace: "pre-wrap",
                        overflowWrap: isPhone ? "anywhere" : undefined,
                      }}
                    >
                      {value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {activeArmed?.hostAnchor === anchor.planHeader ? composer : null}
          {doc.sections.map((section) => {
            let diagramIndex = 0;
            const showSteps = section.is_steps && !stepsRendered && doc.steps.length > 0;
            if (showSteps) stepsRendered = true;
            const sectionAnchor = anchor.section(section.heading);
            const { blocks: sectionBlocks, showQuestions } = sectionPresentation(
              section,
              doc.questions.length,
            );
            return (
              <div key={section.heading}>
                <div
                  style={{
                    display: "flex",
                    flexDirection: isPhone ? "column" : "row",
                    gap: "var(--wb-space-16)",
                    alignItems: isPhone ? "stretch" : "flex-start",
                  }}
                >
                  <section
                    data-anchor={sectionAnchor}
                    style={{ flex: 1, minWidth: 0, marginTop: "var(--wb-space-24)" }}
                  >
                    <h3
                      style={{
                        fontSize: "var(--wb-font-size-lg)",
                        lineHeight: "var(--wb-line-height-lg)",
                      }}
                    >
                      {section.heading}
                    </h3>
                    {showSteps ? (
                      doc.steps.map((step) => {
                        const stepAnchor = anchor.step(step.n);
                        return (
                          <div key={step.n}>
                            <div
                              style={{
                                display: "flex",
                                flexDirection: isPhone ? "column" : "row",
                                gap: "var(--wb-space-16)",
                                alignItems: isPhone ? "stretch" : "flex-start",
                              }}
                            >
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <StepBlock step={step} />
                              </div>
                              {railAside(stepAnchor)}
                            </div>
                            {activeArmed?.hostAnchor === stepAnchor ? composer : null}
                          </div>
                        );
                      })
                    ) : section.is_subplans && doc.subplans.length > 0 ? (
                      <SubplanRows slug={slug} declared={doc.subplans} planIndex={planIndex} />
                    ) : section.is_rulings ? (
                      <div
                        style={{
                          borderLeft: "2px solid var(--wb-accent)",
                          paddingLeft: "var(--wb-space-16)",
                        }}
                      >
                        {sectionBlocks.map((block) => (
                          <BlockView
                            key={blockKey(block.raw)}
                            block={block}
                            sectionHeading={section.heading}
                            diagramIndex={block.type === "mermaid" ? ++diagramIndex : diagramIndex}
                          />
                        ))}
                      </div>
                    ) : (
                      sectionBlocks.map((block) => (
                        <BlockView
                          key={blockKey(block.raw)}
                          block={block}
                          sectionHeading={section.heading}
                          diagramIndex={block.type === "mermaid" ? ++diagramIndex : diagramIndex}
                        />
                      ))
                    )}
                  </section>
                  {railAside(sectionAnchor)}
                </div>
                {activeArmed?.hostAnchor === sectionAnchor ? composer : null}
                {showQuestions ? (
                  <MemoQuestionsPanel key={doc.file_sha256} slug={slug} path={path} doc={doc} />
                ) : null}
              </div>
            );
          })}
        </>
      )}
      {view === "formatted" && activeArmed?.hostAnchor === anchor.planReader ? composer : null}
      {threads.length > 0 ? (
        <div style={{ marginTop: "var(--wb-space-32)" }}>
          <h3
            style={{ fontSize: "var(--wb-font-size-lg)", lineHeight: "var(--wb-line-height-lg)" }}
          >
            Annotations · <span className="num">{count}</span>
          </h3>
          <AnnotationList
            slug={slug}
            threads={threads}
            statusOf={(root) => (statusById[root.id] === "moved" ? "moved" : "located")}
          />
        </div>
      ) : null}
    </div>
  );
}
