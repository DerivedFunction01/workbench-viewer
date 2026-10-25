// Plans — the reading view (Subplan 07, founding Step 6).
// Bundle-aware: a bundle with a plan renders the plan, and
// the bundle's todos ride as its checklist strip; legacy
// flat plans are one-file bundles. The reader renders the
// server-parsed document — header field table, structured
// step blocks, rulings band, lazy mermaid with a source
// fallback — under a source-format banner when the plan
// does not conform (whole source as formatted markdown;
// content is never dropped). A Raw toggle swaps to the
// source view (highlight.js, lazy). Structural anchors are
// derived at render time (plans/anchors.ts, §14.5). The
// reader also carries D7's anchored comment box for the
// open plan, under the checklist strip.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { DegradedBanner as KitBanner } from "../components/DegradedBanner";
import { SegmentedControl } from "../components/SegmentedControl";
import { api, type BundleItem, type PlanDoc, type TodoItem } from "../lib/api";
import { formatDate, formatRelative } from "../lib/format";
import { planBucketLabel, todoStatusLabel } from "../lib/labels";
import { sectionHref } from "../lib/routing";
import { AnchoredComment } from "./inbox/AnchoredComment";
import { anchor } from "./plans/anchors";
import { ChangesPanel, WorktreeChanges } from "./plans/ChangesPanel";
import { BlockView, MarkdownBlock, StepBlock } from "./plans/PlanBody";
import {
  DegradedBanner,
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";

/** Stable content key for a block (never its list index). */
function blockKey(raw: string): string {
  let hash = 0;
  for (let i = 0; i < raw.length; i++) {
    hash = (hash * 31 + raw.charCodeAt(i)) | 0;
  }
  return `b${(hash >>> 0).toString(36)}-${raw.length}`;
}

const STATUS_GLYPH: Record<string, string> = {
  todo: "○",
  doing: "●",
  blocked: "⚠",
  done: "✓",
};

export function ChecklistStrip({ todos }: { todos: TodoItem[] }) {
  if (todos.length === 0) return null;
  return (
    <ul
      style={{
        listStyle: "none",
        margin: "var(--wb-space-8) 0 0",
        padding: 0,
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--wb-space-8)",
      }}
    >
      {todos.map((todo) => (
        <li
          key={todo.path ?? todo.id ?? todo.title ?? ""}
          style={{
            border: "1px solid var(--wb-border-default)",
            borderRadius: "var(--wb-radius-pill)",
            padding: "0 var(--wb-space-8)",
            fontSize: "var(--wb-font-size-xs)",
            lineHeight: "var(--wb-line-height-xs)",
            color: todo.valid === false ? "var(--wb-danger)" : "var(--wb-content-secondary)",
          }}
        >
          <span aria-hidden="true">
            {todo.valid === false ? "⚠" : (STATUS_GLYPH[todo.status ?? ""] ?? "○")}{" "}
          </span>
          {todo.title ?? todo.path ?? "Untitled todo"}
          {todo.valid === false ? " · invalid" : ""}
        </li>
      ))}
    </ul>
  );
}

function bundleTitle(bundle: BundleItem): string {
  return bundle.plan?.title || bundle.id;
}

function BundleRow({ slug, bundle }: { slug: string; bundle: BundleItem }) {
  const plan = bundle.plan;
  const inner = (
    <>
      <span style={{ flex: 1 }}>
        {bundleTitle(bundle)}
        {plan && !plan.conforming ? (
          <span style={{ color: "var(--wb-content-secondary)" }}> · source format</span>
        ) : null}
        {bundle.kind === "bundle" ? (
          <span style={{ color: "var(--wb-content-muted)" }}> · bundle</span>
        ) : null}
        <ChecklistStrip todos={bundle.todos} />
      </span>
      {plan ? (
        <>
          <span style={metaStyle}>{planBucketLabel(plan.status_bucket)}</span>
          <span style={metaStyle}>
            <span className="num">{plan.step_count}</span> steps
          </span>
          <span style={metaStyle}>
            {formatDate(plan.modified)} {formatRelative(plan.modified)}
          </span>
        </>
      ) : (
        <span style={metaStyle}>
          <span className="num">{bundle.open_count}</span> open of{" "}
          <span className="num">{bundle.todo_count}</span> todos
        </span>
      )}
    </>
  );
  return (
    <li>
      {plan ? (
        <a href={sectionHref(slug, "plans", plan.path)} style={listRowStyle}>
          {inner}
        </a>
      ) : (
        <div style={listRowStyle}>{inner}</div>
      )}
      {bundle.errors.length > 0 ? (
        <p style={{ color: "var(--wb-danger)", margin: "0 0 var(--wb-space-8)" }}>
          {bundle.errors.map((e) => `${e.path}: ${e.error}`).join(" · ")}
        </p>
      ) : null}
    </li>
  );
}

function FinishedTodos({ bundle }: { bundle: BundleItem }) {
  if (bundle.todos.length === 0) return null;
  return (
    <details>
      <summary style={{ color: "var(--wb-content-secondary)", cursor: "pointer" }}>
        <span className="num">{bundle.todos.length}</span> finished todos
      </summary>
      <ul style={{ listStyle: "none", margin: "var(--wb-space-8) 0", padding: 0 }}>
        {bundle.todos.map((todo) => (
          <li
            key={todo.path ?? todo.id ?? ""}
            style={{ padding: "var(--wb-space-4) 0", color: "var(--wb-content-secondary)" }}
          >
            <span aria-hidden="true">{STATUS_GLYPH[todo.status ?? ""] ?? "○"} </span>
            {todo.title ?? todo.path} · {todoStatusLabel(todo.status)}
            {todo.body ? (
              <span style={{ color: "var(--wb-content-muted)" }}> — {todo.body}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function SourceView({ source }: { source: string }) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const hljs = (await import("highlight.js")).default;
        const out = hljs.highlight(source, { language: "markdown" }).value;
        if (live) setHtml(out);
      } catch {
        if (live) setHtml(null);
      }
    })();
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

function PlanReader({
  slug,
  projectName,
  path,
  bundle,
}: {
  slug: string;
  projectName: string;
  path: string;
  bundle: BundleItem | null;
}) {
  const [view, setView] = useState<"formatted" | "changes" | "source">("formatted");
  const query = useQuery({
    queryKey: ["plan", slug, path],
    queryFn: () => api.getPlan({ slug, path }),
  });
  if (query.isPending) return <SkeletonWell label={`plan ${path}`} />;
  if (query.isError || !query.data.payload) {
    return (
      <ErrorWell section="Plans" message={query.data?.error ?? "the plan could not be loaded."} />
    );
  }
  const doc = query.data.payload as unknown as PlanDoc;
  const fieldEntries = Object.entries(doc.fields);
  let stepsRendered = false;

  return (
    <div data-anchor={anchor.planReader}>
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
        }}
      >
        <h2 style={{ margin: 0 }}>{doc.title || doc.path}</h2>
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
                      }}
                    >
                      {value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {doc.sections.map((section) => {
            let diagramIndex = 0;
            const showSteps = section.is_steps && !stepsRendered && doc.steps.length > 0;
            if (showSteps) stepsRendered = true;
            return (
              <section
                key={section.heading}
                data-anchor={anchor.section(section.heading)}
                style={{ marginTop: "var(--wb-space-24)" }}
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
                  doc.steps.map((step) => <StepBlock key={step.n} step={step} />)
                ) : section.is_rulings ? (
                  <div
                    style={{
                      borderLeft: "2px solid var(--wb-accent)",
                      paddingLeft: "var(--wb-space-16)",
                    }}
                  >
                    {section.blocks.map((block) => (
                      <BlockView
                        key={blockKey(block.raw)}
                        block={block}
                        sectionHeading={section.heading}
                        diagramIndex={block.type === "mermaid" ? ++diagramIndex : diagramIndex}
                      />
                    ))}
                  </div>
                ) : (
                  section.blocks.map((block) => (
                    <BlockView
                      key={blockKey(block.raw)}
                      block={block}
                      sectionHeading={section.heading}
                      diagramIndex={block.type === "mermaid" ? ++diagramIndex : diagramIndex}
                    />
                  ))
                )}
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}

export function PlansSection({
  slug,
  projectName,
  item,
}: {
  slug: string;
  projectName: string;
  item: string | null;
}) {
  const query = useQuery({
    queryKey: ["plans", slug],
    queryFn: () => api.getPlans({ slug }),
  });

  if (query.isPending) return <SkeletonWell label={`plans for ${projectName}`} />;
  if (query.isError) {
    return <ErrorWell section="Plans" message="the section feed could not be loaded." />;
  }
  const { payload, error } = query.data;
  if (!payload) {
    return <ErrorWell section="Plans" message={error ?? "the companion server did not answer."} />;
  }
  const feed = payload as unknown as import("../lib/api").PlansFeed;
  const active = feed.bundles.filter((bundle) => !bundle.archived);
  const finished = feed.bundles.filter((bundle) => bundle.archived);
  const readerBundle = item
    ? (feed.bundles.find((bundle) => bundle.plan?.path === item) ?? null)
    : null;

  return (
    <section>
      <h1 style={sectionTitleStyle}>Plans</h1>
      <DegradedBanner feed={feed} />
      {item ? (
        <PlanReader slug={slug} projectName={projectName} path={item} bundle={readerBundle} />
      ) : (
        <div data-anchor={anchor.planList}>
          {feed.bundles.length === 0 ? (
            <EmptyWell>
              {feed.available
                ? `No plans in ${projectName} yet.`
                : `No plans for ${projectName} — this project declares no plans directory.`}
            </EmptyWell>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {active.map((bundle) => (
                <BundleRow key={bundle.path} slug={slug} bundle={bundle} />
              ))}
            </ul>
          )}
          {finished.length > 0 ? (
            <>
              <h2
                style={{
                  fontSize: "var(--wb-font-size-base)",
                  marginTop: "var(--wb-space-24)",
                }}
              >
                Finished
              </h2>
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {finished.map((bundle) => (
                  <BundleRow key={bundle.path} slug={slug} bundle={bundle} />
                ))}
              </ul>
              {finished.map((bundle) => (
                <FinishedTodos key={`todos-${bundle.path}`} bundle={bundle} />
              ))}
            </>
          ) : null}
          <WorktreeChanges slug={slug} />
        </div>
      )}
    </section>
  );
}
