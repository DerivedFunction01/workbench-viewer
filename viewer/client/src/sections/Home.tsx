// Workspace home (#/, repo-home spec §4): one row per
// swept project — identity/branch/HEAD, plan counts by
// bucket + the in-progress plan, todo counts, triage/stale
// counts, feed health — sorted by the server (in-progress
// first, then recent activity, then name).
//
// Worktrees are GROUPED (§19): the project row is the
// repo (its main checkout); linked worktrees nest under
// it as children, and only when the repo HAS them — a
// worktree strip never renders as an empty shell.

import { useQuery } from "@tanstack/react-query";
import { api, type HomePayload, type HomeRow } from "../lib/api";
import { formatDate, formatRelative } from "../lib/format";
import { planBucketLabel, todoStatusLabel } from "../lib/labels";
import { useIsPhone } from "../lib/responsive";
import { sectionHref } from "../lib/routing";
import { EmptyWell, ErrorWell, metaStyle, SkeletonWell, sectionTitleStyle } from "./shared";
import { ActivePlanLine, WorktreeChildren } from "./worktreeViews";

/** Outline count badge (derived values only — the
 * mockup's Home form carries the row's counts as badges). */
const countBadgeStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "1px var(--wb-space-8)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-pill)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  color: "var(--wb-content-secondary)",
  whiteSpace: "nowrap",
};

function countsLine(
  counts: Record<string, number>,
  order: string[],
  label: (raw: string) => string,
): string {
  return order
    .filter((key) => (counts[key] ?? 0) > 0)
    .map((key) => `${counts[key]} ${label(key).toLowerCase()}`)
    .join(" · ");
}

function ProjectRow({ row }: { row: HomeRow }) {
  const isPhone = useIsPhone();
  const planCounts = countsLine(row.plans.counts, ["doing", "todo", "done"], planBucketLabel);
  const todoCounts = countsLine(
    row.todos.counts,
    ["doing", "blocked", "todo", "done"],
    todoStatusLabel,
  );
  if (isPhone) {
    // Phone form (mobile mockup, Exhibit 1): the project is
    // a card — the Home list is the project switcher (◆3).
    // Identity stacked (name, slug), the git line as badges
    // (branch badge + head + "main checkout" on a group
    // head), counts as count badges, then the same active
    // plan line and §19 nested worktrees as desktop.
    const children = row.worktrees.filter((w) => !w.is_main);
    return (
      <li
        style={{
          border: "1px solid var(--wb-border-default)",
          borderRadius: "var(--wb-radius-lg)",
          background: "var(--wb-surface-1)",
          padding: "var(--wb-card-padding)",
          marginBottom: "var(--wb-space-16)",
        }}
      >
        <div>
          <a
            href={sectionHref(row.slug, "overview")}
            style={{
              color: "var(--wb-content-primary)",
              textDecoration: "none",
              fontWeight: 700,
              fontSize: "var(--wb-font-size-base)",
              lineHeight: "var(--wb-line-height-base)",
            }}
          >
            {row.name}
          </a>
          <div className="mono" style={{ ...metaStyle, whiteSpace: "normal" }}>
            {row.slug}
          </div>
        </div>
        {row.git ? (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--wb-space-8)",
              alignItems: "center",
              marginTop: "var(--wb-space-8)",
            }}
          >
            <span className="mono" style={countBadgeStyle}>
              {row.git.branch ?? "detached"}
            </span>
            {row.git.head_short ? (
              <span className="mono" style={metaStyle}>
                {row.git.head_short}
              </span>
            ) : null}
            {children.length > 0 ? <span style={countBadgeStyle}>main checkout</span> : null}
          </div>
        ) : (
          <div style={{ ...metaStyle, marginTop: "var(--wb-space-8)" }}>not a git repo</div>
        )}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--wb-space-8)",
            marginTop: "var(--wb-space-8)",
          }}
        >
          {row.plans.available ? (
            <span style={countBadgeStyle}>
              Plans <span className="num">{row.plans.total}</span>
              {planCounts ? ` · ${planCounts}` : ""}
            </span>
          ) : (
            <span style={countBadgeStyle}>No plans directory</span>
          )}
          {row.todos.available ? (
            <span style={countBadgeStyle}>
              Todos <span className="num">{row.todos.total}</span>
              {todoCounts ? ` · ${todoCounts}` : ""}
            </span>
          ) : null}
          {row.review.available && row.review.triage_count > 0 ? (
            <span style={countBadgeStyle}>
              Triage <span className="num">{row.review.triage_count}</span>
            </span>
          ) : null}
          {row.review.available && row.review.stale_count > 0 ? (
            <span style={countBadgeStyle}>
              Stale <span className="num">{row.review.stale_count}</span>
            </span>
          ) : null}
        </div>
        {row.last_activity ? (
          <div style={{ ...metaStyle, marginTop: "var(--wb-space-8)" }}>
            active {formatDate(row.last_activity)} {formatRelative(row.last_activity)}
          </div>
        ) : null}
        {row.degraded ? (
          <div style={{ ...metaStyle, color: "var(--wb-danger)", marginTop: "var(--wb-space-4)" }}>
            degraded — {row.reasons[0] ?? "see Overview"}
          </div>
        ) : null}
        <div style={{ marginTop: "var(--wb-space-8)" }}>
          {row.showcase && row.showcase.source !== "none" ? (
            <ActivePlanLine slug={row.slug} active={row.showcase} />
          ) : row.plans.in_progress ? (
            <span style={{ display: "inline-flex", gap: "var(--wb-space-8)", flexWrap: "wrap" }}>
              <a
                href={sectionHref(row.slug, "plans", row.plans.in_progress.path)}
                style={{ color: "var(--wb-accent)", textDecoration: "none" }}
              >
                {row.plans.in_progress.title}
              </a>
              <span style={metaStyle}>{planBucketLabel("doing")}</span>
            </span>
          ) : (
            <span style={metaStyle}>No active plan</span>
          )}
        </div>
        <WorktreeChildren slug={row.slug} worktrees={row.worktrees} />
      </li>
    );
  }
  return (
    <li
      style={{
        borderBottom: "1px solid var(--wb-border-default)",
        padding: "var(--wb-space-12) 0",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: "var(--wb-space-12)",
          flexWrap: "wrap",
        }}
      >
        <a
          href={sectionHref(row.slug, "overview")}
          style={{
            color: "var(--wb-content-primary)",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          {row.name}
        </a>
        <span className="mono" style={metaStyle}>
          {row.slug}
        </span>
        {row.git ? (
          <span style={metaStyle}>
            <span className="mono">{row.git.branch ?? "detached"}</span>
            {row.git.head_short ? (
              <>
                {" · "}
                <span className="mono">{row.git.head_short}</span>
              </>
            ) : null}
          </span>
        ) : (
          <span style={metaStyle}>not a git repo</span>
        )}
        {row.last_activity ? (
          <span style={metaStyle}>
            active {formatDate(row.last_activity)} {formatRelative(row.last_activity)}
          </span>
        ) : null}
        {row.degraded ? (
          <span style={{ ...metaStyle, color: "var(--wb-danger)" }}>
            degraded — {row.reasons[0] ?? "see Overview"}
          </span>
        ) : null}
      </div>
      <div
        style={{
          display: "flex",
          gap: "var(--wb-space-24)",
          flexWrap: "wrap",
          marginTop: "var(--wb-space-4)",
          fontSize: "var(--wb-font-size-sm)",
        }}
      >
        <span style={{ color: "var(--wb-content-secondary)" }}>
          {row.plans.available ? (
            <>
              Plans <span className="num">{row.plans.total}</span>
              {planCounts ? ` · ${planCounts}` : ""}
            </>
          ) : (
            "No plans directory"
          )}
        </span>
        <span style={{ color: "var(--wb-content-secondary)" }}>
          {row.todos.available ? (
            <>
              Todos <span className="num">{row.todos.total}</span>
              {todoCounts ? ` · ${todoCounts}` : ""}
            </>
          ) : (
            "No todos"
          )}
        </span>
        {row.review.available && (row.review.triage_count > 0 || row.review.stale_count > 0) ? (
          <span style={{ color: "var(--wb-content-secondary)" }}>
            <span className="num">{row.review.triage_count}</span> in triage ·{" "}
            <span className="num">{row.review.stale_count}</span> stale
          </span>
        ) : null}
      </div>
      <div style={{ marginTop: "var(--wb-space-4)" }}>
        {row.showcase && row.showcase.source !== "none" ? (
          <ActivePlanLine slug={row.slug} active={row.showcase} />
        ) : row.plans.in_progress ? (
          <span style={{ display: "inline-flex", gap: "var(--wb-space-8)" }}>
            <a
              href={sectionHref(row.slug, "plans", row.plans.in_progress.path)}
              style={{ color: "var(--wb-accent)", textDecoration: "none" }}
            >
              {row.plans.in_progress.title}
            </a>
            <span style={metaStyle}>{planBucketLabel("doing")}</span>
          </span>
        ) : (
          <span style={metaStyle}>No active plan</span>
        )}
      </div>
      {/* §19 grouping: linked worktrees nest under the repo
          row; nothing renders when there are none. */}
      <WorktreeChildren slug={row.slug} worktrees={row.worktrees} />
    </li>
  );
}

export function HomeSection() {
  const isPhone = useIsPhone();
  const query = useQuery({
    queryKey: ["home"],
    queryFn: () => api.getHome({}),
    refetchInterval: 30000,
  });
  if (query.isPending) return <SkeletonWell label="the workspace home" />;
  if (query.isError || !query.data.payload) {
    return (
      <ErrorWell
        section="Home"
        message={query.data?.error ?? "the companion server did not answer."}
      />
    );
  }
  const feed = query.data.payload as unknown as HomePayload;
  const sweepErrors = (feed.sweep_errors ?? []) as { path?: string; reason?: string }[];
  return (
    <section data-anchor="home/project-list">
      {isPhone ? (
        // The mockup's Home body opens with the section
        // label + project count (the top bar already
        // titles the view "Workbench").
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "var(--wb-space-12)",
          }}
        >
          <span
            style={{
              fontSize: "var(--wb-font-size-xs)",
              lineHeight: "var(--wb-line-height-xs)",
              fontWeight: 700,
              letterSpacing: "0.07em",
              textTransform: "uppercase",
              color: "var(--wb-content-muted)",
            }}
          >
            Projects
          </span>
          <span className="num" style={countBadgeStyle}>
            {feed.projects.length}
          </span>
        </div>
      ) : (
        <h1 style={sectionTitleStyle}>Workspace</h1>
      )}
      {sweepErrors.length > 0 ? (
        <p style={{ color: "var(--wb-danger)" }}>
          {sweepErrors.map((e) => `${e.path ?? "sweep"}: ${e.reason ?? ""}`).join(" · ")}
        </p>
      ) : null}
      {feed.projects.length === 0 ? (
        <EmptyWell>
          No projects in the sweep — a project joins by carrying a workbench.yaml manifest.
        </EmptyWell>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {feed.projects.map((row) => (
            <ProjectRow key={`${row.slug}:${row.root}`} row={row} />
          ))}
        </ul>
      )}
    </section>
  );
}
