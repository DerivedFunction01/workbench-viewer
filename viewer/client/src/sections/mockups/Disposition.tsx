// The disposition cluster (split from MockupDetail.tsx,
// 2026-11-05 follow-up): the approval/disposition form
// state, the entry-action mutation every write rides
// (a refusal is surfaced with the server's own reason),
// and the two UI regions the cluster drives — the
// Disposition card and the approve confirm sheet. The
// lifecycle form state lives here too: the Lifecycle
// card renders it, this hook owns it.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Sheet } from "../../components/Sheet";
import { api } from "../../lib/api";
import { stateValues } from "./helpers";
import type { Disposition } from "./labels";
import { labelStyle } from "./meta";
import type { ApprovalCoverage, Envelope, FullEntry } from "./types";

export function useDisposition({
  slug,
  entryId,
  entry,
  onMutated,
}: {
  slug: string;
  entryId: string;
  entry: FullEntry | null;
  onMutated: () => void;
}) {
  const queryClient = useQueryClient();
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
    if (entry) {
      setStatusChoice(entry.status);
    }
  }, [entry]);

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
  const busy = actionMutation.isPending;

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

  return {
    comment,
    setComment,
    actionError,
    actionNotice,
    confirmApprove,
    setConfirmApprove,
    approveComment,
    setApproveComment,
    statusChoice,
    setStatusChoice,
    ruling,
    setRuling,
    gate,
    setGate,
    acceptDrift,
    setAcceptDrift,
    supersedeTarget,
    setSupersedeTarget,
    runAction,
    busy,
    doDisposition,
    invalidate,
  };
}

export type DispositionState = ReturnType<typeof useDisposition>;

export function DispositionCard({
  projectName,
  disposition,
}: {
  projectName: string;
  disposition: DispositionState;
}) {
  const { comment, setComment, doDisposition, busy } = disposition;
  return (
    <Card title="Disposition" anchor="mockups/disposition">
      <p style={{ margin: "0 0 var(--wb-space-8)", color: "var(--wb-content-secondary)" }}>
        Review this entry in {projectName}. Each disposition is recorded in the review log with its
        comment.
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
        <Button variant="secondary" disabled={busy} onClick={() => doDisposition("needs-changes")}>
          Needs changes
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => doDisposition("stale")}>
          Mark stale
        </Button>
      </div>
      <p style={{ color: "var(--wb-content-muted)", marginBottom: 0 }}>
        Approve opens a confirm sheet with the state snapshot it will cover. Needs changes requires
        a comment.
      </p>
    </Card>
  );
}

export function ApproveSheet({
  entry,
  approval,
  disposition,
}: {
  entry: FullEntry;
  approval: ApprovalCoverage | null;
  disposition: DispositionState;
}) {
  const {
    confirmApprove,
    setConfirmApprove,
    approveComment,
    setApproveComment,
    setComment,
    runAction,
    busy,
    actionError,
  } = disposition;
  return (
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
  );
}
