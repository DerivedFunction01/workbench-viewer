// SegmentedControl — one choice from a small enum, built on
// NATIVE radio inputs (visually hidden, labels styled as
// segments): the radio group gives the WAI-APG pattern for
// free — one Tab stop per group, arrow keys move + select.
// The primitive under ModeControl, PaletteSelect (few-option
// form), DensityToggle and StateControls select fields.
// Contract: docs/component-contracts.md#segmentedcontrol.
import { useId } from "react";

export type SegmentedOption<V extends string> = { value: V; label: string };

export type SegmentedControlProps<V extends string> = {
  options: SegmentedOption<V>[];
  value: V;
  onChange: (value: V) => void;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
};

const SEGMENT_CLASSES = [
  "inline-flex min-h-[30px] cursor-pointer items-center rounded-[var(--wb-radius-sm)] border border-transparent px-3 text-sm whitespace-nowrap",
  "text-(--wb-content-secondary) hover:text-(--wb-content-primary)",
  "peer-checked:border-(--wb-border-default) peer-checked:bg-(--wb-surface-2) peer-checked:font-semibold peer-checked:text-(--wb-content-primary)",
  "peer-focus-visible:outline-2 peer-focus-visible:outline-solid peer-focus-visible:outline-offset-1 peer-focus-visible:outline-(--wb-focus-ring)",
  "peer-disabled:cursor-not-allowed",
].join(" ");

export function SegmentedControl<V extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  disabled = false,
  className,
}: SegmentedControlProps<V>) {
  const name = useId();
  return (
    <fieldset
      className={[
        "m-0 inline-flex min-h-[38px] items-center gap-1 border-0 p-1 [@media(pointer:coarse)]:min-h-[44px]",
        disabled ? "opacity-55" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ backgroundColor: "var(--wb-surface-sunken)", borderRadius: "var(--wb-radius-sm)" }}
    >
      <legend className="sr-only">{ariaLabel}</legend>
      {options.map((opt) => (
        <label key={opt.value} className="inline-flex">
          <input
            type="radio"
            name={name}
            value={opt.value}
            checked={opt.value === value}
            disabled={disabled}
            onChange={() => onChange(opt.value)}
            className="peer sr-only"
          />
          <span className={SEGMENT_CLASSES}>{opt.label}</span>
        </label>
      ))}
    </fieldset>
  );
}
