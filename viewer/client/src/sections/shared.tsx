// Shared section frame pieces. A section is a frame with a
// truthful state: loading skeleton, server error (named, with
// the recovery, once), degraded banner, not-set-up state, or
// content. Empty states are content, not errors (ui-context):
// a sunken well, one line. No fabricated data anywhere — a
// section with nothing to show says so in its own words.

import type { ReactNode } from "react";
import type { FeedEnvelope } from "../lib/api";

const wellStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-lg)",
  padding: "var(--wb-panel-padding)",
  color: "var(--wb-content-secondary)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
};

export function EmptyWell({ children }: { children: ReactNode }) {
  return <div style={wellStyle}>{children}</div>;
}

export function ErrorWell({ section, message }: { section: string; message: string }) {
  return (
    <div style={{ ...wellStyle, color: "var(--wb-danger)" }} role="alert">
      {section}: {message} Reload the section to try again.
    </div>
  );
}

export function SkeletonWell({ label }: { label: string }) {
  return (
    <div style={wellStyle} aria-busy="true">
      Loading {label}…
    </div>
  );
}

export function DegradedBanner({ feed }: { feed: FeedEnvelope }) {
  if (!feed.degraded && feed.available) return null;
  const text = feed.degraded
    ? `This project's data is degraded${feed.reason ? ` — ${feed.reason}` : ""}. What is shown is what could be read.`
    : `This section is not set up for this project${feed.reason ? ` — ${feed.reason}` : ""}.`;
  return (
    <div
      style={{
        background: "var(--wb-surface-1)",
        border: "1px solid var(--wb-border-strong)",
        borderRadius: "var(--wb-radius-md)",
        padding: "var(--wb-space-12) var(--wb-space-16)",
        color: "var(--wb-content-secondary)",
        fontSize: "var(--wb-font-size-sm)",
        lineHeight: "var(--wb-line-height-sm)",
        marginBottom: "var(--wb-space-16)",
      }}
      role="status"
    >
      {text}
    </div>
  );
}

export const sectionTitleStyle: React.CSSProperties = {
  fontSize: "var(--wb-font-size-xl)",
  lineHeight: "var(--wb-line-height-xl)",
  fontWeight: 600,
  letterSpacing: "-0.011em",
  margin: "0 0 var(--wb-space-16)",
};

export const listRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--wb-space-12)",
  minHeight: "var(--wb-row-height)",
  padding: "var(--wb-space-8) var(--wb-space-12)",
  borderBottom: "1px solid var(--wb-border-default)",
  color: "var(--wb-content-primary)",
  textDecoration: "none",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
};

export const metaStyle: React.CSSProperties = {
  color: "var(--wb-content-muted)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  whiteSpace: "nowrap",
};
