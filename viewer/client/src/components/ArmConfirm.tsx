// ArmConfirm — the commit guard (q2 arm-confirm, F3 of
// the 2026-11-10 entries critic pass). A lifecycle commit
// never fires on a single activation: the first activation
// ARMS the control in place — the button becomes its
// confirm form and a plain-voice statement of the action,
// its object, and its consequence renders under the
// control row — and only a second activation commits.
// Any change to the inputs the commit reads (the
// `disarmKey`) disarms it, so a confirmed statement can
// never describe a different commit than the one that
// fires. A disabled control states its reason beside it
// in plain voice instead of sitting silent.
//
// The behaviour is the primitive, not the paint: the
// guard wraps a kit Button and owns only the arm state
// and the statement. Lifecycle mutations route through
// this component — the arm-guard check
// (viewer/tools/check-arm-guard.py) fails any lifecycle
// verb that fires outside it.
// Contract: context/component-contracts.md#armconfirm.

import { type ReactNode, useState } from "react";
import { Button } from "./Button";

export type ArmConfirmProps = {
  /** The control's own label, e.g. "Verify". */
  label: string;
  /** The armed form's label, e.g. "Confirm verify". */
  confirmLabel: string;
  /** The plain-voice statement shown while armed: the
   * action, its object, and its consequence. */
  statement: string;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean;
  /** Why the control is disabled, in plain voice —
   * rendered beside it. Required for the statement to
   * exist at all when disabled. */
  disabledReason?: string;
  /** A mutation is in flight (the wrapped button's busy
   * state): the control disables and any arm clears. */
  busy?: boolean;
  /** Everything the commit reads, serialized: any change
   * disarms. Pass the field values the commit will send. */
  disarmKey: string;
  onConfirm: () => void;
  children?: ReactNode;
};

export function ArmConfirm({
  label,
  confirmLabel,
  statement,
  variant = "secondary",
  disabled = false,
  disabledReason,
  busy = false,
  disarmKey,
  onConfirm,
}: ArmConfirmProps) {
  const [armed, setArmed] = useState(false);
  // Any change to what the commit reads, or a mutation
  // landing, returns the control to its resting form:
  // the statement the reader confirmed must be the
  // commit that fires. (State adjusted during render —
  // the React-docs pattern for prop-derived resets.)
  const [armStamp, setArmStamp] = useState("");
  const stamp = `${disarmKey}|${busy ? "busy" : "idle"}`;
  if (armed && stamp !== armStamp) setArmed(false);
  const inert = disabled || busy;
  return (
    <span style={{ display: "inline-flex", flexDirection: "column", gap: "var(--wb-space-4)" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--wb-space-8)" }}>
        <Button
          variant={variant}
          disabled={inert}
          onClick={() => {
            if (armed) {
              setArmed(false);
              onConfirm();
            } else {
              setArmStamp(stamp);
              setArmed(true);
            }
          }}
        >
          {armed ? confirmLabel : label}
        </Button>
        {disabled && disabledReason ? (
          <span
            style={{ color: "var(--wb-content-secondary)", fontSize: "var(--wb-font-size-sm)" }}
          >
            {disabledReason}
          </span>
        ) : null}
      </span>
      {armed && !inert ? (
        <span
          role="status"
          style={{ color: "var(--wb-content-secondary)", fontSize: "var(--wb-font-size-sm)" }}
        >
          {statement}
        </span>
      ) : null}
    </span>
  );
}
