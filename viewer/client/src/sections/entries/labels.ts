// Component labels and the selection vocabulary of the
// mockup drill-in (§12): the pieces MockupDetail and its
// card leaves share.

import type { TextSelection } from "../../lib/api-types";

/** Display labels for the drill-in's components (§12):
 * the stored snapshot an annotation carries. An explicit
 * data-anchor-label on the element wins; the id-derived
 * form is the fallback. */
const COMPONENT_LABELS: Record<string, string> = {
  "mockups/exhibit-stage": "Exhibit stage",
  "mockups/metadata-card": "Metadata",
  "mockups/state-card": "State",
  "mockups/lifecycle-card": "Lifecycle",
  "mockups/files-card": "Files",
  "mockups/review-log-card": "Review log",
  "mockups/history-card": "History",
  "mockups/entry-sheet": "Entry sheet",
};

export function labelForComponent(el: HTMLElement, id: string): string {
  return (
    el.getAttribute("data-anchor-label") ??
    COMPONENT_LABELS[id] ??
    id.split("/").pop()?.replace(/-/g, " ") ??
    id
  );
}

export type Selected =
  | { kind: "component"; entryId: string; id: string; label: string }
  | { kind: "text"; entryId: string; selection: TextSelection };
