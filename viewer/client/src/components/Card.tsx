// Card — the static content card. No shadow (elevation is the
// surface ladder + border). Contract: docs/component-contracts.md#card.
import type { ReactNode } from "react";

export type CardProps = {
  title?: ReactNode;
  /** Right end of the title row — kit Buttons only. */
  actions?: ReactNode;
  /** Anchor id (`<section-or-exhibit>/<component>`, §14) — renders `data-anchor` on the root. */
  anchor?: string;
  className?: string;
  children?: ReactNode;
};

export function Card({ title, actions, anchor, className, children }: CardProps) {
  return (
    <section
      data-anchor={anchor}
      className={className}
      style={{
        backgroundColor: "var(--wb-card-bg)",
        borderColor: "var(--wb-border-default)",
        borderStyle: "solid",
        borderWidth: 1,
        borderRadius: "var(--wb-card-radius)",
        padding: "var(--wb-card-padding)",
        color: "var(--wb-content-primary)",
      }}
    >
      {title ? (
        <div className="mb-3 flex items-center justify-between gap-4">
          <h3 className="text-sm font-semibold">{title}</h3>
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
