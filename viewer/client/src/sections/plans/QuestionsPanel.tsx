// QuestionsPanel — the Plans reader's Questions card
// (plan syntax standard, Resolvable questions): one
// control per sentinel question in the plan's
// open-questions section — `choice` as a segmented
// control with the recommended option badged, `toggle`
// as a switch with the author's labels, `text` as an
// input. One Resolve posts the whole visible answer set
// with the file's sha256 as the compare-and-swap base
// (POST plan/resolve through the bridge); the answers
// land in the plan file itself. A 409 means the file
// moved under the reader: the panel says so and offers a
// reload — it never retries against the new bytes and
// never overwrites silently. Answered questions render
// in a resolved style (accent edge + the recorded
// answer), distinct from open ones; re-answering is
// allowed and posts as a change like any other.
//
// The reader mounts this panel keyed by the file's
// sha256, so a saved resolve (or a reload after a
// conflict) remounts it with values re-initialized from
// the recorded answers.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Toggle } from "../../components/Toggle";
import { api, type PlanDoc, type PlanQuestion } from "../../lib/api";
import { anchor } from "./anchors";
import { MarkdownBlock } from "./PlanBody";
import {
  initialValues,
  pendingAnswers,
  questionState,
  toggleChecked,
  toggleValue,
} from "./questions";

type Envelope = {
  status: number;
  payload: unknown;
  error: string | null;
};

const inputStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  border: "1px solid var(--wb-border-strong)",
  borderRadius: "var(--wb-radius-sm)",
  color: "var(--wb-content-primary)",
  font: "inherit",
  minHeight: "38px",
  padding: "0 var(--wb-space-12)",
  width: "100%",
  maxWidth: "52ch",
};

function QuestionRow({
  q,
  value,
  onChange,
  disabled,
}: {
  q: PlanQuestion;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  const state = questionState(q, { [q.id]: value });
  return (
    <div
      style={{
        borderLeft:
          state === "answered"
            ? "2px solid var(--wb-accent)"
            : "2px solid var(--wb-border-default)",
        paddingLeft: "var(--wb-space-16)",
        marginTop: "var(--wb-space-16)",
      }}
    >
      <MarkdownBlock text={q.text} sectionHeading="Open questions" />
      {q.detail ? <MarkdownBlock text={q.detail} sectionHeading="Open questions" /> : null}
      <div style={{ marginTop: "var(--wb-space-8)" }}>
        {q.type === "choice" ? (
          <SegmentedControl
            ariaLabel={q.text}
            options={q.options.map((option) => ({
              value: option,
              label: option === q.recommended ? `${option} · recommended` : option,
            }))}
            value={value}
            onChange={onChange}
            disabled={disabled}
          />
        ) : q.type === "toggle" ? (
          <Toggle
            checked={toggleChecked(q, value)}
            onChange={(checked) => onChange(toggleValue(q, checked))}
            label={toggleChecked(q, value) ? (q.labels[0] ?? "") : (q.labels[1] ?? "")}
            disabled={disabled}
          />
        ) : (
          <input
            type="text"
            value={value}
            disabled={disabled}
            onChange={(e) => onChange(e.target.value)}
            aria-label={q.text}
            placeholder="Your answer"
            style={inputStyle}
          />
        )}
      </div>
      <p
        style={{
          color: "var(--wb-content-secondary)",
          fontSize: "var(--wb-font-size-sm)",
          margin: "var(--wb-space-4) 0 0",
        }}
      >
        {state === "answered" ? (
          <>
            Answered: <span className="mono">{q.answer}</span>
            {value !== q.answer && value !== "" ? " — changed, not yet saved" : ""}
          </>
        ) : state === "staged" ? (
          "Answer staged — Resolve writes it into the plan file."
        ) : q.recommended ? (
          <>
            Recommended: <span className="mono">{q.recommended}</span>
          </>
        ) : (
          "Not answered yet."
        )}
      </p>
    </div>
  );
}

export function QuestionsPanel({ slug, path, doc }: { slug: string; path: string; doc: PlanDoc }) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>(() => initialValues(doc.questions));
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const pending = pendingAnswers(doc.questions, values);

  const mutation = useMutation({
    mutationFn: (answers: Record<string, string>) =>
      api.resolvePlanQuestions({
        slug,
        path,
        baseSha256: doc.file_sha256,
        answers,
      }) as Promise<Envelope>,
    onSuccess: (result) => {
      if (result.status === 200) {
        setConflict(false);
        setError(null);
        setSaved(true);
        queryClient.invalidateQueries({ queryKey: ["plan", slug, path] });
        queryClient.invalidateQueries({ queryKey: ["plans", slug] });
      } else if (result.status === 409) {
        // The file changed on disk: surface it, keep the
        // staged answers visible, write nothing.
        setConflict(true);
        setError(null);
        setSaved(false);
      } else {
        setConflict(false);
        setSaved(false);
        setError(result.error ?? `The server refused the resolve (status ${result.status}).`);
      }
    },
    onError: () => {
      setConflict(false);
      setSaved(false);
      setError("The resolve could not reach the companion server. Nothing was written.");
    },
  });

  const reload = () => {
    setConflict(false);
    queryClient.invalidateQueries({ queryKey: ["plan", slug, path] });
  };

  return (
    <div data-annotation-ui="true" style={{ marginTop: "var(--wb-space-24)" }}>
      <Card title="Questions" anchor={anchor.questionsPanel}>
        {doc.questions.map((q) => (
          <QuestionRow
            key={q.id}
            q={q}
            value={values[q.id] ?? ""}
            disabled={mutation.isPending}
            onChange={(value) => {
              setSaved(false);
              setValues((prev) => ({ ...prev, [q.id]: value }));
            }}
          />
        ))}
        {conflict ? (
          <div
            role="alert"
            style={{
              marginTop: "var(--wb-space-16)",
              border: "1px solid var(--wb-danger)",
              borderRadius: "var(--wb-radius-md)",
              padding: "var(--wb-space-12) var(--wb-space-16)",
            }}
          >
            <p style={{ margin: "0 0 var(--wb-space-8)" }}>
              This plan changed on disk since it was opened, so nothing was written. Reload to see
              the current file — the answers staged above will be reset to what the file records.
            </p>
            <Button variant="secondary" onClick={reload}>
              Reload the plan
            </Button>
          </div>
        ) : null}
        {error ? (
          <p role="alert" style={{ color: "var(--wb-danger)", marginTop: "var(--wb-space-16)" }}>
            {error}
          </p>
        ) : null}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-12)",
            marginTop: "var(--wb-space-16)",
            flexWrap: "wrap",
          }}
        >
          <Button
            variant="primary"
            disabled={mutation.isPending || Object.keys(pending).length === 0}
            onClick={() => mutation.mutate(pending)}
          >
            Resolve
          </Button>
          <span style={{ color: "var(--wb-content-secondary)" }}>
            {saved
              ? "Recorded in the plan file."
              : Object.keys(pending).length > 0
                ? `${Object.keys(pending).length} answer(s) staged.`
                : "Answers are written into the plan file itself."}
          </span>
        </div>
        {doc.sentinel_errors.length > 0 ? (
          <p
            style={{
              color: "var(--wb-content-muted)",
              fontSize: "var(--wb-font-size-sm)",
              marginTop: "var(--wb-space-12)",
            }}
          >
            {doc.sentinel_errors.length} malformed question sentinel(s) in this file render as plain
            questions instead:{" "}
            {doc.sentinel_errors.map((e) => `line ${e.line + 1} — ${e.reason}`).join("; ")}.
          </p>
        ) : null}
      </Card>
    </div>
  );
}
