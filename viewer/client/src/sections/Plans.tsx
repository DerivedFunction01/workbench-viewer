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
import { Badge } from "../components/Badge";
import { api } from "../lib/api";
import type { BundleItem, PlanSummary } from "../lib/api-types";
import { formatDate, formatRelative } from "../lib/format";
import { planBucketLabel, todoStatusLabel } from "../lib/labels";
import { useIsPhone } from "../lib/responsive";
import { sectionHref } from "../lib/routing";
import { anchor } from "./plans/anchors";
import { WorktreeChanges } from "./plans/ChangesPanel";
import { ChecklistStrip, STATUS_GLYPH } from "./plans/ChecklistStrip";
import { groupBundles, type PlanGroupEntry, type PlanGrouping } from "./plans/grouping";
import { PlanReader } from "./plans/PlanReader";
import {
  DegradedBanner,
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";
import { UpdatedAgo } from "./UpdatedAgo";

function bundleTitle(bundle: BundleItem): string {
  return bundle.plan?.title || bundle.id;
}

function BundleRow({
  slug,
  bundle,
  subplansCount,
  children,
}: {
  slug: string;
  bundle: BundleItem;
  /** Resolved `## Subplans` declarations (§21): the
   * count a group parent — or a nested child with its
   * own subplans — carries on its row. */
  subplansCount?: number;
  children?: React.ReactNode;
}) {
  const isPhone = useIsPhone();
  const plan = bundle.plan;
  // Stale-work warning (served `derived`, never computed
  // here): the row flags when the bundle itself is stale
  // open work, or when its plan is — the two share a
  // birthdate, so either age labels the row honestly.
  const staleAge = bundle.derived?.stale
    ? bundle.derived.age_days
    : plan?.derived?.stale
      ? plan.derived.age_days
      : null;
  const staleBadge = staleAge != null ? <Badge kind="stale" text={`Stale · ${staleAge}d`} /> : null;
  // Phone (the owner, 2026-10-25): the row stacks — the title
  // takes the full row width on its own line(s) and the
  // metadata line renders beneath it. A column direction
  // stacks deterministically; the earlier flex-wrap +
  // 100%-basis title still reached his phone side by side,
  // the title squeezed into a narrow column (screenshot,
  // 2026-10-25). Desktop's single line is untouched.
  const rowStyle: React.CSSProperties = isPhone
    ? { ...listRowStyle, flexDirection: "column", alignItems: "stretch" }
    : listRowStyle;
  const meta = plan ? (
    <>
      <span style={metaStyle}>{planBucketLabel(plan.status_bucket)}</span>
      <span style={metaStyle}>
        <span className="num">{plan.step_count}</span> steps
      </span>
      {subplansCount ? (
        <span style={metaStyle}>
          <span className="num">{subplansCount}</span>{" "}
          {subplansCount === 1 ? "subplan" : "subplans"}
        </span>
      ) : null}
      <span style={metaStyle}>
        {formatDate(plan.modified)} {formatRelative(plan.modified)}
      </span>
      {staleBadge}
    </>
  ) : (
    <>
      <span style={metaStyle}>
        <span className="num">{bundle.open_count}</span> open of{" "}
        <span className="num">{bundle.todo_count}</span> todos
      </span>
      {staleBadge}
    </>
  );
  const inner = (
    <>
      <span style={isPhone ? undefined : { flex: 1 }}>
        {bundleTitle(bundle)}
        {plan && !plan.conforming ? (
          <span style={{ color: "var(--wb-content-secondary)" }}> · source format</span>
        ) : null}
        {bundle.kind === "bundle" ? (
          <span style={{ color: "var(--wb-content-muted)" }}> · bundle</span>
        ) : null}
        <ChecklistStrip todos={bundle.todos} />
      </span>
      {isPhone ? (
        <span
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "var(--wb-space-12)",
          }}
        >
          {meta}
        </span>
      ) : (
        meta
      )}
    </>
  );
  return (
    <li>
      {plan ? (
        <a href={sectionHref(slug, "plans", plan.path)} style={rowStyle}>
          {inner}
        </a>
      ) : (
        <div style={rowStyle}>{inner}</div>
      )}
      {bundle.errors.length > 0 ? (
        <p style={{ color: "var(--wb-danger)", margin: "0 0 var(--wb-space-8)" }}>
          {bundle.errors.map((e) => `${e.path}: ${e.error}`).join(" · ")}
        </p>
      ) : null}
      {children}
    </li>
  );
}

/** A top-level list row with its grouping (§21): the
 * claimed subplan bundles nested one level beneath it,
 * then a muted row for each declared path that resolves
 * to nothing — vanished references degrade honestly,
 * never silently dropped. */
function BundleGroupRow({
  slug,
  grouping,
  entry,
}: {
  slug: string;
  grouping: PlanGrouping;
  entry: PlanGroupEntry;
}) {
  const isPhone = useIsPhone();
  const hasNested = entry.children.length > 0 || entry.missing.length > 0;
  return (
    <BundleRow slug={slug} bundle={entry.bundle} subplansCount={entry.resolvedCount}>
      {hasNested ? (
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            paddingLeft: "var(--wb-space-24)",
          }}
        >
          {entry.children.map((child) => (
            <BundleRow
              key={child.path}
              slug={slug}
              bundle={child}
              subplansCount={
                child.plan ? grouping.byPlanPath.get(child.plan.path)?.resolvedCount : undefined
              }
            />
          ))}
          {entry.missing.map((declaredPath) => (
            <li key={`missing-${declaredPath}`}>
              <div
                style={
                  isPhone
                    ? {
                        ...listRowStyle,
                        flexDirection: "column",
                        alignItems: "stretch",
                        color: "var(--wb-content-muted)",
                      }
                    : { ...listRowStyle, color: "var(--wb-content-muted)" }
                }
              >
                <span className="mono" style={isPhone ? { overflowWrap: "anywhere" } : { flex: 1 }}>
                  {declaredPath}
                </span>
                <span style={metaStyle}>missing</span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </BundleRow>
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
    refetchInterval: 30000,
  });

  if (query.isPending) return <SkeletonWell label={`plans for ${projectName}`} />;
  if (query.isError) {
    return <ErrorWell section="Plans" message="the section feed could not be loaded." />;
  }
  const { payload, error } = query.data;
  if (!payload) {
    return <ErrorWell section="Plans" message={error ?? "the companion server did not answer."} />;
  }
  const feed = payload as unknown as import("../lib/api-types").PlansFeed;
  // §21 grouping: claimed subplans leave the top level
  // and nest under their first declaring parent, in
  // whichever list (active or finished) the parent
  // renders — resolution covers both alike.
  const grouping = groupBundles(feed.bundles);
  const active = grouping.topLevel.filter((entry) => !entry.bundle.archived);
  const finished = grouping.topLevel.filter((entry) => entry.bundle.archived);
  const readerBundle = item
    ? (feed.bundles.find((bundle) => bundle.plan?.path === item) ?? null)
    : null;
  const planIndex = new Map<string, PlanSummary>();
  for (const bundle of feed.bundles) {
    if (bundle.plan) planIndex.set(bundle.plan.path, bundle.plan);
  }

  return (
    <section>
      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--wb-space-12)" }}>
        <h1 style={sectionTitleStyle}>Plans</h1>
        <UpdatedAgo capturedAt={feed.captured_at} />
      </div>
      <DegradedBanner feed={feed} />
      {item ? (
        <PlanReader
          slug={slug}
          projectName={projectName}
          path={item}
          bundle={readerBundle}
          planIndex={planIndex}
        />
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
              {active.map((entry) => (
                <BundleGroupRow
                  key={entry.bundle.path}
                  slug={slug}
                  grouping={grouping}
                  entry={entry}
                />
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
                {finished.map((entry) => (
                  <BundleGroupRow
                    key={entry.bundle.path}
                    slug={slug}
                    grouping={grouping}
                    entry={entry}
                  />
                ))}
              </ul>
              {finished.map((entry) => (
                <FinishedTodos key={`todos-${entry.bundle.path}`} bundle={entry.bundle} />
              ))}
            </>
          ) : null}
          <WorktreeChanges slug={slug} />
        </div>
      )}
    </section>
  );
}
