// Per-project Overview (repo-home spec §4 + §17) — the
// FIRST per-project tab. The active plan of the main
// checkout is showcased (resolved per §17.2, provenance
// shown; D1's pin), other in-progress bundles list as
// "also in progress here", the worktree panel is GROUPED
// (§19: the main checkout is the group node, linked
// worktrees nest under it — no shell when there are
// none), and the todos/board strip renders the viewer's
// own derivations by reference (links into the sections),
// never re-implemented.

import { useQuery } from "@tanstack/react-query";
import { Card } from "../components/Card";
import {
  type ActiveResolution,
  api,
  type BundleItem,
  type HomePayload,
  type HomeRow,
  type PlansFeed,
  type WorktreesPayload,
} from "../lib/api";
import { formatDate, formatRelative } from "../lib/format";
import { planBucketLabel, todoStatusLabel } from "../lib/labels";
import { sectionHref } from "../lib/routing";
import { AnchoredComment } from "./inbox/AnchoredComment";
import {
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";
import { ActivePlanLine, ProvenanceMark, WorktreeChildren, WorktreeMeta } from "./worktreeViews";

function ShowcaseCard({
  slug,
  projectName,
  showcase,
}: {
  slug: string;
  projectName: string;
  showcase: ActiveResolution | null;
}) {
  if (!showcase || showcase.source === "none" || !showcase.bundle) {
    return (
      <Card anchor="overview/showcase" title="Active plan">
        <EmptyWell>
          No active plan in the main checkout. Declare one with{" "}
          <span className="mono">wb activate &lt;bundle&gt;</span> when work starts, or pick from
          the plan list below.
        </EmptyWell>
        {showcase?.note ? (
          <p style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) 0 0" }}>
            {showcase.note}
          </p>
        ) : null}
      </Card>
    );
  }
  const { plan, bundle } = showcase;
  return (
    <Card anchor="overview/showcase" title="Active plan">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-12)",
          flexWrap: "wrap",
        }}
      >
        {plan ? (
          <a
            href={sectionHref(slug, "plans", plan.path)}
            style={{
              color: "var(--wb-content-primary)",
              textDecoration: "none",
              fontWeight: 600,
              fontSize: "var(--wb-font-size-lg)",
            }}
          >
            {plan.title}
          </a>
        ) : (
          <span style={{ fontWeight: 600, fontSize: "var(--wb-font-size-lg)" }}>{bundle.id}</span>
        )}
        <ProvenanceMark source={showcase.source} />
      </div>
      <p style={{ color: "var(--wb-content-secondary)", margin: "var(--wb-space-8) 0 0" }}>
        {plan ? (
          <>
            {planBucketLabel(plan.status_bucket)} · modified {formatDate(plan.modified)}{" "}
            {formatRelative(plan.modified)} ·{" "}
          </>
        ) : (
          <>Plan-less bundle · </>
        )}
        <span className="mono">{bundle.id}</span> · <span className="num">{bundle.open_count}</span>{" "}
        open of <span className="num">{bundle.todo_count}</span> todos
        {showcase.declared?.since ? <> · declared {formatDate(showcase.declared.since)}</> : null}
      </p>
      {showcase.note ? (
        <p style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) 0 0" }}>
          {showcase.note}
        </p>
      ) : null}
      {plan ? (
        <div style={{ marginTop: "var(--wb-space-8)" }}>
          <AnchoredComment
            slug={slug}
            projectName={projectName}
            anchorType="plan"
            anchorRef={plan.path}
          />
        </div>
      ) : null}
      {showcase.also_in_progress.length > 0 ? (
        <div style={{ marginTop: "var(--wb-space-12)" }}>
          <div style={metaStyle}>Also in progress here</div>
          <ul style={{ listStyle: "none", margin: "var(--wb-space-4) 0 0", padding: 0 }}>
            {showcase.also_in_progress.map((other) => (
              <li key={other.bundle.id} style={{ padding: "var(--wb-space-4) 0" }}>
                {other.plan ? (
                  <a
                    href={sectionHref(slug, "plans", other.plan.path)}
                    style={{ color: "var(--wb-accent)", textDecoration: "none" }}
                  >
                    {other.plan.title}
                  </a>
                ) : (
                  <span className="mono">{other.bundle.id}</span>
                )}{" "}
                <span style={metaStyle}>
                  <span className="num">{other.bundle.open_count}</span> open todos
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}

function WorktreesCard({
  slug,
  payload,
  fallback,
}: {
  slug: string;
  payload: WorktreesPayload | null;
  fallback: HomeRow | null;
}) {
  const worktrees = payload?.worktrees ?? fallback?.worktrees ?? [];
  const available = payload ? payload.available : fallback != null;
  const main = worktrees.find((w) => w.is_main) ?? null;
  return (
    <Card anchor="overview/worktrees" title="Worktrees">
      {!available ? (
        <EmptyWell>
          Git state is unavailable for this project
          {payload?.reason ? ` — ${payload.reason}` : ""}.
        </EmptyWell>
      ) : main == null && worktrees.length === 0 ? (
        <EmptyWell>Not a git repository — no worktrees to show.</EmptyWell>
      ) : (
        <>
          {main ? (
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--wb-space-12)",
                  flexWrap: "wrap",
                }}
              >
                <span style={{ fontWeight: 600 }}>Main checkout</span>
                <WorktreeMeta worktree={main} />
              </div>
              <div style={{ marginTop: "var(--wb-space-4)" }}>
                <ActivePlanLine slug={slug} active={main.active} />
              </div>
              <div className="mono" style={{ ...metaStyle, marginTop: "var(--wb-space-4)" }}>
                {main.path}
              </div>
            </div>
          ) : null}
          {/* §19: linked worktrees nest under the main
              checkout; nothing renders when there are none. */}
          <WorktreeChildren slug={slug} worktrees={worktrees} />
        </>
      )}
    </Card>
  );
}

function PlanList({
  slug,
  bundles,
  showcasePath,
}: {
  slug: string;
  bundles: BundleItem[];
  showcasePath: string | null;
}) {
  const active = bundles.filter((b) => !b.archived);
  if (active.length === 0) {
    return <EmptyWell>No plans in this project yet.</EmptyWell>;
  }
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {active.map((bundle) => {
        const plan = bundle.plan;
        const isShowcase = plan != null && plan.path === showcasePath;
        const inner = (
          <>
            <span style={{ flex: 1 }}>
              {plan ? plan.title : bundle.id}
              {isShowcase ? <span style={{ color: "var(--wb-accent)" }}> · showcase</span> : null}
              {bundle.kind === "bundle" ? (
                <span style={{ color: "var(--wb-content-muted)" }}> · bundle</span>
              ) : null}
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
          <li key={bundle.path}>
            {plan ? (
              <a href={sectionHref(slug, "plans", plan.path)} style={listRowStyle}>
                {inner}
              </a>
            ) : (
              <div style={listRowStyle}>{inner}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function OverviewSection({ slug, projectName }: { slug: string; projectName: string }) {
  const homeQuery = useQuery({
    queryKey: ["home"],
    queryFn: () => api.getHome({}),
    refetchInterval: 30000,
  });
  const worktreesQuery = useQuery({
    queryKey: ["worktrees", slug],
    queryFn: () => api.getWorktrees({ slug }),
  });
  const plansQuery = useQuery({
    queryKey: ["plans", slug],
    queryFn: () => api.getPlans({ slug }),
  });

  if (homeQuery.isPending) return <SkeletonWell label={`overview for ${projectName}`} />;
  if (homeQuery.isError || !homeQuery.data.payload) {
    return (
      <ErrorWell
        section="Overview"
        message={homeQuery.data?.error ?? "the companion server did not answer."}
      />
    );
  }
  const home = homeQuery.data.payload as unknown as HomePayload;
  const row = home.projects.find((p) => p.slug === slug) ?? null;
  const worktreesPayload =
    (worktreesQuery.data?.payload as unknown as WorktreesPayload | null) ?? null;
  const plansFeed = (plansQuery.data?.payload as unknown as PlansFeed | null) ?? null;
  const showcase = row?.showcase ?? null;

  return (
    <section>
      <h1 style={sectionTitleStyle}>Overview</h1>
      {row?.degraded ? (
        <div
          role="status"
          style={{
            border: "1px solid var(--wb-border-strong)",
            borderRadius: "var(--wb-radius-md)",
            padding: "var(--wb-space-12) var(--wb-space-16)",
            color: "var(--wb-content-secondary)",
            marginBottom: "var(--wb-space-16)",
          }}
        >
          Some of this project's data is degraded — {row.reasons.join(" · ")}. What is shown is what
          could be read.
        </div>
      ) : null}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--wb-space-16)",
        }}
      >
        <ShowcaseCard slug={slug} projectName={projectName} showcase={showcase} />
        <WorktreesCard slug={slug} payload={worktreesPayload} fallback={row} />
        <Card anchor="overview/plans" title="Plans">
          {plansQuery.isPending ? (
            <SkeletonWell label="plans" />
          ) : plansFeed == null ? (
            <ErrorWell
              section="Plans"
              message={plansQuery.data?.error ?? "the plans feed did not answer."}
            />
          ) : (
            <PlanList
              slug={slug}
              bundles={plansFeed.bundles}
              showcasePath={showcase?.plan?.path ?? null}
            />
          )}
        </Card>
        <Card anchor="overview/strip" title="Todos & review">
          {row == null ? (
            <EmptyWell>This project is not in the current sweep.</EmptyWell>
          ) : (
            <div
              style={{
                display: "flex",
                gap: "var(--wb-space-24)",
                flexWrap: "wrap",
              }}
            >
              <a
                href={sectionHref(slug, "todos")}
                style={{ color: "var(--wb-accent)", textDecoration: "none" }}
              >
                Todos · <span className="num">{row.todos.total}</span>
                {row.todos.available
                  ? Object.entries(row.todos.counts)
                      .filter(([, n]) => n > 0)
                      .map(([status, n]) => ` · ${n} ${todoStatusLabel(status).toLowerCase()}`)
                      .join("")
                  : ""}
              </a>
              <a
                href={sectionHref(slug, "mockups")}
                style={{ color: "var(--wb-accent)", textDecoration: "none" }}
              >
                In triage · <span className="num">{row.review.triage_count}</span>
              </a>
              <a
                href={sectionHref(slug, "board")}
                style={{ color: "var(--wb-accent)", textDecoration: "none" }}
              >
                Board
              </a>
              {row.last_activity ? (
                <span style={metaStyle}>
                  last activity {formatDate(row.last_activity)} {formatRelative(row.last_activity)}
                </span>
              ) : null}
            </div>
          )}
        </Card>
      </div>
    </section>
  );
}
