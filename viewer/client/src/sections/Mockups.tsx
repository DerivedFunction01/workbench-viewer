// Mockups — the registry browser + review surface
// (Subplan 06, founding Step 5). Triage lane first (the
// section's entry view), then the storyboard: frames at a
// 300px tile minimum, or contact-sheet mode where an entry
// expands into its featured states as mini-frames. Archive
// sits behind a toggle. Drill-in is the entry sheet. All
// data is the project's real feed; project zero's empty
// registry renders as the honest empty state.

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
import { kindLabel, ruledStatusLabel } from "../lib/labels";
import {
  DEFAULT_FILTERS,
  EntryBadges,
  EntryChip,
  type FilterState,
  featuredStates,
  filterEntries,
  isRuledStatus,
  PreviewSummary,
} from "./mockups/helpers";
import { MockupDetail } from "./mockups/MockupDetail";
import type { Envelope, FullEntry, MockupsFeedFull } from "./mockups/types";
import { ENTRY_KINDS, RULED_STATUSES } from "./mockups/types";
import { DegradedBanner, ErrorWell, SkeletonWell, sectionTitleStyle } from "./shared";

type ViewMode = "storyboard" | "contact-sheet";

const headingStyle: React.CSSProperties = {
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--wb-content-secondary)",
  margin: "0 0 var(--wb-space-8)",
};

export function MockupsSection({ slug, projectName }: { slug: string; projectName: string }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("storyboard");
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [frameModes, setFrameModes] = useState<Record<string, "light" | "dark">>({});
  const [palette] = useState(
    () =>
      (typeof document !== "undefined" && document.documentElement.getAttribute("data-palette")) ||
      "olive",
  );

  const activeQuery = useQuery({
    queryKey: ["mockups", slug, false],
    queryFn: () => api.getMockups({ slug }),
  });
  const archivedQuery = useQuery({
    queryKey: ["mockups", slug, true],
    queryFn: () => api.getMockups({ slug, archived: true }),
    enabled: showArchived,
  });

  const feedOf = (data: unknown): MockupsFeedFull | null => {
    const envelope = data as Envelope | undefined;
    if (envelope?.status !== 200 || !envelope?.payload) return null;
    return envelope.payload as MockupsFeedFull;
  };
  const feed = feedOf(activeQuery.data);
  const archivedFeed = feedOf(archivedQuery.data);

  const triageIds = useMemo(() => new Set((feed?.triage ?? []).map((item) => item.id)), [feed]);
  const triageReasons = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const item of feed?.triage ?? []) map.set(item.id, item.reasons);
    return map;
  }, [feed]);
  const entryById = useMemo(() => {
    const map = new Map<string, FullEntry>();
    for (const entry of feed?.entries ?? []) map.set(entry.id, entry);
    for (const entry of archivedFeed?.entries ?? []) map.set(entry.id, entry);
    return map;
  }, [feed, archivedFeed]);

  if (activeQuery.isPending) return <SkeletonWell label={`mockups for ${projectName}`} />;
  if (activeQuery.isError) {
    return <ErrorWell section="Mockups" message="the section feed could not be loaded." />;
  }
  if (!feed) {
    const envelope = activeQuery.data as Envelope | undefined;
    return (
      <ErrorWell
        section="Mockups"
        message={envelope?.error ?? "the companion server did not answer."}
      />
    );
  }

  if (selectedId) {
    return (
      <section>
        <h1 style={sectionTitleStyle}>Mockups</h1>
        <MockupDetail
          slug={slug}
          projectName={projectName}
          entryId={selectedId}
          feedEntry={entryById.get(selectedId) ?? null}
          onClose={() => setSelectedId(null)}
          onMutated={() => {
            queryClient.invalidateQueries({ queryKey: ["mockups", slug] });
          }}
        />
      </section>
    );
  }

  const allEntries = [...feed.entries, ...(showArchived ? (archivedFeed?.entries ?? []) : [])];
  const visible = filterEntries(allEntries, filters, triageIds);
  const kindsPresent = ENTRY_KINDS.filter((kind) => allEntries.some((e) => e.kind === kind));
  const filtersActive =
    filters.statuses.size > 0 ||
    filters.kind !== "" ||
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
      <h1 style={sectionTitleStyle}>Mockups</h1>
      <DegradedBanner feed={feed} />
      {reconcileProblems.length > 0 ? (
        <div style={{ marginBottom: "var(--wb-space-16)" }}>
          <KitDegradedBanner
            message={`Mockups: reconciliation found ${reconcileProblems.length} problem(s) between the registry and the entry folders.`}
            detail="Run wb validate for the findings and their repairs."
          />
        </div>
      ) : null}
      {feed.reconcile?.error ? (
        <div style={{ marginBottom: "var(--wb-space-16)" }}>
          <KitDegradedBanner
            message="Mockups: reconciliation could not be checked for this project."
            detail={feed.reconcile.error}
          />
        </div>
      ) : null}

      {allEntries.length === 0 ? (
        <EmptyState
          message={
            feed.available
              ? `No mockups in ${projectName} yet — nothing awaiting review, nothing stale.`
              : `No mockups for ${projectName} — this project's registry is not set up, so there is nothing to review.`
          }
          action={
            <Toggle checked={showArchived} onChange={setShowArchived} label="Show archived" />
          }
        />
      ) : (
        <>
          <div data-anchor="mockups/triage-lane" style={{ marginBottom: "var(--wb-space-24)" }}>
            <h2 style={headingStyle}>
              Triage · <span className="num">{feed.triage.length}</span> awaiting review
            </h2>
            {feed.triage.length === 0 ? (
              <EmptyState message="Nothing awaiting review" />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--wb-space-8)" }}>
                {feed.triage.map((item) => {
                  const entry = entryById.get(item.id);
                  const needsChanges = item.reasons.some((r) => r.includes("needs-changes"));
                  return (
                    <TriageRow
                      key={item.id}
                      title={item.title}
                      meta={item.reasons.join(" · ")}
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
                      onOpen={() => setSelectedId(item.id)}
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
                { value: "storyboard", label: "Storyboard" },
                { value: "contact-sheet", label: "Contact sheet" },
              ]}
              value={viewMode}
              onChange={setViewMode}
              ariaLabel="View mode"
            />
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
              <span className="sr-only">Kind</span>
              <select
                aria-label="Kind"
                value={filters.kind}
                onChange={(event) => setFilters((prev) => ({ ...prev, kind: event.target.value }))}
                style={{
                  minHeight: "38px",
                  background: "var(--wb-surface-2)",
                  color: "var(--wb-content-primary)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-button-radius)",
                  padding: "0 var(--wb-space-8)",
                }}
              >
                <option value="">All kinds</option>
                {kindsPresent.map((kind) => (
                  <option key={kind} value={kind}>
                    {kindLabel(kind)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Search mockups</span>
              <input
                type="search"
                aria-label="Search mockups"
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
            <EmptyState message="No mockups match these filters" />
          ) : viewMode === "storyboard" ? (
            <div
              data-anchor="mockups/storyboard-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: "var(--wb-space-16)",
              }}
            >
              {visible.map((entry) => {
                const mode = frameModes[entry.id] ?? "light";
                const needsChanges = (triageReasons.get(entry.id) ?? []).some((r) =>
                  r.includes("needs-changes"),
                );
                return (
                  <div key={entry.id} data-palette={palette} data-mode={mode}>
                    <Frame
                      title={entry.title}
                      viewportLabel={`${entry.source_kind} · ${mode}`}
                      archived={entry.archived}
                      headerActions={
                        <SegmentedControl
                          options={[
                            { value: "light", label: "Light" },
                            { value: "dark", label: "Dark" },
                          ]}
                          value={mode}
                          onChange={(next) =>
                            setFrameModes((prev) => ({ ...prev, [entry.id]: next }))
                          }
                          ariaLabel={`Preview mode for ${entry.title}`}
                        />
                      }
                      footer={
                        <>
                          <EntryChip entry={entry} />
                          <EntryBadges
                            derived={entry.derived}
                            approval={entry.approval}
                            needsChanges={needsChanges}
                          />
                          <Button variant="ghost" onClick={() => setSelectedId(entry.id)}>
                            Open
                          </Button>
                        </>
                      }
                    >
                      <PreviewSummary entry={entry} />
                    </Frame>
                  </div>
                );
              })}
            </div>
          ) : (
            <div data-anchor="mockups/contact-sheet">
              {visible.map((entry) => (
                <div key={entry.id} style={{ marginBottom: "var(--wb-space-16)" }}>
                  <h3
                    style={{
                      fontSize: "var(--wb-font-size-sm)",
                      margin: "0 0 var(--wb-space-8)",
                      display: "flex",
                      gap: "var(--wb-space-8)",
                      alignItems: "center",
                    }}
                  >
                    {entry.title} <EntryChip entry={entry} />
                    <span style={{ color: "var(--wb-content-muted)", fontWeight: 400 }}>
                      {ruledStatusLabel(entry.status)} · featured states are state variations of
                      this one entry
                    </span>
                  </h3>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
                      gap: "var(--wb-space-12)",
                    }}
                  >
                    {featuredStates(entry).map((state) => (
                      <Frame
                        key={state.label}
                        title={state.label}
                        archived={entry.archived}
                        footer={
                          <Button variant="ghost" onClick={() => setSelectedId(entry.id)}>
                            Open
                          </Button>
                        }
                      >
                        <PreviewSummary entry={entry} values={state.values} />
                      </Frame>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
