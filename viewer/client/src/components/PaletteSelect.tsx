// PaletteSelect — appearance setting, EXACT ruled contract
// (the owner, 2026-10-25 16:53 EDT; Subplan 05 codes #/settings
// against this signature). Palette ids arrive via props —
// never hardcoded here. ≤4 options ⇒ segmented; more ⇒ a
// native select (same appearance cells as an input row).
// Contract: docs/component-contracts.md#paletteselect.
import { useId } from "react";
import { SegmentedControl } from "./SegmentedControl";

export type PaletteSelectProps = {
  value: string;
  options: { id: string; label: string }[];
  onChange: (id: string) => void;
};

export function PaletteSelect({ value, options, onChange }: PaletteSelectProps) {
  const selectId = useId();
  if (options.length <= 4) {
    return (
      <SegmentedControl
        options={options.map((o) => ({ value: o.id, label: o.label }))}
        value={value}
        onChange={onChange}
        ariaLabel="Palette"
      />
    );
  }
  return (
    <>
      <label htmlFor={selectId} className="sr-only">
        Palette
      </label>
      <select
        id={selectId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[38px] cursor-pointer px-3 text-sm focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring) [@media(pointer:coarse)]:min-h-[44px]"
        style={{
          backgroundColor: "var(--wb-surface-2)",
          color: "var(--wb-content-primary)",
          borderColor: "var(--wb-border-default)",
          borderStyle: "solid",
          borderWidth: 1,
          borderRadius: "var(--wb-button-radius)",
        }}
      >
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </>
  );
}
