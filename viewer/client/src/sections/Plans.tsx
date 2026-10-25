// Plans — shell-checkpoint frame (Subplan 05). The reading
// view (structured steps, diagrams, source toggle) is
// Subplan 07; this frame reads the project's real plans feed
// and lists what exists — title, bucket, step count — or
// the honest empty state.

import { useQuery } from "@tanstack/react-query";
import { api, type PlansFeed } from "../lib/api";
import { formatDate, formatRelative } from "../lib/format";
import { planBucketLabel } from "../lib/labels";
import { sectionHref } from "../lib/routing";
import {
  DegradedBanner,
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";

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
  const feed = payload as unknown as PlansFeed;
  const active = feed.plans.filter((plan) => !plan.archived);
  const archived = feed.plans.filter((plan) => plan.archived);

  return (
    <section>
      <h1 style={sectionTitleStyle}>Plans</h1>
      <DegradedBanner feed={feed} />
      {item ? (
        <p style={{ color: "var(--wb-content-secondary)" }}>
          <a href={sectionHref(slug, "plans")} style={{ color: "var(--wb-accent)" }}>
            All plans
          </a>{" "}
          · <span className="mono">{item}</span>
        </p>
      ) : null}
      {feed.plans.length === 0 ? (
        <EmptyWell>
          {feed.available
            ? `No plans in ${projectName} yet.`
            : `No plans for ${projectName} — this project declares no plans directory.`}
        </EmptyWell>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {active.map((plan) => (
            <li key={plan.path}>
              <a href={sectionHref(slug, "plans", plan.path)} style={listRowStyle}>
                <span style={{ flex: 1 }}>
                  {plan.title}
                  {!plan.conforming ? (
                    <span style={{ color: "var(--wb-content-secondary)" }}> · source format</span>
                  ) : null}
                </span>
                <span style={metaStyle}>{planBucketLabel(plan.status_bucket)}</span>
                <span style={metaStyle}>
                  <span className="num">{plan.step_count}</span> steps
                </span>
                <span style={metaStyle}>
                  {formatDate(plan.modified)} {formatRelative(plan.modified)}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {archived.length > 0 ? (
        <p style={{ color: "var(--wb-content-muted)" }}>
          <span className="num">{archived.length}</span> finished plans in the archive.
        </p>
      ) : null}
    </section>
  );
}
