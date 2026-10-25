// Sheet — modal panel / confirm sheet (the approve confirm is
// the canonical use). Escape (document listener) + backdrop
// button close; focus moves to the panel on open; the visible
// title is the accessible name.
// Contract: docs/component-contracts.md#sheet.
import { type ReactNode, useEffect, useRef } from "react";

export type SheetProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  className?: string;
  children?: ReactNode;
  footer?: ReactNode;
};

export function Sheet({ open, title, onClose, className, children, footer }: SheetProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end">
      <button
        type="button"
        aria-label="Dismiss"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
        style={{
          backgroundColor: "color-mix(in srgb, var(--wb-content-primary) 45%, transparent)",
          transitionDuration: "var(--wb-motion-duration-sheet)",
          transitionTimingFunction: "var(--wb-motion-ease)",
        }}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={[
          "relative m-2 flex w-full max-w-[480px] flex-col focus-visible:outline-none",
          className ?? "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={{
          backgroundColor: "var(--wb-surface-3)",
          borderColor: "var(--wb-border-default)",
          borderStyle: "solid",
          borderWidth: 1,
          borderRadius: "var(--wb-panel-radius)",
          boxShadow: "var(--wb-shadow-overlay)",
          padding: "var(--wb-panel-padding)",
          color: "var(--wb-content-primary)",
        }}
      >
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>
        <div className="flex-1">{children}</div>
        {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
      </div>
    </div>
  );
}
