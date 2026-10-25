// AnnotationBadge — the message-lifecycle badge for
// annotations (repo-home spec §12): outline pill, glyph +
// word, in the palette-constant Okabe–Ito lifecycle hues
// (tokens --wb-status-sent / -acknowledged / -done). A
// message's lifecycle state is neither a registry ruling
// nor a chip, so it takes the derived-badge form (SPEC
// §11) — never the filled Chip. Draft and archived carry
// NO badge: the state word renders in muted text (the
// annotation mockup shows no badge for them; nothing is
// invented to fill the gap). Display only: state in,
// nothing out. Contract: docs/component-contracts.md#annotationbadge.
//
// The two annotation mark tints live here too (one kit
// home for the annotation marks): a LIVE selection wears
// the active palette's accent derivation; a SAVED
// annotation wears Okabe orange, palette-constant. Both
// are <mark> with radius 3, 1px 2px padding, and the
// inset bottom bar, per the mockup's mark.sel / mark.ann.
import type { CSSProperties } from "react";

export type AnnotationState = "draft" | "sent" | "acknowledged" | "done" | "archived";

const BADGED: Record<string, { glyph: string; word: string; token: string }> = {
  sent: { glyph: "→", word: "Sent", token: "sent" },
  acknowledged: { glyph: "◐", word: "Acknowledged", token: "acknowledged" },
  done: { glyph: "✓", word: "Done", token: "done" },
};

const WORDS: Record<string, string> = {
  draft: "Draft",
  archived: "Archived",
};

export const selectionMarkStyle: CSSProperties = {
  backgroundColor: "var(--wb-highlight-selection-fill)",
  boxShadow: "inset 0 -2px 0 var(--wb-highlight-selection-bar)",
  borderRadius: "3px",
  padding: "1px 2px",
};

export const annotationMarkStyle: CSSProperties = {
  backgroundColor: "var(--wb-highlight-annotation-fill)",
  boxShadow: "inset 0 -2px 0 var(--wb-highlight-annotation-bar)",
  borderRadius: "3px",
  padding: "1px 2px",
};

export function AnnotationBadge({ state }: { state: AnnotationState }) {
  const badged = BADGED[state];
  if (!badged) {
    return (
      <span
        className="inline-flex h-6 items-center text-xs whitespace-nowrap"
        style={{ color: "var(--wb-content-muted)" }}
      >
        {WORDS[state] ?? state}
      </span>
    );
  }
  const hue = `var(--wb-status-${badged.token})`;
  return (
    <span
      className="inline-flex h-6 max-w-full items-center gap-1.5 px-2.5 text-xs font-medium whitespace-nowrap"
      style={{
        backgroundColor: "transparent",
        color: `var(--wb-status-${badged.token}-text)`,
        borderColor: hue,
        borderStyle: "solid",
        borderWidth: 1,
        borderRadius: "var(--wb-chip-radius)",
      }}
    >
      <span aria-hidden="true" className="shrink-0 text-xs leading-none" style={{ color: hue }}>
        {badged.glyph}
      </span>
      <span className="truncate">{badged.word}</span>
    </span>
  );
}
