// DensityToggle — appearance setting, EXACT ruled contract
// (the owner, 2026-10-25 16:53 EDT; Subplan 05 codes #/settings
// against this signature). Pure: the shell applies + persists.
// Contract: docs/component-contracts.md#densitytoggle.
import { SegmentedControl } from "./SegmentedControl";

export type DensityValue = "comfortable" | "compact";

export type DensityToggleProps = {
  value: DensityValue;
  onChange: (v: DensityValue) => void;
};

const OPTIONS = [
  { value: "comfortable", label: "Comfortable" },
  { value: "compact", label: "Compact" },
] as const;

export function DensityToggle({ value, onChange }: DensityToggleProps) {
  return (
    <SegmentedControl
      options={[...OPTIONS]}
      value={value}
      onChange={onChange}
      ariaLabel="Density"
    />
  );
}
