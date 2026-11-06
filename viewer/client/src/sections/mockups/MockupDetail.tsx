// Drill-in for one entry (Subplan 06 Step 2 + 3): preview
// well with per-frame mode toggle, metadata, schema-driven
// State panel, Approval panel (the frozen snapshot an
// approval covered), the disposition bar, lifecycle actions,
// files, review log and history. Every write goes through
// the server's entry action (lib/ mutation, actor=viewer);
// a refusal — ruling required, uniformity findings, version
// conflict — is surfaced with the server's own reason,
// never as a silent failure or a spinner.
//
// Composition only (2026-11-05 follow-up split):
// useEntryDetail + Disposition + useEntryAnnotations.

import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Frame } from "../../components/Frame";
import { SegmentedControl } from "../../components/SegmentedControl";
import { StateControls } from "../../components/StateControls";
import { useIsPhone } from "../../lib/responsive";
import { AnnotationList, AnnotationThreadCard, SelectionTintStyle } from "../Annotations";
import { ApprovalCard } from "./ApprovalCard";
import { ApproveSheet, DispositionCard, useDisposition } from "./Disposition";
import { FilePanel } from "./FilePanel";
import { HistoryList, ReviewLog } from "./HistoryLog";
import { EntryBadges, hasState, PreviewSummary } from "./helpers";
import { LifecycleCard } from "./LifecycleCard";
import { MetaCard } from "./meta";
import type { FullEntry } from "./types";
import { SelectionComposer, useEntryAnnotations } from "./useEntryAnnotations";
import { useEntryDetail } from "./useEntryDetail";

export function MockupDetail({
  slug,
  projectName,
  entryId,
  feedEntry,
  onClose,
  onMutated,
}: {
  slug: string;
  projectName: string;
  entryId: string;
  feedEntry: FullEntry | null;
  onClose: () => void;
  onMutated: () => void;
}) {
  const isPhone = useIsPhone();
  const [frameMode, setFrameMode] = useState<"light" | "dark">("light");
  const [palette, setPalette] = useState("olive");

  useEffect(() => {
    setPalette(document.documentElement.getAttribute("data-palette") ?? "olive");
  }, []);

  const {
    detailQuery,
    detail,
    detailError,
    entry,
    derived,
    approval,
    draftState,
    setDraftState,
    draftDirty,
    latestReview,
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
        <p style={{ color: "var(--wb-content-muted)" }}>Loading {entryId}…</p>
      </section>
    );
  }
  if (!entry) {
    return (
      <section data-anchor="mockups/entry-sheet">
        <Button variant="ghost" onClick={onClose}>
          ← All mockups
        </Button>
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          Mockups: {detailError ?? `entry ${entryId} could not be loaded.`}
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
          ← All mockups
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
          <div data-palette={palette} data-mode={frameMode}>
            <Frame
              anchor="mockups/exhibit-stage"
              title={entry.title}
              viewportLabel={`${entry.source_kind} · ${frameMode}`}
              archived={entry.archived}
              headerActions={
                <SegmentedControl
                  options={[
                    { value: "light", label: "Light" },
                    { value: "dark", label: "Dark" },
                  ]}
                  value={frameMode}
                  onChange={setFrameMode}
                  ariaLabel="Preview mode"
                />
              }
              footer={
                <EntryBadges derived={derived} approval={approval} needsChanges={needsChanges} />
              }
            >
              <PreviewSummary entry={entry} values={draftState ?? undefined} />
            </Frame>
          </div>

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

          <DispositionCard projectName={projectName} disposition={disposition} />
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

          {hasState(entry) && draftState ? (
            <div>
              <StateControls
                anchor="mockups/state-card"
                schema={entry.state_schema}
                values={draftState}
                onChange={(key, value) =>
                  setDraftState((prev) => ({ ...(prev ?? {}), [key]: value }))
                }
                title="State"
              />
              {draftDirty ? (
                <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
                  Unsaved state changes — the preview reflects them; the approval coverage below
                  still describes the recorded state.
                </p>
              ) : null}
              <div style={{ marginTop: "var(--wb-space-8)" }}>
                <Button
                  variant="secondary"
                  disabled={busy || !draftDirty}
                  onClick={() =>
                    runAction({
                      verb: "set-state",
                      state: draftState,
                      expect_version: entry.version,
                    })
                  }
                >
                  Save state
                </Button>
              </div>
            </div>
          ) : (
            <Card title="State" anchor="mockups/state-card">
              <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
                No state schema declared — this entry has no editable internal state.
              </p>
            </Card>
          )}

          <ApprovalCard approval={approval} latestReview={latestReview} />

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

      <ApproveSheet
        entry={entry}
        approval={approval}
        draftDirty={draftDirty}
        disposition={disposition}
      />
    </section>
  );
}
