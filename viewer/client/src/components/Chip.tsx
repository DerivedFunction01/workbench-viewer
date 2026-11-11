// Chip — the ONE rendering of a ruled status (SPEC §5.1).
// Filled pill: 8px dot + glyph + one word, always all three.
// Pressable form (filter chips) renders a <button aria-pressed>.
// Contract: context/component-contracts.md#chip.
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

// The pill itself stays 24px (the chip contract); the pressable
// form's TARGET is the full contract height: a transparent,
// borderless hit-area span inside the button stretches the
// button's box to 38px (44px coarse) while the pill — the
// button's first flex row — keeps its own 24px. The two boxes
// are separate elements, so the target grows without the pill
// growing (ui-context: interactive targets never shrink below
// 38px; the chip's own size is its contract size).
const BASE_CLASSES =
  "inline-flex h-6 max-w-full items-center gap-1.5 px-2.5 text-xs font-medium whitespace-nowrap";

const HIT_AREA_CLASSES =
  "pointer-events-none absolute inset-x-0 top-1/2 h-[38px] -translate-y-1/2 [@media(pointer:coarse)]:h-[44px]";

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
  const pillStyle: CSSProperties = {
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
        className="group relative inline-flex cursor-pointer items-center justify-center border-0 bg-transparent p-0 focus-visible:outline-none"
        style={{ minHeight: "38px" }}
      >
        <span aria-hidden="true" className={HIT_AREA_CLASSES} />
        <span
          className={`${classes} group-focus-visible:outline-2 group-focus-visible:outline-solid group-focus-visible:outline-offset-1 group-focus-visible:outline-(--wb-focus-ring)`}
          style={pillStyle}
        >
          {chipInner(status, label)}
        </span>
      </button>
    );
  }
  return (
    <span className={classes} style={pillStyle}>
      {chipInner(status, label)}
    </span>
  );
}
