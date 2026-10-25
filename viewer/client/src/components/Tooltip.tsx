// Tooltip — the ONE tooltip system: the data-tip mechanism.
// No native title, no second system. The tip appears on hover
// and on focus-within after a 300ms delay; it is a label aid
// only (icon Buttons still carry aria-label).
// Contract: docs/component-contracts.md#tooltip.
import type { ReactNode } from "react";

export type TooltipProps = {
  text: string;
  className?: string;
  children: ReactNode;
};

const TIP_CLASSES = [
  "after:pointer-events-none after:absolute after:bottom-full after:left-1/2 after:z-50 after:mb-2",
  "after:-translate-x-1/2 after:px-2 after:py-1 after:text-xs after:whitespace-nowrap",
  "after:bg-(--wb-content-primary) after:text-(--wb-surface-1)",
  "after:rounded-[var(--wb-radius-sm)] after:shadow-[var(--wb-shadow-overlay)]",
  "after:opacity-0 after:transition-opacity after:duration-(--wb-motion-duration-pop)",
  "after:content-[attr(data-tip)]",
  "group-focus-within:after:opacity-100 group-focus-within:after:delay-300",
  "group-hover:after:opacity-100 group-hover:after:delay-300",
].join(" ");

export function Tooltip({ text, className, children }: TooltipProps) {
  return (
    <span
      data-tip={text}
      className={["group relative inline-flex", TIP_CLASSES, className ?? ""]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </span>
  );
}
