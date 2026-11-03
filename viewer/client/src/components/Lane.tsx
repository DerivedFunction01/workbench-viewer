// Lane — one board column: surface-1 body, uppercase section
// head + count chip, sunken inner well for cards. Scroll
// styling is the themes CSS's alone, never a component's.
// Contract: docs/component-contracts.md#lane.
import type { ReactNode } from "react";

export type LaneProps = {
  title: string;
  count: number;
  /** Review lane: 2px accent left edge. */
  accent?: boolean;
  /** Soft warning tone on the count (Doing > 7, display only). */
  countWarning?: boolean;
  /** Anchor id (`<section-or-exhibit>/<component>`, §14) — renders `data-anchor` on the root. */
  anchor?: string;
  className?: string;
  children?: ReactNode;
};

export function Lane({
  title,
  count,
  accent = false,
  countWarning = false,
  anchor,
  className,
  children,
}: LaneProps) {
  return (
    <section
      data-anchor={anchor}
      aria-label={title}
      className={className}
      style={{
        backgroundColor: "var(--wb-lane-bg)",
        borderColor: "var(--wb-border-default)",
        borderStyle: "solid",
        borderWidth: 1,
        borderLeftColor: accent ? "var(--wb-accent)" : "var(--wb-border-default)",
        borderLeftWidth: accent ? 2 : 1,
        borderRadius: "var(--wb-lane-radius)",
        color: "var(--wb-content-primary)",
      }}
    >
      <header className="flex items-center gap-2 px-4 pt-3 pb-2">
        <h3
          className="text-xs font-semibold tracking-[0.06em] uppercase"
          style={{ color: "var(--wb-content-secondary)" }}
        >
          {title}
        </h3>
        <span
          className="num inline-flex h-5 items-center px-2 text-xs font-medium"
          style={
            countWarning
              ? {
                  backgroundColor: "color-mix(in srgb, var(--wb-status-stale) 14%, transparent)",
                  color: "var(--wb-status-stale-text)",
                  borderRadius: "var(--wb-chip-radius)",
                }
              : {
                  backgroundColor: "var(--wb-surface-sunken)",
                  color: "var(--wb-content-secondary)",
                  borderRadius: "var(--wb-chip-radius)",
                }
          }
        >
          {count}
        </span>
      </header>
      <div
        className="mx-2 mb-2 flex flex-col gap-2 p-2"
        style={{ backgroundColor: "var(--wb-lane-well)", borderRadius: "var(--wb-radius-md)" }}
      >
        {children}
      </div>
    </section>
  );
}
