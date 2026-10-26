#!/usr/bin/env bun
// test-questions.ts — the Questions card derivations
// (client/src/sections/plans/questions.ts) against a
// fixture question set covering all three control types
// in their open, answered, and re-answered states. The
// panel's whole state logic rides on these: what starts
// in each control, what one Resolve posts, and which
// display state a row renders.
//
// Usage: bun viewer/tools/test-questions.ts
// Exit 1 on any failure.

import type { PlanBlock, PlanQuestion, PlanSection } from "../client/src/lib/api";
import {
  initialValues,
  pendingAnswers,
  questionState,
  sectionPresentation,
  toggleChecked,
  toggleValue,
} from "../client/src/sections/plans/questions";

function question(partial: Partial<PlanQuestion>): PlanQuestion {
  return {
    id: "q",
    type: "choice",
    text: "A question?",
    detail: "",
    options: [],
    labels: [],
    recommended: null,
    answer: "",
    checked: false,
    item_kind: "task",
    line: 0,
    sentinel_line: 1,
    answer_line: 2,
    ...partial,
  };
}

const choice = question({
  id: "q-store",
  type: "choice",
  options: ["messages store", "registry"],
  recommended: "messages store",
});
const answeredChoice = question({
  id: "q-kind",
  type: "choice",
  options: ["explainer", "ruling"],
  answer: "ruling",
  checked: true,
});
const toggle = question({
  id: "q-guard",
  type: "toggle",
  labels: ["guarded", "unguarded"],
});
const answeredToggle = question({
  id: "q-legacy",
  type: "toggle",
  labels: ["on", "off"],
  answer: "off",
  checked: true,
});
const text = question({ id: "q-name", type: "text" });
const all = [choice, answeredChoice, toggle, answeredToggle, text];

let failures = 0;
function check(name: string, ok: boolean, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${ok ? "" : ` (${detail})`}`);
  if (!ok) failures += 1;
}

const initial = initialValues(all);
check(
  "initial values carry recorded answers; unanswered start empty",
  initial["q-store"] === "" &&
    initial["q-kind"] === "ruling" &&
    initial["q-guard"] === "" &&
    initial["q-legacy"] === "off" &&
    initial["q-name"] === "",
  JSON.stringify(initial),
);

check(
  "nothing pending when values equal the recorded state",
  Object.keys(pendingAnswers(all, initial)).length === 0,
  JSON.stringify(pendingAnswers(all, initial)),
);

const staged = {
  ...initial,
  "q-store": "registry",
  "q-kind": "explainer",
  "q-guard": "guarded",
  "q-name": "decision sheet",
};
const pending = pendingAnswers(all, staged);
check(
  "pending carries new, changed, and free-text answers",
  pending["q-store"] === "registry" &&
    pending["q-kind"] === "explainer" &&
    pending["q-guard"] === "guarded" &&
    pending["q-name"] === "decision sheet" &&
    Object.keys(pending).length === 4,
  JSON.stringify(pending),
);

check(
  "an emptied value never posts (no un-answering)",
  Object.keys(pendingAnswers(all, { ...staged, "q-kind": "" })).length === 3,
);

check(
  "display states: answered / staged / open",
  questionState(answeredChoice, initial) === "answered" &&
    questionState(choice, staged) === "staged" &&
    questionState(choice, initial) === "open" &&
    questionState(text, staged) === "staged",
);

check(
  "toggle rests off while unanswered; on-label checks it",
  toggleChecked(toggle, "") === false &&
    toggleChecked(toggle, "guarded") === true &&
    toggleChecked(toggle, "unguarded") === false &&
    toggleChecked(answeredToggle, "off") === false,
);

check(
  "toggle flips record the author's labels",
  toggleValue(toggle, true) === "guarded" && toggleValue(toggle, false) === "unguarded",
);

const fullBlock: PlanBlock = { type: "markdown", text: "full", raw: "full" };
const leftoverBlock: PlanBlock = { type: "markdown", text: "leftover", raw: "leftover" };
function section(partial: Partial<PlanSection>): PlanSection {
  return {
    heading: "Open questions",
    level: 2,
    raw: "",
    blocks: [fullBlock],
    is_rulings: false,
    is_steps: false,
    is_open_questions: false,
    is_subplans: false,
    is_critical_files: false,
    ...partial,
  };
}
const flagged = section({
  is_open_questions: true,
  leftover_blocks: [leftoverBlock],
});

const withCard = sectionPresentation(flagged, 3);
check(
  "flagged section with questions: card shows, leftover blocks render",
  withCard.showQuestions === true &&
    withCard.blocks.length === 1 &&
    withCard.blocks[0] === leftoverBlock,
);

const noQuestions = sectionPresentation(flagged, 0);
check(
  "flagged section without questions: no card, full blocks render",
  noQuestions.showQuestions === false && noQuestions.blocks[0] === fullBlock,
);

const unflagged = sectionPresentation(section({}), 3);
check(
  "unflagged section never shows the card, even with questions elsewhere",
  unflagged.showQuestions === false && unflagged.blocks[0] === fullBlock,
);

const noLeftover = sectionPresentation(section({ is_open_questions: true }), 2);
check(
  "flagged section with no leftover field renders no blocks (never the covered ones)",
  noLeftover.showQuestions === true && noLeftover.blocks.length === 0,
);

console.log(`test-questions: ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
