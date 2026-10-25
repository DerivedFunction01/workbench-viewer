// StateControls — an entry's internal-state controls, GENERATED
// from its declared state_schema (SPEC §14.3; schema shape is the
// lib validator's: {field: {type: toggle|select|text|number,
// options?, default?, label?, min?, max?, step?}}). The schema is
// untrusted at this boundary: it is validated defensively at
// render — an invalid schema yields honest error rows, never a
// crash, and valid fields still render.
// Contract: docs/component-contracts.md#statecontrols.
import { type CSSProperties, type ReactNode, useId } from "react";
import { Button } from "./Button";
import { SegmentedControl } from "./SegmentedControl";
import { Toggle } from "./Toggle";

export type StateValue = boolean | string | number;
export type StateValues = Record<string, StateValue>;

export type StateControlsProps = {
  schema: unknown;
  values: StateValues;
  onChange: (key: string, value: StateValue) => void;
  title?: string;
  disabled?: boolean;
  className?: string;
};

type FieldSpec = {
  type: "toggle" | "select" | "text" | "number";
  options?: string[];
  label?: string;
  min?: number;
  max?: number;
  step?: number;
};

const FIELD_TYPES = ["toggle", "select", "text", "number"];

function humanize(key: string): string {
  const words = key.replace(/_/g, " ").trim();
  return words.length > 0 ? words.charAt(0).toUpperCase() + words.slice(1) : key;
}

/** Returns a problem string, or the usable spec. Mirrors the lib
 * validator's checks (check_state_schema) plus value conformance. */
function validateField(key: string, raw: unknown, value: StateValue | undefined): string | null {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return `Field "${key}": spec must be an object`;
  }
  const spec = raw as Record<string, unknown>;
  const type = spec.type;
  if (typeof type !== "string" || !FIELD_TYPES.includes(type)) {
    return `Field "${key}": type must be one of ${FIELD_TYPES.join(", ")}`;
  }
  if (type === "select") {
    const options = spec.options;
    if (
      !Array.isArray(options) ||
      options.length === 0 ||
      !options.every((o) => typeof o === "string")
    ) {
      return `Field "${key}": select needs a non-empty options list of strings`;
    }
    if (value !== undefined && typeof value !== "string") {
      return `Field "${key}": select value must be text`;
    }
    if (value !== undefined && !options.includes(value as string)) {
      return `Field "${key}": value is not one of its options`;
    }
  }
  if (type === "toggle" && value !== undefined && typeof value !== "boolean") {
    return `Field "${key}": toggle needs true/false`;
  }
  if (type === "number" && value !== undefined && typeof value !== "number") {
    return `Field "${key}": needs a number`;
  }
  if (type === "text" && value !== undefined && typeof value !== "string") {
    return `Field "${key}": needs text`;
  }
  return null;
}

function asSpec(raw: unknown): FieldSpec {
  return raw as FieldSpec;
}

const INPUT_STYLE: CSSProperties = {
  backgroundColor: "var(--wb-surface-2)",
  color: "var(--wb-content-primary)",
  borderColor: "var(--wb-border-default)",
  borderStyle: "solid",
  borderWidth: 1,
  borderRadius: "var(--wb-button-radius)",
};

const INPUT_CLASSES =
  "min-h-[38px] px-3 text-sm focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring) disabled:cursor-not-allowed disabled:opacity-55 [@media(pointer:coarse)]:min-h-[44px]";

function FieldError({ problem }: { problem: string }) {
  return (
    <p
      role="alert"
      className="px-3 py-2 text-sm"
      style={{
        backgroundColor: "color-mix(in srgb, var(--wb-status-stale) 14%, transparent)",
        borderColor: "var(--wb-status-stale)",
        borderStyle: "solid",
        borderWidth: 1,
        borderRadius: "var(--wb-radius-md)",
        color: "var(--wb-content-primary)",
      }}
    >
      <span aria-hidden="true" style={{ color: "var(--wb-status-stale)" }}>
        ⚠{" "}
      </span>
      {problem}
    </p>
  );
}

export function StateControls({
  schema,
  values,
  onChange,
  title = "State",
  disabled = false,
  className,
}: StateControlsProps) {
  const baseId = useId();

  let body: ReactNode;
  if (typeof schema !== "object" || schema === null || Array.isArray(schema)) {
    body = <FieldError problem="State schema must be an object of field specs" />;
  } else {
    const entries = Object.entries(schema as Record<string, unknown>);
    if (entries.length === 0) {
      body = <FieldError problem="State schema declares no fields" />;
    } else {
      body = entries.map(([key, raw]) => {
        const problem = validateField(key, raw, values[key]);
        const spec = asSpec(raw);
        const label =
          typeof spec?.label === "string" && spec.label.length > 0 ? spec.label : humanize(key);
        const controlId = `${baseId}-${key}`;
        if (problem) {
          return (
            <div key={key} className="py-2">
              <FieldError problem={problem} />
            </div>
          );
        }
        const value = values[key];
        let labelIsSpan = false;
        let control: ReactNode = null;
        if (spec.type === "toggle") {
          control = (
            <Toggle
              checked={value === true}
              onChange={(v) => onChange(key, v)}
              label={label}
              disabled={disabled}
            />
          );
          return (
            <div key={key} className="py-1">
              {control}
            </div>
          );
        }
        if (spec.type === "select") {
          const options = spec.options ?? [];
          const current = typeof value === "string" ? value : (options[0] ?? "");
          labelIsSpan = options.length <= 4;
          control =
            options.length <= 4 ? (
              <SegmentedControl
                options={options.map((o) => ({ value: o, label: humanize(o) }))}
                value={current}
                onChange={(v) => onChange(key, v)}
                ariaLabel={label}
                disabled={disabled}
              />
            ) : (
              <select
                id={controlId}
                value={current}
                disabled={disabled}
                onChange={(e) => onChange(key, e.target.value)}
                className={INPUT_CLASSES}
                style={INPUT_STYLE}
              >
                {options.map((o) => (
                  <option key={o} value={o}>
                    {humanize(o)}
                  </option>
                ))}
              </select>
            );
        } else if (spec.type === "number") {
          const current = typeof value === "number" ? value : 0;
          const step = typeof spec.step === "number" ? spec.step : 1;
          const clamp = (n: number) => {
            let out = n;
            if (typeof spec.min === "number") out = Math.max(spec.min, out);
            if (typeof spec.max === "number") out = Math.min(spec.max, out);
            return out;
          };
          control = (
            <span className="inline-flex items-center gap-2">
              <Button
                variant="ghost"
                iconOnly
                ariaLabel={`Decrease ${label}`}
                disabled={disabled}
                onClick={() => onChange(key, clamp(current - step))}
              >
                −
              </Button>
              <input
                id={controlId}
                type="number"
                className={`${INPUT_CLASSES} num w-[72px] text-center`}
                style={INPUT_STYLE}
                value={current}
                min={spec.min}
                max={spec.max}
                step={step}
                disabled={disabled}
                onChange={(e) => {
                  const n = e.target.valueAsNumber;
                  if (!Number.isNaN(n)) onChange(key, clamp(n));
                }}
              />
              <Button
                variant="ghost"
                iconOnly
                ariaLabel={`Increase ${label}`}
                disabled={disabled}
                onClick={() => onChange(key, clamp(current + step))}
              >
                +
              </Button>
            </span>
          );
        } else {
          control = (
            <input
              id={controlId}
              type="text"
              className={`${INPUT_CLASSES} w-[200px]`}
              style={INPUT_STYLE}
              value={typeof value === "string" ? value : ""}
              disabled={disabled}
              onChange={(e) => onChange(key, e.target.value)}
            />
          );
        }
        return (
          <div key={key} className="flex items-center justify-between gap-4 py-1">
            {labelIsSpan ? (
              <span className="text-sm" style={{ color: "var(--wb-content-primary)" }}>
                {label}
              </span>
            ) : (
              <label
                htmlFor={controlId}
                className="text-sm"
                style={{ color: "var(--wb-content-primary)" }}
              >
                {label}
              </label>
            )}
            {control}
          </div>
        );
      });
    }
  }

  return (
    <section
      aria-label={title}
      className={className}
      style={{
        backgroundColor: "var(--wb-surface-2)",
        borderColor: "var(--wb-border-default)",
        borderStyle: "solid",
        borderWidth: 1,
        borderRadius: "var(--wb-panel-radius)",
        padding: "var(--wb-panel-padding)",
      }}
    >
      <h3
        className="mb-3 text-xs font-semibold tracking-[0.06em] uppercase"
        style={{ color: "var(--wb-content-secondary)" }}
      >
        {title}
      </h3>
      {body}
    </section>
  );
}
