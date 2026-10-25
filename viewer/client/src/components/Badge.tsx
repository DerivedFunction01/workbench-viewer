// Badge — derived / review states ONLY (never a ruled status).
// Outline pill: glyph + word + magnitude; `text` is required
// because a badge without its word is a defect. `approved`
// is the one filled badge (it aliases the implemented tones).
// Contract: docs/component-contracts.md#badge.
import type { CSSProperties } from "react";

export type BadgeKind = "stale" | "not-covered" | "needs-changes" | "approved" | "in-triage";

export type BadgeProps = {
  kind: BadgeKind;
  /** Word + magnitude, e.g. "Stale · 23d unverified". Required. */
  text: string;
  /** Approved only: the state hash, rendered mono after the text. */
  stateHash?: string;
  className?: string;
};

const GLYPHS: Record<BadgeKind, string> = {
  stale: "◷",
  "not-covered": "⚠",
  "needs-changes": "↩",
  approved: "✓",
  "in-triage": "▤",
};

function badgeStyle(kind: BadgeKind): CSSProperties {
  const hue = `var(--wb-status-${kind})`;
  if (kind === "approved") {
    return {
      backgroundColor: `color-mix(in srgb, ${hue} 14%, transparent)`,
      color: "var(--wb-status-approved-text)",
      borderWidth: 0,
      borderRadius: "var(--wb-chip-radius)",
    };
  }
  return {
    backgroundColor: "transparent",
    color: `var(--wb-status-${kind}-text)`,
    borderColor: hue,
    borderStyle: "solid",
    borderWidth: 1,
    borderRadius: "var(--wb-chip-radius)",
  };
}

export function Badge({ kind, text, stateHash, className }: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex h-6 max-w-full items-center gap-1.5 px-2.5 text-xs font-medium whitespace-nowrap",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={badgeStyle(kind)}
    >
      <span
        aria-hidden="true"
        className="shrink-0 text-xs leading-none"
        style={{ color: `var(--wb-status-${kind})` }}
      >
        {GLYPHS[kind]}
      </span>
      <span className="truncate">{text}</span>
      {kind === "approved" && stateHash ? (
        <span className="mono shrink-0">· state {stateHash}</span>
      ) : null}
    </span>
  );
}
