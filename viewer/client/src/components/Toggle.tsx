// Toggle — one boolean, rendered as <button role="switch"> so
// Space/Enter toggle natively. Contract: docs/component-contracts.md#toggle.
import { type CSSProperties, useState } from "react";

export type ToggleProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
};

export function Toggle({ checked, onChange, label, disabled = false, className }: ToggleProps) {
  const [hover, setHover] = useState(false);
  const trackStyle: CSSProperties = checked
    ? {
        backgroundColor: hover && !disabled ? "var(--wb-accent-hover)" : "var(--wb-accent)",
        borderWidth: 0,
        borderRadius: "var(--wb-radius-pill)",
        transitionDuration: "var(--wb-motion-duration-pop)",
        transitionTimingFunction: "var(--wb-motion-ease)",
      }
    : {
        backgroundColor: "var(--wb-surface-sunken)",
        borderColor: hover && !disabled ? "var(--wb-accent)" : "var(--wb-border-strong)",
        borderStyle: "solid",
        borderWidth: 1,
        borderRadius: "var(--wb-radius-pill)",
        transitionDuration: "var(--wb-motion-duration-pop)",
        transitionTimingFunction: "var(--wb-motion-ease)",
      };
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={[
        "group inline-flex min-h-[38px] items-center gap-2 focus-visible:outline-none [@media(pointer:coarse)]:min-h-[44px]",
        disabled ? "cursor-not-allowed opacity-55" : "cursor-pointer",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span
        aria-hidden="true"
        className="relative inline-block h-6 w-10 shrink-0 group-focus-visible:outline-2 group-focus-visible:outline-solid group-focus-visible:outline-offset-1 group-focus-visible:outline-(--wb-focus-ring)"
        style={trackStyle}
      >
        <span
          aria-hidden="true"
          className="absolute top-1/2 inline-block h-[18px] w-[18px] rounded-full"
          style={{
            backgroundColor: checked ? "var(--wb-on-accent)" : "var(--wb-surface-2)",
            left: checked ? 19 : 3,
            transform: "translateY(-50%)",
            transitionDuration: "var(--wb-motion-duration-pop)",
            transitionTimingFunction: "var(--wb-motion-ease)",
            transitionProperty: "left",
          }}
        />
      </span>
      <span
        className="text-sm"
        style={{ color: disabled ? "var(--wb-content-secondary)" : "var(--wb-content-primary)" }}
      >
        {label}
      </span>
    </button>
  );
}
