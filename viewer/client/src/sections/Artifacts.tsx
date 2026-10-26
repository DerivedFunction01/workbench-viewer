// Artifacts — the sibling collection beside Mockups
// (SPEC §8.5): disposition-bearing items of kind
// `artifact` only, served by their own feed. List +
// drill-in in v1 (the storyboard and contact-sheet modes
// stay Mockups-only). Unlike Mockups, the section honors
// its route item segment — a Board or message link to an
// item opens its detail directly. Per-item messages mount
// under the open detail, anchored to the entry exactly as
// they do for mockups.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { DegradedBanner as KitDegradedBanner } from "../components/DegradedBanner";
import { EmptyState } from "../components/EmptyState";
import { Frame } from "../components/Frame";
import { SegmentedControl } from "../components/SegmentedControl";
import { Toggle } from "../components/Toggle";
import { TriageRow } from "../components/TriageRow";
import { api } from "../lib/api";
import { sectionHref } from "../lib/routing";
import { ArtifactDetail } from "./artifacts/ArtifactDetail";
import type { ArtifactsFeed, Envelope, FullEntry } from "./artifacts/types";
import { AnchoredComment } from "./inbox/AnchoredComment";
import {
  DEFAULT_FILTERS,
  EntryBadges,
  EntryChip,
  type FilterState,
  filterEntries,
  isRuledStatus,
  PreviewSummary,
} from "./mockups/helpers";
import { RULED_STATUSES } from "./mockups/types";
import { DegradedBanner, ErrorWell, SkeletonWell, sectionTitleStyle } from "./shared";

const headingStyle: React.CSSProperties = {
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--wb-content-secondary)",
  margin: "0 0 var(--wb-space-8)",
};

export function ArtifactsSection({
  slug,
  projectName,
  item,
}: {
  slug: string;
  projectName: string;
  item: string | null;
}) {
  const queryClient = useQueryClient();
  const [localSelected, setLocalSelected] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  // The route item segment wins over local selection: a
  // link to an item opens its detail from birth (SPEC
  // §8.5), and closing it returns to the list route.
  const selectedId = item ?? localSelected;
  const closeDetail = () => {
    setLocalSelected(null);
    if (item != null && typeof window !== "undefined") {
      window.location.hash = sectionHref(slug, "artifacts");
    }
  };

  const activeQuery = useQuery({
    queryKey: ["artifacts", slug, false],
    queryFn: () => api.getArtifacts({ slug }),
  });
  const archivedQuery = useQuery({
    queryKey: ["artifacts", slug, true],
    queryFn: () => api.getArtifacts({ slug, archived: true }),
    enabled: showArchived,
  });

  const feedOf = (data: unknown): ArtifactsFeed | null => {
    const envelope = data as Envelope | undefined;
    if (envelope?.status !== 200 || !envelope?.payload) return null;
    return envelope.payload as ArtifactsFeed;
  };
  const feed = feedOf(activeQuery.data);
  const archivedFeed = feedOf(archivedQuery.data);

  const triageIds = useMemo(() => new Set((feed?.triage ?? []).map((t) => t.id)), [feed]);
  const triageReasons = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const t of feed?.triage ?? []) map.set(t.id, t.reasons);
    return map;
  }, [feed]);
  const entryById = useMemo(() => {
    const map = new Map<string, FullEntry>();
    for (const entry of feed?.entries ?? []) map.set(entry.id, entry);
    for (const entry of archivedFeed?.entries ?? []) map.set(entry.id, entry);
    return map;
  }, [feed, archivedFeed]);

  if (activeQuery.isPending) return <SkeletonWell label={`artifacts for ${projectName}`} />;
  if (activeQuery.isError) {
    return <ErrorWell section="Artifacts" message="the section feed could not be loaded." />;
  }
  if (!feed) {
    const envelope = activeQuery.data as Envelope | undefined;
    return (
      <ErrorWell
        section="Artifacts"
        message={envelope?.error ?? "the companion server did not answer."}
      />
    );
  }

  if (selectedId) {
    return (
      <section>
        <h1 style={sectionTitleStyle}>Artifacts</h1>
        <ArtifactDetail
          slug={slug}
          projectName={projectName}
          entryId={selectedId}
          feedEntry={entryById.get(selectedId) ?? null}
          onClose={closeDetail}
          onMutated={() => {
            queryClient.invalidateQueries({ queryKey: ["artifacts", slug] });
          }}
        />
        <div style={{ marginTop: "var(--wb-space-16)" }}>
          <AnchoredComment
            slug={slug}
            projectName={projectName}
            anchorType="entry"
            anchorRef={selectedId}
          />
        </div>
      </section>
    );
  }

  const allEntries = [...feed.entries, ...(showArchived ? (archivedFeed?.entries ?? []) : [])];
  const visible = filterEntries(allEntries, filters, triageIds);
  const filtersActive =
    filters.statuses.size > 0 ||
    filters.staleOnly ||
    filters.triageOnly ||
    filters.search.trim() !== "";
  const reconcileProblems =
    feed.reconcile && feed.reconcile.status !== "ok" ? feed.reconcile.problems : [];

  const toggleStatus = (status: string) => {
    setFilters((prev) => {
      const next = new Set(prev.statuses);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return { ...prev, statuses: next };
    });
  };

  return (
    <section>
      <h1 style={sectionTitleStyle}>Artifacts</h1>
      <DegradedBanner feed={feed} />
      {reconcileProblems.length > 0 ? (
        <div style={{ marginBottom: "var(--wb-space-16)" }}>
          <KitDegradedBanner
            message={`Artifacts: reconciliation found ${reconcileProblems.length} problem(s) between the registry and the entry folders.`}
            detail="Run wb validate for the findings and their repairs."
          />
        </div>
      ) : null}
      {feed.reconcile?.error ? (
        <div style={{ marginBottom: "var(--wb-space-16)" }}>
          <KitDegradedBanner
            message="Artifacts: reconciliation could not be checked for this project."
            detail={feed.reconcile.error}
          />
        </div>
      ) : null}

      {allEntries.length === 0 ? (
        <EmptyState
          message={
            feed.available
              ? `No artifacts in ${projectName} yet — nothing awaiting a ruling, nothing answered.`
              : `No artifacts for ${projectName} — this project's registry is not set up, so there is nothing to rule on.`
          }
          action={
            <Toggle checked={showArchived} onChange={setShowArchived} label="Show archived" />
          }
        />
      ) : (
        <>
          <div data-anchor="artifacts/triage-lane" style={{ marginBottom: "var(--wb-space-24)" }}>
            <h2 style={headingStyle}>
              Triage · <span className="num">{feed.triage.length}</span> awaiting review
            </h2>
            {feed.triage.length === 0 ? (
              <EmptyState message="Nothing awaiting review" />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--wb-space-8)" }}>
                {feed.triage.map((triageItem) => {
                  const entry = entryById.get(triageItem.id);
                  const needsChanges = triageItem.reasons.some((r) => r.includes("needs-changes"));
                  return (
                    <TriageRow
                      key={triageItem.id}
                      title={triageItem.title}
                      meta={triageItem.reasons.join(" · ")}
                      leading={entry ? <EntryChip entry={entry} /> : undefined}
                      badges={
                        entry ? (
                          <EntryBadges
                            derived={entry.derived}
                            approval={entry.approval}
                            needsChanges={needsChanges}
                          />
                        ) : undefined
                      }
                      onOpen={() => setLocalSelected(triageItem.id)}
                    />
                  );
                })}
              </div>
            )}
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--wb-space-12)",
              alignItems: "center",
              marginBottom: "var(--wb-space-16)",
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--wb-space-4)" }}>
              {RULED_STATUSES.map((status) =>
                isRuledStatus(status) ? (
                  <Chip
                    key={status}
                    status={status}
                    pressed={filters.statuses.has(status)}
                    onPress={() => toggleStatus(status)}
                  />
                ) : null,
              )}
            </div>
            <SegmentedControl
              options={[
                { value: "recent", label: "Recently changed" },
                { value: "unverified", label: "Oldest unverified" },
                { value: "title", label: "Title" },
              ]}
              value={filters.sort}
              onChange={(sort) => setFilters((prev) => ({ ...prev, sort }))}
              ariaLabel="Sort entries"
            />
            <Toggle
              checked={filters.triageOnly}
              onChange={(checked) => setFilters((prev) => ({ ...prev, triageOnly: checked }))}
              label="Triage only"
            />
            <Toggle
              checked={filters.staleOnly}
              onChange={(checked) => setFilters((prev) => ({ ...prev, staleOnly: checked }))}
              label="Stale only"
            />
            <Toggle checked={showArchived} onChange={setShowArchived} label="Show archived" />
            <label>
              <span className="sr-only">Search artifacts</span>
              <input
                type="search"
                aria-label="Search artifacts"
                placeholder="Search title, id, source…"
                value={filters.search}
                onChange={(event) =>
                  setFilters((prev) => ({ ...prev, search: event.target.value }))
                }
                style={{
                  minHeight: "38px",
                  background: "var(--wb-surface-2)",
                  color: "var(--wb-content-primary)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-button-radius)",
                  padding: "0 var(--wb-space-8)",
                }}
              />
            </label>
          </div>

          <p style={{ color: "var(--wb-content-secondary)" }}>
            <span className="num">{visible.length}</span> of{" "}
            <span className="num">{allEntries.length}</span> entries
            {showArchived ? " (archive included)" : ""}
            {filtersActive ? (
              <>
                {" · "}
                <Button variant="ghost" onClick={() => setFilters(DEFAULT_FILTERS)}>
                  Clear filters
                </Button>
              </>
            ) : null}
          </p>

          {visible.length === 0 ? (
            <EmptyState message="No artifacts match these filters" />
          ) : (
            <div
              data-anchor="artifacts/entry-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: "var(--wb-space-16)",
              }}
            >
              {visible.map((entry) => {
                const needsChanges = (triageReasons.get(entry.id) ?? []).some((r) =>
                  r.includes("needs-changes"),
                );
                return (
                  <Frame
                    key={entry.id}
                    title={entry.title}
                    viewportLabel={`${entry.source_kind} · ${entry.main_file ?? "no main file"}`}
                    archived={entry.archived}
                    footer={
                      <>
                        <EntryChip entry={entry} />
                        <EntryBadges
                          derived={entry.derived}
                          approval={entry.approval}
                          needsChanges={needsChanges}
                        />
                        <Button variant="ghost" onClick={() => setLocalSelected(entry.id)}>
                          Open
                        </Button>
                      </>
                    }
                  >
                    <PreviewSummary entry={entry} />
                  </Frame>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}
