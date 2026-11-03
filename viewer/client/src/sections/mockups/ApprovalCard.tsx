// The Approval card: the frozen snapshot an approval
// covered, read against the current state.

import { Card } from "../../components/Card";
import { formatDateTime, formatShortHash } from "../../lib/format";
import { MetaRow } from "./meta";
import type { ApprovalCoverage, LatestReview } from "./types";

export function ApprovalCard({
  approval,
  latestReview,
}: {
  approval: ApprovalCoverage | null;
  latestReview: LatestReview | null;
}) {
  return (
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
  );
}
