// Annotation state for the drill-in (split from
// MockupDetail.tsx, 2026-11-05 follow-up): the exhibit's
// threads, the selected component / armed text selection
// (one composer at a time), and each thread's derived
// presence/re-location status. Viewing never acknowledges
// anything — pickup is an agent act.

import { type RefObject, useEffect, useState } from "react";
import {
  AnnotationComposer,
  clearAnnotationMarks,
  highlightSelectionInElement,
  useAnnotationThreads,
} from "../Annotations";
import { normalizeText } from "../plans/relocation";
import { labelForComponent, type Selected } from "./labels";
import type { FullEntry } from "./types";

export function useEntryAnnotations(
  slug: string,
  entryId: string,
  entry: FullEntry | null,
  detailRef: RefObject<HTMLElement | null>,
) {
  const { threads, count } = useAnnotationThreads(slug, entryId);
  const [selectedState, setSelected] = useState<Selected | null>(null);
  // A selection belongs to the entry it was made on; it
  // never renders (or posts) against another entry.
  const selected = selectedState?.entryId === entryId ? selectedState : null;
  const [statusById, setStatusById] = useState<Record<number, "located" | "moved">>({});
  useEffect(() => {
    const rootEl = detailRef.current;
    if (!rootEl || !entry) return;
    clearAnnotationMarks(rootEl);
    const next: Record<number, "located" | "moved"> = {};
    for (const t of threads) {
      const sel = t.root.selection;
      if (!sel) {
        next[t.root.id] = "located";
        continue;
      }
      const el = rootEl.querySelector(`[data-anchor="${sel.component_id}"]`);
      if (!el) {
        next[t.root.id] = "moved";
        continue;
      }
      next[t.root.id] =
        sel.kind === "component" ||
        highlightSelectionInElement(el as HTMLElement, sel) === "located"
          ? "located"
          : "moved";
    }
    setStatusById(next);
  }, [threads, entry, detailRef]);
  useEffect(() => {
    const rootEl = detailRef.current;
    if (!rootEl || !entry) return;
    const clearSelected = () => {
      const prev = rootEl.querySelector<HTMLElement>("[data-wb-selected-component]");
      if (!prev) return;
      prev.style.outline = "";
      prev.style.outlineOffset = "";
      prev.style.position = "";
      delete prev.dataset.wbSelectedComponent;
      prev.querySelector(":scope > [data-wb-anchor-tag]")?.remove();
    };
    clearSelected();
    if (selected?.kind !== "component") return;
    const el = rootEl.querySelector<HTMLElement>(`[data-anchor="${selected.id}"]`);
    if (!el) return;
    el.dataset.wbSelectedComponent = "";
    el.style.outline = "2.5px solid var(--wb-accent)";
    el.style.outlineOffset = "3px";
    if (window.getComputedStyle(el).position === "static") el.style.position = "relative";
    const tag = document.createElement("span");
    tag.dataset.wbAnchorTag = "";
    tag.setAttribute("data-annotation-ui", "true");
    tag.textContent = selected.label;
    Object.assign(tag.style, {
      position: "absolute",
      top: "-10px",
      right: "10px",
      background: "var(--wb-accent)",
      color: "var(--wb-on-accent)",
      fontFamily: "var(--wb-font-mono)",
      fontSize: "var(--wb-font-size-xs)",
      padding: "1px 7px",
      borderRadius: "999px",
      zIndex: "5",
      pointerEvents: "none",
    });
    el.appendChild(tag);
    return clearSelected;
  }, [selected, entry, detailRef]);

  // Component selection (§12): a plain click inside the
  // drill-in selects the nearest component — accent
  // outline + anchor-tag pill (the effect above renders
  // them) — and pins the composer beneath the stage.
  // Clicks on controls and inside the annotation UI are
  // not selection; a live text selection owns its gesture
  // (the mouseup handler arms the text composer instead).
  function onDetailClick(e: React.MouseEvent) {
    const rootEl = detailRef.current;
    if (!rootEl) return;
    const target = e.target as Element;
    if (target.closest("[data-annotation-ui]")) return;
    if (target.closest("button, a, input, select, textarea, label")) return;
    const winSel = window.getSelection();
    if (winSel && !winSel.isCollapsed) return;
    const el = target.closest<HTMLElement>("[data-anchor]");
    if (!el || !rootEl.contains(el)) return;
    const id = el.dataset.anchor as string;
    setSelected({ kind: "component", entryId, id, label: labelForComponent(el, id) });
  }

  // Text selection inside a component arms a text
  // annotation scoped by that component (the §12 rules,
  // identical to the Plans reader's): one component only,
  // quote/prefix/suffix from the rendered text, oversize
  // refused quietly.
  function onDetailMouseUp() {
    const rootEl = detailRef.current;
    const winSel = window.getSelection();
    if (!rootEl || !winSel || winSel.isCollapsed || winSel.rangeCount === 0) return;
    const range = winSel.getRangeAt(0);
    const cac = range.commonAncestorContainer;
    const cacEl = cac.nodeType === Node.ELEMENT_NODE ? (cac as Element) : cac.parentElement;
    if (!cacEl || cacEl.closest("[data-annotation-ui]") || !rootEl.contains(cac)) return;
    const elementOf = (node: Node): Element | null =>
      node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
    const startEl = elementOf(range.startContainer)?.closest<HTMLElement>("[data-anchor]");
    const endEl = elementOf(range.endContainer)?.closest<HTMLElement>("[data-anchor]");
    if (!startEl || startEl !== endEl || !rootEl.contains(startEl)) return;
    const componentId = startEl.dataset.anchor as string;
    const text = startEl.textContent ?? "";
    const pre = document.createRange();
    pre.selectNodeContents(startEl);
    pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    const quote = range.toString();
    if (!quote || normalizeText(quote) === "" || quote.length > 500) return;
    if (text.slice(start, start + quote.length) !== quote) return;
    setSelected({
      kind: "text",
      entryId,
      selection: {
        kind: "text",
        component_id: componentId,
        component_label: labelForComponent(startEl, componentId),
        quote,
        prefix: text.slice(Math.max(0, start - 120), start),
        suffix: text.slice(start + quote.length, start + quote.length + 120),
      },
    });
  }

  const pinnedThreads =
    selected?.kind === "component"
      ? threads.filter(
          (t) =>
            t.root.selection?.kind === "component" &&
            t.root.selection.component_id === selected.id &&
            statusById[t.root.id] !== "moved",
        )
      : [];

  return {
    threads,
    count,
    selected,
    setSelected,
    statusById,
    onDetailClick,
    onDetailMouseUp,
    pinnedThreads,
  };
}

// The composer the selection pins beneath the stage.
// The inner AnnotationComposer carries the per-selection
// key, exactly as the inline element did, so each
// selection remounts the composer.
export function SelectionComposer({
  slug,
  entryId,
  selected,
  onClose,
}: {
  slug: string;
  entryId: string;
  selected: Selected;
  onClose: () => void;
}) {
  if (selected.kind === "component") {
    return (
      <AnnotationComposer
        key={`component:${selected.id}`}
        slug={slug}
        anchorType="component"
        anchorRef={entryId}
        selection={{
          kind: "component",
          component_id: selected.id,
          component_label: selected.label,
          entry_id: entryId,
        }}
        onClose={onClose}
        onSent={onClose}
      />
    );
  }
  return (
    <AnnotationComposer
      key={`text:${selected.selection.component_id}:${selected.selection.quote}`}
      slug={slug}
      anchorType="text"
      anchorRef={entryId}
      selection={selected.selection}
      quote={selected.selection.quote}
      onClose={onClose}
      onSent={onClose}
    />
  );
}
