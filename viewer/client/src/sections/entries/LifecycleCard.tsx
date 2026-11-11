// The Lifecycle card: the status ruling, verify,
// archive, and supersede actions for one entry.

import type { Dispatch, SetStateAction } from "react";
import { ArmConfirm } from "../../components/ArmConfirm";
import { Card } from "../../components/Card";
import { Field, Input, Select } from "../../components/Fields";
import { Toggle } from "../../components/Toggle";
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
      <Field label="Set status" style={{ marginBottom: "var(--wb-space-8)" }}>
        {(id) => (
          <Select
            id={id}
            value={statusChoice}
            onChange={(event) => setStatusChoice(event.target.value)}
            style={{ display: "block", width: "100%" }}
            options={RULED_STATUSES.map((status) => ({
              value: status,
              label: ruledStatusLabel(status),
            }))}
          />
        )}
      </Field>
      <Field
        label="Ruling note (required for Canonical and Hard gate)"
        style={{ marginBottom: "var(--wb-space-8)" }}
      >
        {(id) => (
          <Input
            id={id}
            type="text"
            value={ruling}
            onChange={(event) => setRuling(event.target.value)}
            style={{ display: "block", width: "100%" }}
          />
        )}
      </Field>
      {statusChoice === "hard-gate" ? (
        <Field label="Gate name" style={{ marginBottom: "var(--wb-space-8)" }}>
          {(id) => (
            <Input
              id={id}
              type="text"
              value={gate}
              onChange={(event) => setGate(event.target.value)}
              style={{ display: "block", width: "100%" }}
            />
          )}
        </Field>
      ) : null}
      <div style={{ display: "flex", gap: "var(--wb-space-8)", flexWrap: "wrap" }}>
        <ArmConfirm
          label="Set status"
          confirmLabel="Confirm status change"
          statement={`Sets the status of “${entry.title}” to ${ruledStatusLabel(statusChoice)}. The ruling is recorded in the entry's history.`}
          busy={busy}
          disarmKey={`${statusChoice}|${ruling}|${gate}|${entry.version}`}
          onConfirm={() =>
            runAction({
              verb: "set-status",
              status: statusChoice,
              ruling: ruling.trim() ? ruling.trim() : undefined,
              gate: statusChoice === "hard-gate" && gate.trim() ? gate.trim() : undefined,
              expect_version: entry.version,
            })
          }
        />
        <ArmConfirm
          label="Verify"
          confirmLabel="Confirm verify"
          statement={`Records “${entry.title}” as verified at its current content${
            acceptDrift ? ", accepting the drift since the last verify" : ""
          }.`}
          busy={busy}
          disarmKey={`${acceptDrift}|${entry.version}`}
          onConfirm={() => runAction({ verb: "verify", accept_drift: acceptDrift })}
        />
        {entry.archived ? (
          <ArmConfirm
            label="Unarchive"
            confirmLabel="Confirm unarchive"
            statement={`Returns “${entry.title}” to the active entries.`}
            busy={busy}
            disarmKey={`unarchive|${entry.version}`}
            onConfirm={() => runAction({ verb: "unarchive" })}
          />
        ) : (
          <ArmConfirm
            label="Archive"
            confirmLabel="Confirm archive"
            statement={`Archives “${entry.title}”. It leaves the active lists and stays readable in the archive.`}
            busy={busy}
            disarmKey={`archive|${entry.version}`}
            onConfirm={() => runAction({ verb: "archive" })}
          />
        )}
      </div>
      {derived?.drift ? (
        <div style={{ marginTop: "var(--wb-space-8)" }}>
          <Toggle
            checked={acceptDrift}
            onChange={setAcceptDrift}
            label="Accept drift on verify (the file changed since the last verify)"
          />
        </div>
      ) : null}
      <div style={{ marginTop: "var(--wb-space-12)" }}>
        <span style={labelStyle}>Supersede with</span>
        {supersedeCandidates.length > 0 ? (
          <>
            <Select
              ariaLabel="Superseding entry"
              value={supersedeTarget}
              onChange={(event) => setSupersedeTarget(event.target.value)}
              style={{ display: "block", width: "100%", marginTop: "var(--wb-space-4)" }}
              options={[
                { value: "", label: "Choose the superseding entry…", disabled: true },
                ...supersedeCandidates.map((candidate) => ({
                  value: candidate.id,
                  label: candidateLabel(candidate),
                })),
              ]}
            />
            <div
              style={{
                display: "flex",
                gap: "var(--wb-space-8)",
                flexWrap: "wrap",
                marginTop: "var(--wb-space-8)",
              }}
            >
              <ArmConfirm
                label="Supersede"
                confirmLabel="Confirm supersede"
                variant="danger"
                statement={`Marks “${entry.title}” as superseded by “${
                  supersedeCandidates.find((c) => c.id === supersedeTarget.trim())?.title ??
                  supersedeTarget.trim()
                }”. The entry keeps its record; its status becomes Superseded.`}
                disabled={supersedeTarget.trim() === ""}
                disabledReason="Choose the superseding entry first."
                busy={busy}
                disarmKey={`${supersedeTarget}|${ruling}|${entry.version}`}
                onConfirm={() =>
                  runAction({
                    verb: "supersede",
                    new_id: supersedeTarget.trim(),
                    ruling: ruling.trim() ? ruling.trim() : undefined,
                  })
                }
              />
            </div>
          </>
        ) : (
          <p style={{ margin: "var(--wb-space-4) 0 0", color: "var(--wb-content-secondary)" }}>
            No other entries in this project to supersede with.
          </p>
        )}
      </div>
    </Card>
  );
}
