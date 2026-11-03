// Button — the kit's only button. Sections never hand-roll one.
// Variants × states per docs/component-contracts.md#button.
import { type CSSProperties, type MouseEvent, type ReactNode, useState } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

export type ButtonProps = {
  variant?: ButtonVariant;
  /** Icon-only (row actions). Requires ariaLabel; never for destructive/disposition actions. */
  iconOnly?: boolean;
  ariaLabel?: string;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  children?: ReactNode;
};

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring)";

function variantStyle(variant: ButtonVariant, hover: boolean, active: boolean): CSSProperties {
  const base: CSSProperties = { borderRadius: "var(--wb-button-radius)" };
  switch (variant) {
    case "primary":
      return {
        ...base,
        backgroundColor: active
          ? "color-mix(in srgb, var(--wb-accent) 88%, black)"
          : hover
            ? "var(--wb-accent-hover)"
            : "var(--wb-accent)",
        color: "var(--wb-on-accent)",
        borderWidth: 0,
      };
    case "danger":
      return {
        ...base,
        backgroundColor: active
          ? "color-mix(in srgb, var(--wb-danger) 78%, black)"
          : hover
            ? "color-mix(in srgb, var(--wb-danger) 88%, black)"
            : "var(--wb-danger)",
        color: "var(--wb-on-accent)",
        borderWidth: 0,
      };
    case "secondary":
      return {
        ...base,
        backgroundColor: active
          ? "var(--wb-surface-sunken)"
          : hover
            ? "var(--wb-surface-1)"
            : "var(--wb-surface-2)",
        color: "var(--wb-content-primary)",
        borderColor: "var(--wb-border-strong)",
        borderStyle: "solid",
        borderWidth: 1,
      };
    case "ghost":
      return {
        ...base,
        backgroundColor: active
          ? "var(--wb-surface-sunken)"
          : hover
            ? "var(--wb-surface-1)"
            : "transparent",
        color: hover || active ? "var(--wb-content-primary)" : "var(--wb-content-secondary)",
        borderWidth: 0,
      };
  }
}

export function Button({
  variant = "primary",
  iconOnly = false,
  ariaLabel,
  type = "button",
  disabled = false,
  onClick,
  className,
  children,
}: ButtonProps) {
  const [hover, setHover] = useState(false);
  const [active, setActive] = useState(false);
  if (iconOnly && !ariaLabel) {
    throw new Error("Button: iconOnly requires ariaLabel");
  }
  const classes = [
    "inline-flex min-h-[38px] items-center justify-center gap-2 text-sm font-medium whitespace-nowrap select-none [@media(pointer:coarse)]:min-h-[44px]",
    iconOnly ? "w-[38px] px-0 [@media(pointer:coarse)]:w-[44px]" : "px-4",
    disabled ? "cursor-not-allowed opacity-55" : "cursor-pointer",
    FOCUS,
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  const track = (e: MouseEvent<HTMLButtonElement>) => {
    if (e.type === "mouseenter") setHover(true);
    if (e.type === "mouseleave") {
      setHover(false);
      setActive(false);
    }
    if (e.type === "mousedown") setActive(true);
    if (e.type === "mouseup") setActive(false);
  };

  return (
    <button
      type={type}
      disabled={disabled}
      aria-label={ariaLabel}
      onClick={onClick}
      onMouseEnter={track}
      onMouseLeave={track}
      onMouseDown={track}
      onMouseUp={track}
      className={classes}
      style={variantStyle(variant, !disabled && hover, !disabled && active)}
    >
      {children}
    </button>
  );
}
