// The Lifecycle card: the status ruling, verify,
// archive, and supersede actions for one entry.

import type { Dispatch, SetStateAction } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ruledStatusLabel } from "../../lib/labels";
import { labelStyle } from "./meta";
import type { DerivedStaleness, FullEntry } from "./types";
import { RULED_STATUSES } from "./types";

export function LifecycleCard({
  entry,
  derived,
  busy,
  runAction,
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
  supersedeCandidates,
  candidateLabel,
}: {
  entry: FullEntry;
  derived: DerivedStaleness | null;
  busy: boolean;
  runAction: (body: Record<string, unknown>) => void;
  statusChoice: string;
  setStatusChoice: Dispatch<SetStateAction<string>>;
  ruling: string;
  setRuling: Dispatch<SetStateAction<string>>;
  gate: string;
  setGate: Dispatch<SetStateAction<string>>;
  acceptDrift: boolean;
  setAcceptDrift: Dispatch<SetStateAction<boolean>>;
  supersedeTarget: string;
  setSupersedeTarget: Dispatch<SetStateAction<string>>;
  supersedeCandidates: FullEntry[];
  candidateLabel: (candidate: FullEntry) => string;
}) {
  return (
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
      <div style={{ marginTop: "var(--wb-space-12)" }}>
        <span style={labelStyle}>Supersede with</span>
        {supersedeCandidates.length > 0 ? (
          <>
            <select
              aria-label="Superseding entry"
              value={supersedeTarget}
              onChange={(event) => setSupersedeTarget(event.target.value)}
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
            No other entries in this project to supersede with.
          </p>
        )}
      </div>
    </Card>
  );
}
