// ModeControl — appearance setting, EXACT ruled contract
// (the owner, 2026-10-25 16:53 EDT; Subplan 05 codes #/settings
// against this signature). Pure: the shell applies + persists.
// Contract: docs/component-contracts.md#modecontrol.
import { SegmentedControl } from "./SegmentedControl";

export type ModeValue = "system" | "light" | "dark";

export type ModeControlProps = {
  value: ModeValue;
  onChange: (v: ModeValue) => void;
};

const OPTIONS = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
] as const;

export function ModeControl({ value, onChange }: ModeControlProps) {
  return (
    <SegmentedControl
      options={[...OPTIONS]}
      value={value}
      onChange={onChange}
      ariaLabel="Color mode"
    />
  );
}
