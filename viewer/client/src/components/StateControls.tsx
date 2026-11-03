// StateControls — an entry's internal-state controls, GENERATED
// from its declared state_schema (SPEC §14.3; schema shape is the
// lib validator's: {field: {type: toggle|select|text|number,
// options?, default?, label?, min?, max?, step?, question?,
// recommended?, option_notes?}}). A field that declares a
// question renders as a DECISION BLOCK (SPEC §5.1): the prompt
// leads, and a select question's options render as full-width
// rows carrying the recommended badge and each option's
// explanation inside the row — each fact stated once, nothing
// repeated under the control. Toggle/text/number questions
// keep the prompt + control + Recommended line form. Fields
// without a question keep the label/control row (stacked on
// phone). The schema is
// untrusted at this boundary: it is validated defensively at
// render — an invalid schema yields honest error rows, never a
// crash, and valid fields still render.
// Contract: docs/component-contracts.md#statecontrols.
import { type CSSProperties, type ReactNode, useId } from "react";
import { useIsPhone } from "../lib/responsive";
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
  /** Anchor id (`<section-or-exhibit>/<component>`, §14) — renders `data-anchor` on the container. */
  anchor?: string;
  className?: string;
};

type FieldSpec = {
  type: "toggle" | "select" | "text" | "number";
  options?: string[];
  label?: string;
  min?: number;
  max?: number;
  step?: number;
  question?: string;
  recommended?: StateValue;
  option_notes?: Record<string, string>;
};

/** The declared recommendation, when usable for the field's
 * type (the lib validator's rule: one of the options for a
 * select, a boolean for a toggle, a value of the type
 * otherwise). Unusable values are ignored, never rendered. */
function recommendedValue(spec: FieldSpec): StateValue | undefined {
  const rec = spec.recommended;
  if (rec === undefined) return undefined;
  if (spec.type === "toggle") return typeof rec === "boolean" ? rec : undefined;
  if (spec.type === "select") {
    return typeof rec === "string" && (spec.options ?? []).includes(rec) ? rec : undefined;
  }
  if (spec.type === "number") return typeof rec === "number" ? rec : undefined;
  return typeof rec === "string" ? rec : undefined;
}

/** Explanation text per option, restricted to real options
 * carrying text. */
function optionNotes(spec: FieldSpec): [string, string][] {
  const notes = spec.option_notes;
  if (typeof notes !== "object" || notes === null) return [];
  const options = spec.options ?? [];
  return Object.entries(notes).filter(
    (entry): entry is [string, string] =>
      options.includes(entry[0]) && typeof entry[1] === "string",
  );
}

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

/** Option rows for a select QUESTION field — the decision
 * block's control. One full-width row per option carrying,
 * in one unit: the option label (wraps freely, never
 * nowrap), the "· recommended" badge on the recommended
 * option (the ONLY place a select question states it), and
 * the option's note as the row's secondary text. No notes
 * block follows: each fact renders once, inside its row.
 * Native radios in a fieldset — the SegmentedControl
 * semantics (one Tab stop per group, arrows move +
 * select); the selected row takes the checked-segment
 * styling (border, surface-2, semibold label). */
function OptionRows({
  options,
  value,
  recommended,
  notes,
  ariaLabel,
  disabled,
  onChange,
}: {
  options: string[];
  value: string;
  recommended?: StateValue;
  notes: Map<string, string>;
  ariaLabel: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const name = useId();
  return (
    <fieldset
      className={[
        "m-0 flex w-full min-w-0 flex-col gap-1 border-0 p-1",
        disabled ? "opacity-55" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        backgroundColor: "var(--wb-surface-sunken)",
        borderRadius: "var(--wb-radius-sm)",
      }}
    >
      <legend className="sr-only">{ariaLabel}</legend>
      {options.map((option) => {
        const checked = option === value;
        const note = notes.get(option);
        return (
          <label key={option} className="block min-w-0 cursor-pointer">
            <input
              type="radio"
              name={name}
              value={option}
              checked={checked}
              disabled={disabled}
              onChange={() => onChange(option)}
              className="peer sr-only"
            />
            <span
              className={[
                "flex min-h-[38px] flex-col justify-center gap-0.5 rounded-[var(--wb-radius-sm)] border border-transparent px-3 py-2 [@media(pointer:coarse)]:min-h-[44px]",
                "peer-checked:border-(--wb-border-default) peer-checked:bg-(--wb-surface-2)",
                "peer-focus-visible:outline-2 peer-focus-visible:outline-solid peer-focus-visible:outline-offset-1 peer-focus-visible:outline-(--wb-focus-ring)",
                "peer-disabled:cursor-not-allowed",
              ].join(" ")}
            >
              <span
                className="text-sm"
                style={{
                  color: checked ? "var(--wb-content-primary)" : "var(--wb-content-secondary)",
                  fontWeight: checked ? 600 : 400,
                }}
              >
                {humanize(option)}
                {option === recommended ? (
                  <span style={{ color: "var(--wb-content-secondary)", fontWeight: 400 }}>
                    {" · recommended"}
                  </span>
                ) : null}
              </span>
              {note ? (
                <span className="text-sm" style={{ color: "var(--wb-content-secondary)" }}>
                  {note}
                </span>
              ) : null}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}

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
  anchor,
  className,
}: StateControlsProps) {
  const baseId = useId();
  const isPhone = useIsPhone();

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
        // The question keys (SPEC §5.1/§14.4): the prompt,
        // the marked recommendation, the per-option
        // explanations — rendered for every field that
        // declares them, whatever the entry's kind.
        const question =
          typeof spec.question === "string" && spec.question.length > 0 ? spec.question : null;
        const recommended = recommendedValue(spec);
        const notes = optionNotes(spec);
        const questionBlock = question ? (
          <p className="text-sm" style={{ margin: "0 0 var(--wb-space-4)", fontWeight: 600 }}>
            {question}
          </p>
        ) : null;
        const recommendedLine =
          recommended !== undefined && spec.type !== "select" ? (
            <p
              className="text-sm"
              style={{
                margin: "var(--wb-space-4) 0 0",
                color: "var(--wb-content-secondary)",
              }}
            >
              Recommended:{" "}
              {spec.type === "toggle" ? (recommended ? "On" : "Off") : String(recommended)}
            </p>
          ) : null;
        const notesBlock =
          notes.length > 0 ? (
            <div style={{ marginTop: "var(--wb-space-4)" }}>
              {notes.map(([option, note]) => (
                <p
                  key={option}
                  className="text-sm"
                  style={{
                    margin: "0 0 var(--wb-space-2)",
                    color: "var(--wb-content-secondary)",
                  }}
                >
                  <span className="mono">{option}</span>
                  {option === recommended ? " (recommended)" : ""} — {note}
                </p>
              ))}
            </div>
          ) : null;
        const underBlock =
          recommendedLine || notesBlock ? (
            <>
              {recommendedLine}
              {notesBlock}
            </>
          ) : null;
        if (question && spec.type === "select") {
          // The decision block: the field's short label as
          // a muted eyebrow (identity preserved — there is
          // no side-by-side label column here), the prompt,
          // then the option rows. No underBlock: the badge
          // and the notes live inside the rows, stated once.
          const options = spec.options ?? [];
          const current = typeof value === "string" ? value : (options[0] ?? "");
          return (
            <div key={key} className="py-1">
              <p
                className="text-xs font-semibold tracking-[0.06em] uppercase"
                style={{ margin: "0 0 var(--wb-space-2)", color: "var(--wb-content-muted)" }}
              >
                {label}
              </p>
              {questionBlock}
              <OptionRows
                options={options}
                value={current}
                recommended={recommended}
                notes={new Map(notes)}
                ariaLabel={question}
                disabled={disabled}
                onChange={(v) => onChange(key, v)}
              />
            </div>
          );
        }
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
              {questionBlock}
              {control}
              {underBlock}
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
                className={isPhone ? "w-full" : undefined}
                options={options.map((o) => ({
                  value: o,
                  label: humanize(o) + (o === recommended ? " · recommended" : ""),
                }))}
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
                className={`${INPUT_CLASSES}${isPhone ? " w-full" : ""}`}
                style={INPUT_STYLE}
              >
                {options.map((o) => (
                  <option key={o} value={o}>
                    {humanize(o)}
                    {o === recommended ? " (recommended)" : ""}
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
              className={`${INPUT_CLASSES} ${isPhone ? "w-full" : "w-[200px]"}`}
              style={INPUT_STYLE}
              value={typeof value === "string" ? value : ""}
              disabled={disabled}
              onChange={(e) => onChange(key, e.target.value)}
            />
          );
        }
        return (
          <div key={key} className="py-1">
            {questionBlock}
            <div
              className={
                isPhone ? "flex flex-col gap-2" : "flex items-center justify-between gap-4"
              }
            >
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
            {underBlock}
          </div>
        );
      });
    }
  }

  return (
    <section
      data-anchor={anchor}
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
