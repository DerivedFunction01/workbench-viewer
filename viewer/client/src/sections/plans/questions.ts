// questions.ts — the resolvable-questions derivations
// behind the Plans reader's Questions card (plan syntax
// standard, the sentinel): pure functions over the
// parser's question records, kept free of React so the
// panel's state logic is testable without a DOM
// (viewer/tools/test-questions.ts).

import type { PlanBlock, PlanQuestion, PlanSection } from "../../lib/api";

/** Starting control values, keyed by question id: the
 * recorded answer ("" while a question is unanswered). */
export function initialValues(questions: PlanQuestion[]): Record<string, string> {
  const values: Record<string, string> = {};
  for (const q of questions) values[q.id] = q.answer;
  return values;
}

/** The answer set one Resolve posts: every question whose
 * current value is non-empty and differs from its
 * recorded answer. An emptied value never posts —
 * clearing an answer is not a resolution the sentinel
 * carries (an empty `answer=` IS the unanswered state). */
export function pendingAnswers(
  questions: PlanQuestion[],
  values: Record<string, string>,
): Record<string, string> {
  const pending: Record<string, string> = {};
  for (const q of questions) {
    const value = values[q.id] ?? "";
    if (value !== "" && value !== q.answer) pending[q.id] = value;
  }
  return pending;
}

/** A question's display state: `answered` when the file
 * records an answer, `staged` when the reader has one
 * locally that the next Resolve will write, else `open`. */
export function questionState(
  q: PlanQuestion,
  values: Record<string, string>,
): "answered" | "staged" | "open" {
  if (q.answer !== "") return "answered";
  if ((values[q.id] ?? "") !== "") return "staged";
  return "open";
}

/** One section's presentation in the reader (the
 * single-render rule): the Questions card shows at the
 * flagged section's position exactly when the plan
 * carries extracted questions, and that section then
 * renders its leftover blocks — the content no question
 * covers — in place of its full blocks, so a question
 * never renders both as markdown and as a control.
 * Every other section, and every section of a plan
 * without questions, renders its blocks as parsed. */
export function sectionPresentation(
  section: PlanSection,
  questionCount: number,
): { blocks: PlanBlock[]; showQuestions: boolean } {
  const showQuestions = section.is_open_questions && questionCount > 0;
  return {
    blocks: showQuestions ? (section.leftover_blocks ?? []) : section.blocks,
    showQuestions,
  };
}

/** The toggle's position for a value: on exactly when the
 * value is the author's on-label (labels[0]); an
 * unanswered toggle rests at off until it is touched. */
export function toggleChecked(q: PlanQuestion, value: string): boolean {
  return q.labels.length === 2 && value === q.labels[0];
}

/** The value a toggle flip records: the author's label
 * for the new position. */
export function toggleValue(q: PlanQuestion, checked: boolean): string {
  return checked ? (q.labels[0] ?? "") : (q.labels[1] ?? "");
}
