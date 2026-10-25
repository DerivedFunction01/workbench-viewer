// DegradedBanner — per-project degraded state + plan
// source-format flags. An error names the section + the
// recovery in one sentence, once. Never danger tokens.
// Contract: docs/component-contracts.md#degradedbanner.
export type DegradedBannerProps = {
  tone?: "degraded" | "source-format";
  /** Section + problem, one sentence. */
  message: string;
  /** The recovery, one sentence. */
  detail?: string;
  className?: string;
};

export function DegradedBanner({
  tone = "degraded",
  message,
  detail,
  className,
}: DegradedBannerProps) {
  const degraded = tone === "degraded";
  return (
    <div
      role="status"
      className={["flex items-start gap-2 px-4 py-3", className ?? ""].filter(Boolean).join(" ")}
      style={
        degraded
          ? {
              backgroundColor: "color-mix(in srgb, var(--wb-status-stale) 14%, transparent)",
              borderColor: "var(--wb-status-stale)",
              borderStyle: "solid",
              borderWidth: 1,
              borderRadius: "var(--wb-radius-md)",
              color: "var(--wb-content-primary)",
            }
          : {
              backgroundColor: "var(--wb-surface-1)",
              borderColor: "var(--wb-border-default)",
              borderStyle: "solid",
              borderWidth: 1,
              borderRadius: "var(--wb-radius-md)",
              color: "var(--wb-content-primary)",
            }
      }
    >
      <span
        aria-hidden="true"
        className="shrink-0 text-sm leading-none"
        style={{ color: degraded ? "var(--wb-status-stale)" : "var(--wb-content-secondary)" }}
      >
        {degraded ? "⚠" : "ℹ"}
      </span>
      <div className="text-sm">
        <p>{message}</p>
        {detail ? <p style={{ color: "var(--wb-content-secondary)" }}>{detail}</p> : null}
      </div>
    </div>
  );
}
