// Drill-in for one artifact item — the sibling of
// MockupDetail (SPEC §8.5): the same cards, the same
// entryAction verbs, the same confirm-approve sheet
// semantics, composed over the shared blocks. Two
// deliberate differences from the mockup pane: the stage
// renders the item's main file as a live preview (a
// sandboxed, scriptless iframe fed by the guarded peek
// path — entry content is never executed), and there is
// no exhibit-annotation machinery (the sandboxed frame
// cannot be selected into; per-item messages mount under
// the detail in the section, as they do for mockups).
// The item's questions are its state schema; Save state
// records the answers, Approve binds them by hash, and
// Copy answers JSON carries them out as text.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Sheet } from "../../components/Sheet";
import { StateControls, type StateValues } from "../../components/StateControls";
import { api } from "../../lib/api";
import { formatDate, formatDateTime, formatShortHash } from "../../lib/format";
import { ruledStatusLabel } from "../../lib/labels";
import { useIsPhone } from "../../lib/responsive";
import { FilePanel } from "../mockups/FilePanel";
import { HistoryList, ReviewLog } from "../mockups/HistoryLog";
import { EntryBadges, hasState, OwnerLine, stateValues } from "../mockups/helpers";
import { RULED_STATUSES } from "../mockups/types";
import { labelStyle, MetaCard, MetaRow, toStateValues } from "./meta";
import { PreviewStage } from "./PreviewStage";
import type { ArtifactsFeed, EntryDetail, Envelope, FullEntry } from "./types";

type Disposition = "approve" | "needs-changes" | "stale";

export function ArtifactDetail({
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
  const queryClient = useQueryClient();
  const isPhone = useIsPhone();
  const [comment, setComment] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [approveComment, setApproveComment] = useState("");
  const [statusChoice, setStatusChoice] = useState("canonical");
  const [ruling, setRuling] = useState("");
  const [gate, setGate] = useState("");
  const [acceptDrift, setAcceptDrift] = useState(false);
  const [supersedeTarget, setSupersedeTarget] = useState("");
  const [copyNotice, setCopyNotice] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: ["entry", slug, entryId],
    queryFn: () => api.getEntry({ slug, entryId }),
  });
  // The collection's own feed — the supersede picker's
  // candidates and the "Superseded by" title lookup scope
  // to this collection (SPEC §8.5).
  const feedQuery = useQuery({
    queryKey: ["artifacts", slug, false],
    queryFn: () => api.getArtifacts({ slug }),
  });
  const feedEnvelope = feedQuery.data as Envelope | undefined;
  const feed: ArtifactsFeed | null =
    feedEnvelope && feedEnvelope.status === 200 && feedEnvelope.payload
      ? (feedEnvelope.payload as ArtifactsFeed)
      : null;
  const detailEnvelope = detailQuery.data as Envelope | undefined;
  const detail =
    detailEnvelope && detailEnvelope.status === 200
      ? (detailEnvelope.payload as EntryDetail)
      : null;
  const detailError =
    detailEnvelope && detailEnvelope.status !== 200
      ? (detailEnvelope.error ?? "the entry detail could not be loaded.")
      : null;

  // The feed row is a complete fallback for everything
  // except history/files, exactly as in the mockup pane.
  const entry: FullEntry | null = detail?.entry ?? feedEntry;
  const derived = detail?.derived ?? feedEntry?.derived ?? null;
  const approval = detail?.approval ?? feedEntry?.approval ?? null;

  const [draftState, setDraftState] = useState<StateValues | null>(() =>
    entry ? toStateValues(entry) : null,
  );

  useEffect(() => {
    if (entry) {
      setDraftState(toStateValues(entry));
      setStatusChoice(entry.status);
    }
  }, [entry]);

  const savedStateJson = useMemo(
    () => JSON.stringify(stateValues(entry ?? ({} as FullEntry))),
    [entry],
  );
  const draftDirty =
    draftState != null && entry != null && JSON.stringify(draftState) !== savedStateJson;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["entry", slug, entryId] });
    queryClient.invalidateQueries({ queryKey: ["artifacts", slug] });
    onMutated();
  };

  const actionMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.entryAction({ slug, entryId, body }) as Promise<Envelope>,
    onSuccess: (result, body) => {
      if (result.status === 200) {
        setActionError(null);
        setConfirmApprove(false);
        setActionNotice(`Recorded — ${String(body.verb)} applied to ${entryId}.`);
        if (result.payload) {
          queryClient.setQueryData(["entry", slug, entryId], {
            status: 200,
            payload: result.payload,
            error: null,
          });
        }
        invalidate();
      } else {
        setActionNotice(null);
        setActionError(result.error ?? `The server refused this action (status ${result.status}).`);
      }
    },
    onError: () => {
      setActionError("The action could not reach the companion server. Nothing was recorded.");
    },
  });
  const runAction = (body: Record<string, unknown>) => actionMutation.mutate(body);

  if (detailQuery.isPending && !entry) {
    return (
      <section data-anchor="artifacts/entry-sheet">
        <p style={{ color: "var(--wb-content-muted)" }}>Loading {entryId}…</p>
      </section>
    );
  }
  if (!entry) {
    return (
      <section data-anchor="artifacts/entry-sheet">
        <Button variant="ghost" onClick={onClose}>
          ← All artifacts
        </Button>
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          Artifacts: {detailError ?? `entry ${entryId} could not be loaded.`}
        </p>
      </section>
    );
  }

  const latestReview = detail?.latest_review ?? null;
  const needsChanges = latestReview?.payload?.disposition === "needs-changes";
  const busy = actionMutation.isPending;

  // Supersede candidates: this collection's other items,
  // labelled by title + ruled status (never by id), with
  // a created-date suffix on shared titles.
  const supersedeCandidates = (feed?.entries ?? []).filter(
    (candidate) => candidate.id !== entry.id,
  );
  const candidateTitleCounts = new Map<string, number>();
  for (const candidate of supersedeCandidates) {
    candidateTitleCounts.set(candidate.title, (candidateTitleCounts.get(candidate.title) ?? 0) + 1);
  }
  const candidateLabel = (candidate: FullEntry): string => {
    const base = `${candidate.title} · ${ruledStatusLabel(candidate.status)}`;
    return (candidateTitleCounts.get(candidate.title) ?? 0) > 1
      ? `${base} · ${formatDate(candidate.created_at)}`
      : base;
  };
  const supersededByTitle = entry.superseded_by
    ? ((feed?.entries ?? []).find((candidate) => candidate.id === entry.superseded_by)?.title ??
      null)
    : null;

  const doDisposition = (disposition: Disposition) => {
    if (disposition === "approve") {
      setApproveComment(comment);
      setConfirmApprove(true);
      return;
    }
    if (disposition === "needs-changes" && comment.trim() === "") {
      setActionError("Needs changes requires a comment — say what must change.");
      return;
    }
    runAction({
      verb: "review",
      disposition,
      comment: comment.trim() ? comment.trim() : undefined,
    });
    setComment("");
  };

  const copyAnswers = () => {
    const payload = JSON.stringify(
      { id: entry.id, title: entry.title, state: stateValues(entry) },
      null,
      2,
    );
    if (typeof navigator === "undefined" || !navigator.clipboard) {
      setCopyNotice("Clipboard unavailable here — the answers JSON could not be copied.");
      return;
    }
    navigator.clipboard.writeText(payload).then(
      () =>
        setCopyNotice(
          "Answers JSON copied — it travels as text; the record is the transcription into the owning project's files.",
        ),
      () => setCopyNotice("Clipboard write failed — the answers JSON could not be copied."),
    );
  };

  const selectStyle: React.CSSProperties = {
    display: "block",
    width: "100%",
    minHeight: "38px",
    marginTop: "var(--wb-space-4)",
    background: "var(--wb-surface-2)",
    color: "var(--wb-content-primary)",
    border: "1px solid var(--wb-border-default)",
    borderRadius: "var(--wb-button-radius)",
    padding: "0 var(--wb-space-8)",
  };
  const inputStyle: React.CSSProperties = { ...selectStyle };

  return (
    <section data-anchor="artifacts/entry-sheet">
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
          ← All artifacts
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
          gridTemplateColumns: isPhone ? "minmax(0, 1fr)" : "7fr 5fr",
          gap: "var(--wb-space-24)",
          alignItems: "start",
        }}
      >
        <div style={isPhone ? { minWidth: 0 } : { position: "sticky", top: "var(--wb-space-16)" }}>
          <PreviewStage slug={slug} entry={entry} draftState={draftState} />

          <Card title="Disposition" anchor="artifacts/disposition">
            <p style={{ margin: "0 0 var(--wb-space-8)", color: "var(--wb-content-secondary)" }}>
              Review this item in {projectName}. Each disposition is recorded in the review log with
              its comment. Approving binds the recorded answers — the state snapshot — by hash.
            </p>
            <label style={{ display: "block", marginBottom: "var(--wb-space-8)" }}>
              <span style={labelStyle}>Comment</span>
              <textarea
                aria-label="Review comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={3}
                style={{
                  display: "block",
                  width: "100%",
                  marginTop: "var(--wb-space-4)",
                  background: "var(--wb-surface-sunken)",
                  color: "var(--wb-content-primary)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-radius-md)",
                  padding: "var(--wb-space-8)",
                  fontSize: "var(--wb-font-size-sm)",
                }}
              />
            </label>
            <div style={{ display: "flex", gap: "var(--wb-space-8)", flexWrap: "wrap" }}>
              <Button disabled={busy} onClick={() => doDisposition("approve")}>
                Approve
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => doDisposition("needs-changes")}
              >
                Needs changes
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => doDisposition("stale")}>
                Mark stale
              </Button>
            </div>
            <p style={{ color: "var(--wb-content-muted)", marginBottom: 0 }}>
              Approve opens a confirm sheet with the answer set it will cover. Needs changes
              requires a comment.
            </p>
          </Card>
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
                anchor="artifacts/state-card"
                schema={entry.state_schema}
                values={draftState}
                onChange={(key, value) =>
                  setDraftState((prev) => ({ ...(prev ?? {}), [key]: value }))
                }
                title="Questions"
              />
              {draftDirty ? (
                <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
                  Unsaved answers — the approval coverage below still describes the recorded
                  answers.
                </p>
              ) : null}
              <div
                style={{
                  marginTop: "var(--wb-space-8)",
                  display: "flex",
                  gap: "var(--wb-space-8)",
                  flexWrap: "wrap",
                }}
              >
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
                <Button variant="secondary" disabled={busy} onClick={copyAnswers}>
                  Copy answers JSON
                </Button>
              </div>
              {copyNotice ? (
                <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
                  {copyNotice}
                </p>
              ) : null}
            </div>
          ) : (
            <Card title="Questions" anchor="artifacts/state-card">
              <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
                No questions declared — this item carries no state schema.
              </p>
            </Card>
          )}

          <Card title="Approval" anchor="artifacts/approval-card">
            {approval?.approved ? (
              <>
                <p style={{ margin: "0 0 var(--wb-space-8)" }}>
                  {approval.covers_current ? (
                    <>This approval covers the current answer set.</>
                  ) : (
                    <>
                      This approval does not cover the current answer set — re-approve to cover it.
                    </>
                  )}
                </p>
                <MetaRow label="Approved at">
                  {approval.approved_at ? formatDateTime(approval.approved_at) : "—"}
                </MetaRow>
                <MetaRow label="Approved by">{latestReview?.actor ?? "—"}</MetaRow>
                <MetaRow label="Covered state">
                  <span className="mono">{formatShortHash(approval.approved_state_sha256)}</span>
                </MetaRow>
                <MetaRow label="Current state">
                  <span className="mono">{formatShortHash(approval.current_state_sha256)}</span>
                </MetaRow>
                {latestReview?.payload?.state ? (
                  <ul style={{ listStyle: "none", margin: "var(--wb-space-8) 0 0", padding: 0 }}>
                    {Object.entries(latestReview.payload.state).map(([key, value]) => (
                      <li key={key}>
                        <span className="mono" style={{ color: "var(--wb-content-muted)" }}>
                          {key}
                        </span>{" "}
                        {String(value)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
                Not approved — no approval snapshot is recorded for this item.
              </p>
            )}
          </Card>

          <Card title="Lifecycle" anchor="artifacts/lifecycle-card">
            <label style={{ display: "block", marginBottom: "var(--wb-space-8)" }}>
              <span style={labelStyle}>Set status</span>
              <select
                aria-label="New status"
                value={statusChoice}
                onChange={(event) => setStatusChoice(event.target.value)}
                style={selectStyle}
              >
                {RULED_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {ruledStatusLabel(status)}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: "block", marginBottom: "var(--wb-space-8)" }}>
              <span style={labelStyle}>Ruling note (required for Canonical and Hard gate)</span>
              <input
                aria-label="Ruling note"
                type="text"
                value={ruling}
                onChange={(event) => setRuling(event.target.value)}
                style={inputStyle}
              />
            </label>
            {statusChoice === "hard-gate" ? (
              <label style={{ display: "block", marginBottom: "var(--wb-space-8)" }}>
                <span style={labelStyle}>Gate name</span>
                <input
                  aria-label="Gate name"
                  type="text"
                  value={gate}
                  onChange={(event) => setGate(event.target.value)}
                  style={inputStyle}
                />
              </label>
            ) : null}
            <div style={{ display: "flex", gap: "var(--wb-space-8)", flexWrap: "wrap" }}>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  runAction({
                    verb: "set-status",
                    status: statusChoice,
                    ruling: ruling.trim() ? ruling.trim() : undefined,
                    gate: statusChoice === "hard-gate" && gate.trim() ? gate.trim() : undefined,
                    expect_version: entry.version,
                  })
                }
              >
                Set status
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => runAction({ verb: "verify", accept_drift: acceptDrift })}
              >
                Verify
              </Button>
              {entry.archived ? (
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => runAction({ verb: "unarchive" })}
                >
                  Unarchive
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => runAction({ verb: "archive" })}
                >
                  Archive
                </Button>
              )}
            </div>
            {derived?.drift ? (
              <label
                style={{
                  display: "flex",
                  gap: "var(--wb-space-8)",
                  alignItems: "center",
                  marginTop: "var(--wb-space-8)",
                }}
              >
                <input
                  type="checkbox"
                  checked={acceptDrift}
                  onChange={(event) => setAcceptDrift(event.target.checked)}
                />
                <span>Accept drift on verify (the file changed since the last verify)</span>
              </label>
            ) : null}
            <div style={{ marginTop: "var(--wb-space-12)" }}>
              <span style={labelStyle}>Supersede with</span>
              {supersedeCandidates.length > 0 ? (
                <>
                  <select
                    aria-label="Superseding entry"
                    value={supersedeTarget}
                    onChange={(event) => setSupersedeTarget(event.target.value)}
                    style={selectStyle}
                  >
                    <option value="" disabled>
                      Choose the superseding entry…
                    </option>
                    {supersedeCandidates.map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidateLabel(candidate)}
                      </option>
                    ))}
                  </select>
                  <div
                    style={{
                      display: "flex",
                      gap: "var(--wb-space-8)",
                      flexWrap: "wrap",
                      marginTop: "var(--wb-space-8)",
                    }}
                  >
                    <Button
                      variant="danger"
                      disabled={busy || supersedeTarget.trim() === ""}
                      onClick={() =>
                        runAction({
                          verb: "supersede",
                          new_id: supersedeTarget.trim(),
                          ruling: ruling.trim() ? ruling.trim() : undefined,
                        })
                      }
                    >
                      Supersede
                    </Button>
                  </div>
                </>
              ) : (
                <p style={{ margin: "var(--wb-space-4) 0 0", color: "var(--wb-content-muted)" }}>
                  No other items in this collection to supersede with.
                </p>
              )}
            </div>
          </Card>

          {detail ? (
            <>
              <div data-anchor="artifacts/files-card">
                <FilePanel
                  slug={slug}
                  entryId={entryId}
                  files={detail.files}
                  configPath={entry.config_path ?? null}
                  onMutated={invalidate}
                />
              </div>
              <div data-anchor="artifacts/review-log-card">
                <ReviewLog history={detail.history} />
              </div>
              <div data-anchor="artifacts/history-card">
                <HistoryList history={detail.history} />
              </div>
            </>
          ) : null}
        </div>
      </div>

      <Sheet
        open={confirmApprove}
        title={`Approve ${entry.title}`}
        onClose={() => setConfirmApprove(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmApprove(false)}>
              Cancel
            </Button>
            <Button
              disabled={busy}
              onClick={() => {
                runAction({
                  verb: "review",
                  disposition: "approve",
                  comment: approveComment.trim() ? approveComment.trim() : undefined,
                });
                setComment("");
              }}
            >
              Approve this state
            </Button>
          </>
        }
      >
        <p style={{ color: "var(--wb-content-secondary)" }}>
          Approval binds to the answer set below — a later answer change will show as not covered
          until re-approval.
        </p>
        {draftDirty ? (
          <p role="alert" style={{ color: "var(--wb-danger)" }}>
            You have unsaved answers. Approving now covers the recorded answers, not the unsaved
            edits — save the state first if the approval should cover them.
          </p>
        ) : null}
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {Object.entries(stateValues(entry)).map(([key, value]) => (
            <li key={key}>
              <span className="mono" style={{ color: "var(--wb-content-muted)" }}>
                {key}
              </span>{" "}
              {String(value)}
            </li>
          ))}
          {Object.keys(stateValues(entry)).length === 0 ? (
            <li style={{ color: "var(--wb-content-secondary)" }}>No answers recorded.</li>
          ) : null}
        </ul>
        <p className="mono" style={{ color: "var(--wb-content-muted)", overflowWrap: "anywhere" }}>
          state {approval?.current_state_sha256 ?? "—"}
        </p>
        <label style={{ display: "block" }}>
          <span style={labelStyle}>Comment</span>
          <textarea
            aria-label="Approval comment"
            value={approveComment}
            onChange={(event) => setApproveComment(event.target.value)}
            rows={3}
            style={{
              display: "block",
              width: "100%",
              marginTop: "var(--wb-space-4)",
              background: "var(--wb-surface-sunken)",
              color: "var(--wb-content-primary)",
              border: "1px solid var(--wb-border-default)",
              borderRadius: "var(--wb-radius-md)",
              padding: "var(--wb-space-8)",
            }}
          />
        </label>
        {actionError ? (
          <p role="alert" style={{ color: "var(--wb-danger)" }}>
            {actionError}
          </p>
        ) : null}
      </Sheet>
    </section>
  );
}
