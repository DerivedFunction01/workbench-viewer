// TriageRow — one entry in the triage queue; the whole row
// opens the entry. Chip + Badges arrive as slots so the
// ruled/derived split stays visible. Chips inside the row
// are the inert form; badges are always inert.
// Contract: context/component-contracts.md#triagerow.
import { type CSSProperties, type ReactNode, useState } from "react";

export type TriageRowProps = {
  title: string;
  meta?: string;
  /** The entry's Chip. */
  leading?: ReactNode;
  /** Badge(s): stale / needs-changes / not-covered. */
  badges?: ReactNode;
  onOpen: () => void;
  className?: string;
};

export function TriageRow({ title, meta, leading, badges, onOpen, className }: TriageRowProps) {
  const [hover, setHover] = useState(false);
  const [active, setActive] = useState(false);
  const style: CSSProperties = {
    backgroundColor: active
      ? "var(--wb-surface-sunken)"
      : hover
        ? "var(--wb-surface-1)"
        : "var(--wb-surface-2)",
    borderColor: hover || active ? "var(--wb-border-strong)" : "var(--wb-border-default)",
    borderStyle: "solid",
    borderWidth: 1,
    borderRadius: "var(--wb-radius-md)",
    color: "var(--wb-content-primary)",
    minHeight: "calc(var(--wb-row-height) + var(--wb-space-8))",
    padding: "var(--wb-space-12) var(--wb-space-16)",
    textAlign: "left",
    width: "100%",
  };
  return (
    <button
      type="button"
      onClick={onOpen}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => {
        setHover(false);
        setActive(false);
      }}
      onMouseDown={() => setActive(true)}
      onMouseUp={() => setActive(false)}
      className={[
        "flex cursor-pointer items-center gap-3 focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring)",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={style}
    >
      {leading}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{title}</span>
        {meta ? (
          // The meta line is the entry's triage reason — why
          // it needs a ruling. That is essential content, so
          // it wears the secondary voice (the meta-only
          // muted voice never carries it, F1). Title and
          // reason wrap inside the row's own column: at
          // desktop widths eliding the reason into the
          // title made the two run together (F10); the row
          // grows instead of hiding the reason.
          <span
            className="block text-xs"
            style={{ color: "var(--wb-content-secondary)", overflowWrap: "anywhere" }}
          >
            {meta}
          </span>
        ) : null}
      </span>
      {badges ? <span className="flex shrink-0 items-center gap-2">{badges}</span> : null}
      <span aria-hidden="true" style={{ color: "var(--wb-content-secondary)" }}>
        ›
      </span>
    </button>
  );
}
