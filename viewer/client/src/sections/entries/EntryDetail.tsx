// Drill-in for one entry (Subplan 06 Step 2 + 3): the
// entry's page rendered in the stage (2026-11-10)
// beside the recorded-state summary the
// annotation machinery selects into, metadata, lifecycle
// actions, files, review log and history. Every write
// goes through the server's entry action (lib/ mutation,
// actor=viewer); a refusal — ruling required, uniformity
// findings, version conflict — is surfaced with the
// server's own reason, never as a silent failure or a
// spinner. The viewer's own state controls retired with
// the byte route, and its review disposition retired with
// the hosted route: an entry's questions live in its page
// now, and answers are recorded by transcription in the
// owning thread (SPEC §5.1). Since the 2026-11-10
// unification this one drill-in serves every kind — the
// retired sibling detail for kind `artifact` composed
// the same cards over the same blocks, and its surfaces
// (stage, metadata, lifecycle, files, review log,
// history) all live here.
//
// Composition only (2026-11-05 follow-up split):
// useEntryDetail + Disposition + useEntryAnnotations.

import { useRef } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useIsPhone } from "../../lib/responsive";
import { AnnotationList, AnnotationThreadCard, SelectionTintStyle } from "./Annotations";
import { useDisposition } from "./Disposition";
import { FilePanel } from "./FilePanel";
import { HistoryList, ReviewLog } from "./HistoryLog";
import { EntryBadges, OwnerLine, PreviewSummary } from "./helpers";
import { LifecycleCard } from "./LifecycleCard";
import { MetaCard } from "./meta";
import { PreviewStage } from "./PreviewStage";
import type { FullEntry } from "./types";
import { SelectionComposer, useEntryAnnotations } from "./useEntryAnnotations";
import { useEntryDetail } from "./useEntryDetail";

export function EntryDetail({
  slug,
  entryId,
  feedEntry,
  onClose,
  onMutated,
}: {
  slug: string;
  entryId: string;
  feedEntry: FullEntry | null;
  onClose: () => void;
  onMutated: () => void;
}) {
  const isPhone = useIsPhone();

  const {
    detailQuery,
    detail,
    detailError,
    entry,
    derived,
    approval,
    needsChanges,
    supersedeCandidates,
    candidateLabel,
    supersededByTitle,
  } = useEntryDetail(slug, entryId, feedEntry);

  const disposition = useDisposition({ slug, entryId, entry, onMutated });
  const { actionError, actionNotice, runAction, busy } = disposition;

  const detailRef = useRef<HTMLElement | null>(null);
  const annotations = useEntryAnnotations(slug, entryId, entry, detailRef);
  const { threads, count, selected, statusById, pinnedThreads } = annotations;

  if (detailQuery.isPending && !entry) {
    return (
      <section data-anchor="mockups/entry-sheet">
        <p style={{ color: "var(--wb-content-secondary)" }}>Loading {entryId}…</p>
      </section>
    );
  }
  if (!entry) {
    return (
      <section data-anchor="mockups/entry-sheet">
        <Button variant="ghost" onClick={onClose}>
          ← All entries
        </Button>
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          Entries: {detailError ?? `entry ${entryId} could not be loaded.`}
        </p>
      </section>
    );
  }

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions lint/a11y/useKeyWithClickEvents: the drill-in root only OBSERVES clicks/selection to select components and arm the annotation composer; it has no activation behavior of its own
    <section
      data-anchor="mockups/entry-sheet"
      data-annotation-scope="true"
      ref={detailRef}
      onClick={annotations.onDetailClick}
      onMouseUp={annotations.onDetailMouseUp}
    >
      <SelectionTintStyle />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-12)",
          flexWrap: "wrap",
          marginBottom: "var(--wb-space-16)",
        }}
      >
        <Button variant="ghost" onClick={onClose}>
          ← All entries
        </Button>
        <h2
          style={{
            fontSize: "var(--wb-font-size-lg)",
            lineHeight: "var(--wb-line-height-lg)",
            fontWeight: 600,
            margin: 0,
          }}
        >
          {entry.title}
        </h2>
        <EntryBadges derived={derived} approval={approval} needsChanges={needsChanges} />
        <OwnerLine entry={entry} />
        {entry.archived ? (
          <span style={{ color: "var(--wb-content-secondary)" }}>Archived</span>
        ) : null}
      </div>

      {detailError ? (
        <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
          Entry detail (history and files) could not be loaded — {detailError} What follows is the
          feed's record for this entry.
        </p>
      ) : null}
      {actionError ? (
        <p
          role="alert"
          style={{
            color: "var(--wb-danger)",
            border: "1px solid var(--wb-danger)",
            borderRadius: "var(--wb-radius-md)",
            padding: "var(--wb-space-12) var(--wb-space-16)",
          }}
        >
          {actionError}
        </p>
      ) : null}
      {actionNotice ? (
        <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
          {actionNotice}
        </p>
      ) : null}

      <div
        style={{
          display: "grid",
          // Phone: one column — the stage (with its
          // composer and pinned threads) first, then the
          // card column stacked under it (§20: the drill-in
          // carries its per-exhibit annotation list).
          // Phone: minmax(0, 1fr), not 1fr — a bare 1fr is
          // minmax(auto, 1fr) and the stage's min-content
          // (frame header + summary) blows the track out to
          // 398px in a 358px column (measured on the
          // drill-in). Desktop's 7fr/5fr is untouched.
          gridTemplateColumns: isPhone ? "minmax(0, 1fr)" : "7fr 5fr",
          gap: "var(--wb-space-24)",
          alignItems: "start",
        }}
      >
        <div style={isPhone ? { minWidth: 0 } : { position: "sticky", top: "var(--wb-space-16)" }}>
          <PreviewStage slug={slug} entry={entry} />
          {/* The recorded state, ungrouped (F5, ruling q3
              retitle-and-ungroup): the stage above IS the
              preview — the rendered page in its own frame,
              titled with the entry's title. The recorded
              state is not a second preview of the entry and
              does not wear its title or a frame of its own;
              it is a headed record under the stage. The
              section stays inside the annotation scope —
              the machinery selects into this surface. */}
          <section aria-label="Recorded state" style={{ marginTop: "var(--wb-space-16)" }}>
            <h3
              style={{
                fontSize: "var(--wb-font-size-xs)",
                lineHeight: "var(--wb-line-height-xs)",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                color: "var(--wb-content-secondary)",
                margin: "0 0 var(--wb-space-8)",
              }}
            >
              Recorded state
            </h3>
            <PreviewSummary entry={entry} />
          </section>

          {selected ? (
            <SelectionComposer
              slug={slug}
              entryId={entryId}
              selected={selected}
              onClose={() => annotations.setSelected(null)}
            />
          ) : null}
          {pinnedThreads.length > 0 ? (
            <div
              style={{
                display: "grid",
                gap: "var(--wb-space-8)",
                marginTop: "var(--wb-space-16)",
              }}
            >
              {pinnedThreads.map((t) => (
                <AnnotationThreadCard key={t.root.id} slug={slug} thread={t} />
              ))}
            </div>
          ) : null}
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "var(--wb-space-16)",
            minWidth: isPhone ? 0 : undefined,
          }}
        >
          <MetaCard entry={entry} derived={derived} supersededByTitle={supersededByTitle} />

          <LifecycleCard
            entry={entry}
            derived={derived}
            busy={busy}
            runAction={runAction}
            statusChoice={disposition.statusChoice}
            setStatusChoice={disposition.setStatusChoice}
            ruling={disposition.ruling}
            setRuling={disposition.setRuling}
            gate={disposition.gate}
            setGate={disposition.setGate}
            acceptDrift={disposition.acceptDrift}
            setAcceptDrift={disposition.setAcceptDrift}
            supersedeTarget={disposition.supersedeTarget}
            setSupersedeTarget={disposition.setSupersedeTarget}
            supersedeCandidates={supersedeCandidates}
            candidateLabel={candidateLabel}
          />

          <div data-annotation-ui="true">
            <Card title={`Annotations · ${count}`} anchor="mockups/annotations-card">
              {threads.length === 0 ? (
                <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
                  No annotations yet — click a component in the stage, or select text inside one, to
                  annotate this exhibit.
                </p>
              ) : (
                <AnnotationList
                  slug={slug}
                  threads={threads}
                  statusOf={(root) => (statusById[root.id] === "moved" ? "moved" : "located")}
                />
              )}
            </Card>
          </div>

          {detail ? (
            <>
              <div data-anchor="mockups/files-card">
                <FilePanel
                  slug={slug}
                  entryId={entryId}
                  files={detail.files}
                  configPath={entry.config_path ?? null}
                  onMutated={disposition.invalidate}
                />
              </div>
              <div data-anchor="mockups/review-log-card">
                <ReviewLog history={detail.history} />
              </div>
              <div data-anchor="mockups/history-card">
                <HistoryList history={detail.history} />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
