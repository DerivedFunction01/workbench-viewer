// Drill-in for one entry (Subplan 06 Step 2 + 3): preview
// well with per-frame mode toggle, metadata, schema-driven
// State panel, Approval panel (the frozen snapshot an
// approval covered), the disposition bar, lifecycle actions,
// files, review log and history. Every write goes through
// the server's entry action (lib/ mutation, actor=viewer);
// a refusal — ruling required, uniformity findings, version
// conflict — is surfaced with the server's own reason,
// never as a silent failure or a spinner.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Frame } from "../../components/Frame";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Sheet } from "../../components/Sheet";
import { StateControls, type StateValues } from "../../components/StateControls";
import { api, type TextSelection } from "../../lib/api";
import { formatDate, formatDateTime, formatShortHash } from "../../lib/format";
import { kindLabel, ruledStatusLabel } from "../../lib/labels";
import { useIsPhone } from "../../lib/responsive";
import {
  AnnotationComposer,
  AnnotationList,
  AnnotationThreadCard,
  clearAnnotationMarks,
  highlightSelectionInElement,
  SelectionTintStyle,
  useAnnotationThreads,
} from "../Annotations";
import { normalizeText } from "../plans/relocation";
import { FilePanel } from "./FilePanel";
import { HistoryList, ReviewLog } from "./HistoryLog";
import { EntryBadges, hasState, PreviewSummary, stateValues } from "./helpers";
import type { EntryDetail, Envelope, FullEntry } from "./types";
import { RULED_STATUSES } from "./types";

type Disposition = "approve" | "needs-changes" | "stale";

/** Display labels for the drill-in's components (§12):
 * the stored snapshot an annotation carries. An explicit
 * data-anchor-label on the element wins; the id-derived
 * form is the fallback. */
const COMPONENT_LABELS: Record<string, string> = {
  "mockups/exhibit-stage": "Exhibit stage",
  "mockups/disposition": "Disposition",
  "mockups/metadata-card": "Metadata",
  "mockups/state-card": "State",
  "mockups/approval-card": "Approval",
  "mockups/lifecycle-card": "Lifecycle",
  "mockups/files-card": "Files",
  "mockups/review-log-card": "Review log",
  "mockups/history-card": "History",
  "mockups/entry-sheet": "Entry sheet",
};

function labelForComponent(el: HTMLElement, id: string): string {
  return (
    el.getAttribute("data-anchor-label") ??
    COMPONENT_LABELS[id] ??
    id.split("/").pop()?.replace(/-/g, " ") ??
    id
  );
}

type Selected =
  | { kind: "component"; entryId: string; id: string; label: string }
  | { kind: "text"; entryId: string; selection: TextSelection };

const labelStyle: React.CSSProperties = {
  color: "var(--wb-content-muted)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "128px 1fr",
        gap: "var(--wb-space-12)",
        padding: "var(--wb-space-4) 0",
        borderBottom: "1px solid var(--wb-border-default)",
        fontSize: "var(--wb-font-size-sm)",
      }}
    >
      <span style={labelStyle}>{label}</span>
      <span style={{ overflowWrap: "anywhere" }}>{children}</span>
    </div>
  );
}

function toStateValues(source: FullEntry | null): StateValues {
  const values: StateValues = {};
  if (!source) return values;
  for (const [key, value] of Object.entries(stateValues(source))) {
    if (typeof value === "boolean" || typeof value === "string" || typeof value === "number") {
      values[key] = value;
    }
  }
  return values;
}

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
  const queryClient = useQueryClient();
  const isPhone = useIsPhone();
  const [frameMode, setFrameMode] = useState<"light" | "dark">("light");
  const [palette, setPalette] = useState("olive");
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

  useEffect(() => {
    setPalette(document.documentElement.getAttribute("data-palette") ?? "olive");
  }, []);

  const detailQuery = useQuery({
    queryKey: ["entry", slug, entryId],
    queryFn: () => api.getEntry({ slug, entryId }),
  });
  const detailEnvelope = detailQuery.data as Envelope | undefined;
  const detail =
    detailEnvelope && detailEnvelope.status === 200
      ? (detailEnvelope.payload as EntryDetail)
      : null;
  const detailError =
    detailEnvelope && detailEnvelope.status !== 200
      ? (detailEnvelope.error ?? "the entry detail could not be loaded.")
      : null;

  // The feed row is a complete fallback for everything except
  // history/files: if the detail action refuses, the drill-in
  // still renders the entry's recorded truth from the feed.
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

  // Annotation state (§12): the exhibit's threads, the
  // selected component / armed text selection (one
  // composer at a time), and each thread's derived
  // presence/re-location status. Viewing never
  // acknowledges anything — pickup is an agent act.
  const detailRef = useRef<HTMLElement | null>(null);
  const { threads, count } = useAnnotationThreads(slug, entryId);
  const [selectedState, setSelected] = useState<Selected | null>(null);
  // A selection belongs to the entry it was made on; it
  // never renders (or posts) against another entry.
  const selected = selectedState?.entryId === entryId ? selectedState : null;
  const [statusById, setStatusById] = useState<Record<number, "located" | "moved">>({});
  useEffect(() => {
    const rootEl = detailRef.current;
    if (!rootEl || !entry) return;
    clearAnnotationMarks(rootEl);
    const next: Record<number, "located" | "moved"> = {};
    for (const t of threads) {
      const sel = t.root.selection;
      if (!sel) {
        next[t.root.id] = "located";
        continue;
      }
      const el = rootEl.querySelector(`[data-anchor="${sel.component_id}"]`);
      if (!el) {
        next[t.root.id] = "moved";
        continue;
      }
      next[t.root.id] =
        sel.kind === "component" ||
        highlightSelectionInElement(el as HTMLElement, sel) === "located"
          ? "located"
          : "moved";
    }
    setStatusById(next);
  }, [threads, entry]);
  useEffect(() => {
    const rootEl = detailRef.current;
    if (!rootEl || !entry) return;
    const clearSelected = () => {
      const prev = rootEl.querySelector<HTMLElement>("[data-wb-selected-component]");
      if (!prev) return;
      prev.style.outline = "";
      prev.style.outlineOffset = "";
      prev.style.position = "";
      delete prev.dataset.wbSelectedComponent;
      prev.querySelector(":scope > [data-wb-anchor-tag]")?.remove();
    };
    clearSelected();
    if (selected?.kind !== "component") return;
    const el = rootEl.querySelector<HTMLElement>(`[data-anchor="${selected.id}"]`);
    if (!el) return;
    el.dataset.wbSelectedComponent = "";
    el.style.outline = "2.5px solid var(--wb-accent)";
    el.style.outlineOffset = "3px";
    if (window.getComputedStyle(el).position === "static") el.style.position = "relative";
    const tag = document.createElement("span");
    tag.dataset.wbAnchorTag = "";
    tag.setAttribute("data-annotation-ui", "true");
    tag.textContent = selected.label;
    Object.assign(tag.style, {
      position: "absolute",
      top: "-10px",
      right: "10px",
      background: "var(--wb-accent)",
      color: "var(--wb-on-accent)",
      fontFamily: "var(--wb-font-mono)",
      fontSize: "var(--wb-font-size-xs)",
      padding: "1px 7px",
      borderRadius: "999px",
      zIndex: "5",
      pointerEvents: "none",
    });
    el.appendChild(tag);
    return clearSelected;
  }, [selected, entry]);

  const savedStateJson = useMemo(
    () => JSON.stringify(stateValues(entry ?? ({} as FullEntry))),
    [entry],
  );
  const draftDirty =
    draftState != null && entry != null && JSON.stringify(draftState) !== savedStateJson;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["entry", slug, entryId] });
    queryClient.invalidateQueries({ queryKey: ["mockups", slug] });
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
        // The refusal IS the result: surface the server's reason.
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

  const latestReview = detail?.latest_review ?? null;
  const needsChanges = latestReview?.payload?.disposition === "needs-changes";
  const busy = actionMutation.isPending;

  // Component selection (§12): a plain click inside the
  // drill-in selects the nearest component — accent
  // outline + anchor-tag pill (the effect above renders
  // them) — and pins the composer beneath the stage.
  // Clicks on controls and inside the annotation UI are
  // not selection; a live text selection owns its gesture
  // (the mouseup handler arms the text composer instead).
  function onDetailClick(e: React.MouseEvent) {
    const rootEl = detailRef.current;
    if (!rootEl) return;
    const target = e.target as Element;
    if (target.closest("[data-annotation-ui]")) return;
    if (target.closest("button, a, input, select, textarea, label")) return;
    const winSel = window.getSelection();
    if (winSel && !winSel.isCollapsed) return;
    const el = target.closest<HTMLElement>("[data-anchor]");
    if (!el || !rootEl.contains(el)) return;
    const id = el.dataset.anchor as string;
    setSelected({ kind: "component", entryId, id, label: labelForComponent(el, id) });
  }

  // Text selection inside a component arms a text
  // annotation scoped by that component (the §12 rules,
  // identical to the Plans reader's): one component only,
  // quote/prefix/suffix from the rendered text, oversize
  // refused quietly.
  function onDetailMouseUp() {
    const rootEl = detailRef.current;
    const winSel = window.getSelection();
    if (!rootEl || !winSel || winSel.isCollapsed || winSel.rangeCount === 0) return;
    const range = winSel.getRangeAt(0);
    const cac = range.commonAncestorContainer;
    const cacEl = cac.nodeType === Node.ELEMENT_NODE ? (cac as Element) : cac.parentElement;
    if (!cacEl || cacEl.closest("[data-annotation-ui]") || !rootEl.contains(cac)) return;
    const elementOf = (node: Node): Element | null =>
      node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
    const startEl = elementOf(range.startContainer)?.closest<HTMLElement>("[data-anchor]");
    const endEl = elementOf(range.endContainer)?.closest<HTMLElement>("[data-anchor]");
    if (!startEl || startEl !== endEl || !rootEl.contains(startEl)) return;
    const componentId = startEl.dataset.anchor as string;
    const text = startEl.textContent ?? "";
    const pre = document.createRange();
    pre.selectNodeContents(startEl);
    pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    const quote = range.toString();
    if (!quote || normalizeText(quote) === "" || quote.length > 500) return;
    if (text.slice(start, start + quote.length) !== quote) return;
    setSelected({
      kind: "text",
      entryId,
      selection: {
        kind: "text",
        component_id: componentId,
        component_label: labelForComponent(startEl, componentId),
        quote,
        prefix: text.slice(Math.max(0, start - 120), start),
        suffix: text.slice(start + quote.length, start + quote.length + 120),
      },
    });
  }

  const annotationComposer = selected ? (
    selected.kind === "component" ? (
      <AnnotationComposer
        key={`component:${selected.id}`}
        slug={slug}
        anchorType="component"
        anchorRef={entryId}
        selection={{
          kind: "component",
          component_id: selected.id,
          component_label: selected.label,
          entry_id: entryId,
        }}
        onClose={() => setSelected(null)}
        onSent={() => setSelected(null)}
      />
    ) : (
      <AnnotationComposer
        key={`text:${selected.selection.component_id}:${selected.selection.quote}`}
        slug={slug}
        anchorType="text"
        anchorRef={entryId}
        selection={selected.selection}
        quote={selected.selection.quote}
        onClose={() => setSelected(null)}
        onSent={() => setSelected(null)}
      />
    )
  ) : null;

  const pinnedThreads =
    selected?.kind === "component"
      ? threads.filter(
          (t) =>
            t.root.selection?.kind === "component" &&
            t.root.selection.component_id === selected.id &&
            statusById[t.root.id] !== "moved",
        )
      : [];

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

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions lint/a11y/useKeyWithClickEvents: the drill-in root only OBSERVES clicks/selection to select components and arm the annotation composer; it has no activation behavior of its own
    <section
      data-anchor="mockups/entry-sheet"
      data-annotation-scope="true"
      ref={detailRef}
      onClick={onDetailClick}
      onMouseUp={onDetailMouseUp}
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

          {annotationComposer}
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

          <Card title="Disposition" anchor="mockups/disposition">
            <p style={{ margin: "0 0 var(--wb-space-8)", color: "var(--wb-content-secondary)" }}>
              Review this entry in {projectName}. Each disposition is recorded in the review log
              with its comment.
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
              Approve opens a confirm sheet with the state snapshot it will cover. Needs changes
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
          <Card title="Metadata" anchor="mockups/metadata-card">
            <MetaRow label="Id">
              <span className="mono">{entry.id}</span>
            </MetaRow>
            <MetaRow label="Kind">{kindLabel(entry.kind)}</MetaRow>
            <MetaRow label="Status">
              {ruledStatusLabel(entry.status)}
              {entry.gate ? ` · gate: ${entry.gate}` : ""}
            </MetaRow>
            <MetaRow label="Source">
              {entry.source_kind}
              {entry.source_ref ? (
                <>
                  {" · "}
                  <span className="mono">{entry.source_ref}</span>
                </>
              ) : null}
            </MetaRow>
            <MetaRow label="Entry dir">
              <span className="mono">{entry.entry_dir ?? "—"}</span>
            </MetaRow>
            <MetaRow label="Main file">
              <span className="mono">{entry.main_file ?? "—"}</span>
            </MetaRow>
            <MetaRow label="Content sha">
              <span className="mono">{formatShortHash(entry.content_sha256)}</span>
            </MetaRow>
            <MetaRow label="Spec ref">{entry.spec_ref ?? "—"}</MetaRow>
            <MetaRow label="Plan ref">{entry.plan_ref ?? "—"}</MetaRow>
            <MetaRow label="Ruling">
              {entry.ruling_text ?? "—"}
              {entry.ruling_date ? ` (${entry.ruling_date})` : ""}
            </MetaRow>
            <MetaRow label="Superseded by">{entry.superseded_by ?? "—"}</MetaRow>
            <MetaRow label="Created">{formatDateTime(entry.created_at)}</MetaRow>
            <MetaRow label="Updated">
              {formatDate(entry.updated_at)} · status changed {formatDate(entry.status_changed_at)}
            </MetaRow>
            <MetaRow label="Last verified">
              {entry.last_verified_at ? formatDateTime(entry.last_verified_at) : "Never"}
            </MetaRow>
            <MetaRow label="Version">
              <span className="num">{entry.version}</span>
            </MetaRow>
            {derived ? (
              <MetaRow label="Staleness">
                {derived.stale
                  ? derived.reasons.join("; ")
                  : `Not stale · ${Math.floor(derived.days_since_verified)}d since verified · ${derived.age_days}d old`}
                {derived.drift ? " · content drifted" : ""}
              </MetaRow>
            ) : null}
          </Card>

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

          <Card title="Approval" anchor="mockups/approval-card">
            {approval?.approved ? (
              <>
                <p style={{ margin: "0 0 var(--wb-space-8)" }}>
                  {approval.covers_current ? (
                    <>This approval covers the current state.</>
                  ) : (
                    <>This approval does not cover the current state — re-approve to cover it.</>
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
                Not approved — no approval snapshot is recorded for this entry.
              </p>
            )}
          </Card>

          <Card title="Lifecycle" anchor="mockups/lifecycle-card">
            <label style={{ display: "block", marginBottom: "var(--wb-space-8)" }}>
              <span style={labelStyle}>Set status</span>
              <select
                aria-label="New status"
                value={statusChoice}
                onChange={(event) => setStatusChoice(event.target.value)}
                style={{
                  display: "block",
                  width: "100%",
                  minHeight: "38px",
                  marginTop: "var(--wb-space-4)",
                  background: "var(--wb-surface-2)",
                  color: "var(--wb-content-primary)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-button-radius)",
                  padding: "0 var(--wb-space-8)",
                }}
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
                style={{
                  display: "block",
                  width: "100%",
                  minHeight: "38px",
                  marginTop: "var(--wb-space-4)",
                  background: "var(--wb-surface-2)",
                  color: "var(--wb-content-primary)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-button-radius)",
                  padding: "0 var(--wb-space-8)",
                }}
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
                  style={{
                    display: "block",
                    width: "100%",
                    minHeight: "38px",
                    marginTop: "var(--wb-space-4)",
                    background: "var(--wb-surface-2)",
                    color: "var(--wb-content-primary)",
                    border: "1px solid var(--wb-border-default)",
                    borderRadius: "var(--wb-button-radius)",
                    padding: "0 var(--wb-space-8)",
                  }}
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
            <label style={{ display: "block", marginTop: "var(--wb-space-12)" }}>
              <span style={labelStyle}>Supersede with entry id</span>
              <span
                style={{
                  display: "flex",
                  gap: "var(--wb-space-8)",
                  marginTop: "var(--wb-space-4)",
                }}
              >
                <input
                  aria-label="Superseding entry id"
                  type="text"
                  value={supersedeTarget}
                  onChange={(event) => setSupersedeTarget(event.target.value)}
                  style={{
                    flex: 1,
                    minHeight: "38px",
                    background: "var(--wb-surface-2)",
                    color: "var(--wb-content-primary)",
                    border: "1px solid var(--wb-border-default)",
                    borderRadius: "var(--wb-button-radius)",
                    padding: "0 var(--wb-space-8)",
                  }}
                />
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
              </span>
            </label>
          </Card>

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
                  onMutated={invalidate}
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
          Approval binds to the state snapshot below — a later state change will show as not covered
          until re-approval.
        </p>
        {draftDirty ? (
          <p role="alert" style={{ color: "var(--wb-danger)" }}>
            You have unsaved state changes. Approving now covers the recorded state, not the unsaved
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
            <li style={{ color: "var(--wb-content-secondary)" }}>No internal state values.</li>
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
