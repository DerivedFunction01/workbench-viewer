// Chip — the ONE rendering of a ruled status (SPEC §5.1).
// Filled pill: 8px dot + glyph + one word, always all three.
// Pressable form (filter chips) renders a <button aria-pressed>.
// Contract: docs/component-contracts.md#chip.
import { type CSSProperties, type ReactNode, useState } from "react";

export type RuledStatus =
  | "canonical"
  | "implemented"
  | "deferred"
  | "unexplored"
  | "hard-gate"
  | "abandoned";

export type ChipProps = {
  status: RuledStatus;
  /** hard-gate only: the gate name, appended after the word. */
  gate?: string;
  /** Filter-chip form; meaningful only with onPress. */
  pressed?: boolean;
  /** Present ⇒ interactive filter chip. */
  onPress?: () => void;
  className?: string;
};

const GLYPHS: Record<RuledStatus, string> = {
  canonical: "◆",
  implemented: "✓",
  deferred: "❚❚",
  unexplored: "?",
  "hard-gate": "⬢",
  abandoned: "✕",
};

const WORDS: Record<RuledStatus, string> = {
  canonical: "Canonical",
  implemented: "Implemented",
  deferred: "Deferred",
  unexplored: "Unexplored",
  "hard-gate": "Hard gate",
  abandoned: "Abandoned",
};

const BASE_CLASSES =
  "inline-flex h-6 max-w-full items-center gap-1.5 px-2.5 text-xs font-medium whitespace-nowrap";

function chipInner(status: RuledStatus, label: string): ReactNode {
  return (
    <>
      <span
        aria-hidden="true"
        className="inline-block h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: `var(--wb-status-${status})` }}
      />
      <span aria-hidden="true" className="shrink-0 text-xs leading-none">
        {GLYPHS[status]}
      </span>
      <span className="truncate">{label}</span>
    </>
  );
}

export function Chip({ status, gate, pressed = false, onPress, className }: ChipProps) {
  const [hover, setHover] = useState(false);
  const label = gate && status === "hard-gate" ? `${WORDS[status]} · ${gate}` : WORDS[status];
  const hue = `var(--wb-status-${status})`;
  const outlined = Boolean(onPress) || status === "abandoned";
  const style: CSSProperties = {
    backgroundColor: `color-mix(in srgb, ${hue} ${pressed ? 22 : 14}%, transparent)`,
    color: `var(--wb-status-${status}-text)`,
    borderColor: !onPress || pressed || hover ? hue : "transparent",
    borderStyle: status === "abandoned" ? "dashed" : "solid",
    borderWidth: outlined ? 1 : 0,
    borderRadius: "var(--wb-chip-radius)",
  };
  const classes = [BASE_CLASSES, className ?? ""].filter(Boolean).join(" ");

  if (onPress) {
    return (
      <button
        type="button"
        aria-pressed={pressed}
        onClick={onPress}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className={`${classes} cursor-pointer focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring)`}
        style={style}
      >
        {chipInner(status, label)}
      </button>
    );
  }
  return (
    <span className={classes} style={style}>
      {chipInner(status, label)}
    </span>
  );
}
