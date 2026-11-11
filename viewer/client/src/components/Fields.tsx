// Fields — the kit's form controls (F4 of the 2026-11-10
// entries critic pass): a native <select> and a native
// <input> under kit chrome, plus the Field labelled
// wrapper. Native semantics underneath, exactly as
// SegmentedControl sits on native radios: the browser's
// own behaviour (IME, autofill, screen readers, the
// platform picker) is the kit's, and the chrome is the
// StateControls input/select row's — surface-2 fill,
// 1px border-default, button radius, primary text, 38px
// (44px coarse), the one focus ring, hover border-strong,
// disabled surface-1 + opacity 0.55 + secondary text —
// so StateControls' generated fields and the hand-built
// forms render as one family. The appearance idiom lives
// HERE and StateControls consumes it too, so the two
// never drift.
// Contract: context/component-contracts.md#fields.

import {
  type CSSProperties,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  useId,
} from "react";

/** The field appearance, shared by StateControls and the
 * hand-built forms. Inline style for the token plumbing
 * (the kit's convention); classes carry sizing, the focus
 * ring, and the disabled treatment. */
export const FIELD_STYLE: CSSProperties = {
  backgroundColor: "var(--wb-surface-2)",
  color: "var(--wb-content-primary)",
  borderColor: "var(--wb-border-default)",
  borderStyle: "solid",
  borderWidth: 1,
  borderRadius: "var(--wb-button-radius)",
};

export const FIELD_CLASSES =
  "min-h-[38px] px-3 text-sm focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring) disabled:cursor-not-allowed disabled:opacity-55 [@media(pointer:coarse)]:min-h-[44px]";

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  options: { value: string; label: string; disabled?: boolean }[];
  ariaLabel?: string;
};

/** A native select in kit chrome. Options are data, not
 * children, so every call site states its full option set
 * (including an explicit placeholder option when the
 * field starts unset). */
export function Select({ options, ariaLabel, className, style, ...rest }: SelectProps) {
  return (
    <select
      aria-label={ariaLabel}
      className={[FIELD_CLASSES, className ?? ""].filter(Boolean).join(" ")}
      style={{ ...FIELD_STYLE, ...style }}
      {...rest}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value} disabled={option.disabled}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  ariaLabel?: string;
};

/** A native text input in kit chrome (type="text" and
 * type="search" are the ruled forms; other types pass
 * through the same chrome). */
export function Input({ ariaLabel, className, style, ...rest }: InputProps) {
  return (
    <input
      aria-label={ariaLabel}
      className={[FIELD_CLASSES, className ?? ""].filter(Boolean).join(" ")}
      style={{ ...FIELD_STYLE, ...style }}
      {...rest}
    />
  );
}

export type FieldProps = {
  /** The visible label, rendered in the kit label idiom
   * (12px uppercase secondary — the entries field label). */
  label: string;
  /** Visually hidden label instead (filter-bar groups,
   * where the group heading names the field). */
  labelHidden?: boolean;
  /** The control: a render prop receiving the generated
   * id, so any kit control binds to the label. */
  children: (id: string) => ReactNode;
  className?: string;
  style?: CSSProperties;
};

/** The labelled-field wrapper: a visible label bound to
 * its control by htmlFor, in the label idiom the entries
 * forms already use. The label is a statement of what the
 * field IS; validation and consequence text live with the
 * control's section, never in the label. */
export function Field({ label, labelHidden = false, children, className, style }: FieldProps) {
  const id = useId();
  return (
    <label className={className} style={{ display: "block", ...style }} htmlFor={id}>
      <span
        className={labelHidden ? "sr-only" : undefined}
        style={
          labelHidden
            ? undefined
            : {
                display: "block",
                color: "var(--wb-content-secondary)",
                fontSize: "var(--wb-font-size-xs)",
                lineHeight: "var(--wb-line-height-xs)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "var(--wb-space-4)",
              }
        }
      >
        {label}
      </span>
      {children(id)}
    </label>
  );
}
