// The drill-in's metadata pieces: the shared label
// style and row, and the Metadata card itself.

import { Card } from "../../components/Card";
import { formatDate, formatDateTime, formatShortHash } from "../../lib/format";
import { kindLabel, ruledStatusLabel } from "../../lib/labels";
import type { DerivedStaleness, FullEntry } from "./types";

export const labelStyle: React.CSSProperties = {
  color: "var(--wb-content-muted)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

export function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
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

export function MetaCard({
  entry,
  derived,
  supersededByTitle,
}: {
  entry: FullEntry;
  derived: DerivedStaleness | null;
  supersededByTitle: string | null;
}) {
  return (
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
      <MetaRow label="Superseded by">
        {entry.superseded_by ? (supersededByTitle ?? entry.superseded_by) : "—"}
      </MetaRow>
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
  );
}
