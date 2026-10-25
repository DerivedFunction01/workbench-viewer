// Mockups — shell-checkpoint frame (Subplan 05). The full
// storyboard (grid, contact sheet, drill-in, review flow) is
// Subplan 06; this frame already reads the project's real
// mockups feed and renders its truthful state: the triage
// count, the entries that exist, or the honest empty state.

import { useQuery } from "@tanstack/react-query";
import { api, type MockupsFeed } from "../lib/api";
import { formatDate, formatRelative } from "../lib/format";
import { ruledStatusLabel } from "../lib/labels";
import { DegradedBanner, EmptyWell, ErrorWell, SkeletonWell, sectionTitleStyle } from "./shared";

export function MockupsSection({ slug, projectName }: { slug: string; projectName: string }) {
  const query = useQuery({
    queryKey: ["mockups", slug],
    queryFn: () => api.getMockups({ slug }),
  });

  if (query.isPending) return <SkeletonWell label={`mockups for ${projectName}`} />;
  if (query.isError) {
    return <ErrorWell section="Mockups" message="the section feed could not be loaded." />;
  }
  const { payload, error } = query.data;
  if (!payload) {
    return (
      <ErrorWell section="Mockups" message={error ?? "the companion server did not answer."} />
    );
  }
  const feed = payload as unknown as MockupsFeed;

  return (
    <section>
      <h1 style={sectionTitleStyle}>Mockups</h1>
      <DegradedBanner feed={feed} />
      {feed.entries.length === 0 ? (
        <EmptyWell>
          {feed.available
            ? `No mockups in ${projectName} yet — nothing awaiting review, nothing stale.`
            : `No mockups for ${projectName} — this project's registry is not set up, so there is nothing to review.`}
        </EmptyWell>
      ) : (
        <>
          <p style={{ color: "var(--wb-content-secondary)" }}>
            <span className="num">{feed.triage.length}</span> awaiting review ·{" "}
            <span className="num">{feed.entries.length}</span> total
          </p>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {feed.entries.map((entry) => (
              <li
                key={entry.id}
                style={{
                  borderBottom: "1px solid var(--wb-border-default)",
                  padding: "var(--wb-space-8) 0",
                }}
              >
                <span style={{ fontWeight: 600 }}>{entry.title}</span>{" "}
                <span style={{ color: "var(--wb-content-secondary)" }}>
                  {ruledStatusLabel(entry.status)}
                </span>{" "}
                <span style={{ color: "var(--wb-content-muted)" }}>
                  {formatDate(entry.updated_at as string | undefined)}{" "}
                  {formatRelative(entry.updated_at as string | undefined)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
