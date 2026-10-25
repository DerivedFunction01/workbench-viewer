// EmptyState — honest empty: a sunken well, one line, styled
// as content. Empty is a state, not an error.
// Contract: docs/component-contracts.md#emptystate.
import type { ReactNode } from "react";

export type EmptyStateProps = {
  /** The one line, e.g. "No mockups match these filters". */
  message: string;
  detail?: string;
  /** A kit Button, if a recovery action exists. At most one. */
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ message, detail, action, className }: EmptyStateProps) {
  return (
    <div
      className={["flex flex-col items-center justify-center gap-2 text-center", className ?? ""]
        .filter(Boolean)
        .join(" ")}
      style={{
        backgroundColor: "var(--wb-surface-sunken)",
        borderColor: "var(--wb-border-default)",
        borderStyle: "dashed",
        borderWidth: 1,
        borderRadius: "var(--wb-radius-lg)",
        padding: "var(--wb-panel-padding)",
      }}
    >
      <p className="text-sm" style={{ color: "var(--wb-content-secondary)" }}>
        {message}
      </p>
      {detail ? (
        <p className="text-xs" style={{ color: "var(--wb-content-muted)" }}>
          {detail}
        </p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
