"""Resolvable plan questions (plan syntax standard):
sentinel extraction in lib/plans/parser.py and the
apply_answers composition. Fixtures are synthetic; the
live-corpus losslessness proof stays in test_plans.py."""

import unittest

from lib.plans import parser as plan_parser

CHOICE_PLAN = """# A plan with questions

Status: draft

## Objective

Do a thing.

## Open questions

- [ ] Which store holds the index?
  - Recommendation: the messages store.
  <!-- wb-question
  id=q-store
  type=choice
  options=messages store | registry | a new store
  recommended=messages store
  answer=
  -->
- [ ] Nightly cleanup of the message store
  - Recommendation: enabled.
  <!-- wb-question
  id=q-cleanup
  type=toggle
  labels=Enabled | Disabled
  recommended=Enabled
  answer=
  -->
- [ ] What name should the new entry kind carry?
  <!-- wb-question
  id=q-kind-name
  type=text
  answer=
  -->
- [ ] A plain question with no sentinel?
  - Recommendation: none needed.

## Critical files

- `lib/plans/parser.py`
"""

ANSWERED_PLAN = """# An answered plan

Status: draft

## Open questions

- [x] Which store holds the index?
  - Recommendation: the messages store.
  <!-- wb-question
  id=q-store
  type=choice
  options=messages store | registry
  recommended=messages store
  answer=registry
  -->
"""

LEGACY_PLAN = """# Determination

Status: determination — awaiting a ruling

## Open questions for the owner

1. **Kind name**: `explainer`, `ruling`, or `decision` —
   the word every repo will filter by.
   <!-- wb-question
   id=q-kind
   type=choice
   options=explainer | ruling | decision
   recommended=explainer
   answer=
   -->
2. **Pilot scope**: the big entry, or a smaller set?
   <!-- wb-question
   id=q-pilot
   type=choice
   options=big entry | smaller set
   answer=
   -->
"""


def one_question(body: str) -> str:
    return ("# P\n\nStatus: draft\n\n## Open questions\n\n"
            + body + "\n")


class TestExtraction(unittest.TestCase):
    def test_choice_toggle_text_records(self):
        doc = plan_parser.parse_plan(CHOICE_PLAN)
        self.assertEqual(doc["sentinel_errors"], [])
        qs = {q["id"]: q for q in doc["questions"]}
        self.assertEqual(set(qs),
                         {"q-store", "q-cleanup", "q-kind-name"})
        store = qs["q-store"]
        self.assertEqual(store["type"], "choice")
        self.assertEqual(
            store["options"],
            ["messages store", "registry", "a new store"])
        self.assertEqual(store["recommended"], "messages store")
        self.assertEqual(store["answer"], "")
        self.assertFalse(store["checked"])
        self.assertEqual(store["item_kind"], "task")
        self.assertEqual(store["text"],
                         "Which store holds the index?")
        cleanup = qs["q-cleanup"]
        self.assertEqual(cleanup["type"], "toggle")
        self.assertEqual(cleanup["labels"],
                         ["Enabled", "Disabled"])
        kind = qs["q-kind-name"]
        self.assertEqual(kind["type"], "text")
        self.assertIsNone(kind["options"])
        self.assertIsNone(kind["recommended"])

    def test_plain_question_stays_plain(self):
        doc = plan_parser.parse_plan(CHOICE_PLAN)
        texts = [q["text"] for q in doc["open_questions"]]
        self.assertEqual(len(texts), 4)
        self.assertTrue(any("plain question" in t
                            for t in texts))

    def test_sentinel_lines_never_pollute_item_text(self):
        doc = plan_parser.parse_plan(CHOICE_PLAN)
        for item in doc["open_questions"]:
            self.assertNotIn("wb-question", item["text"])
            self.assertNotIn("answer=", item["text"])
            self.assertNotIn("id=q-", item["text"])

    def test_answered_question_record(self):
        doc = plan_parser.parse_plan(ANSWERED_PLAN)
        self.assertEqual(doc["sentinel_errors"], [])
        (q,) = doc["questions"]
        self.assertEqual(q["answer"], "registry")
        self.assertTrue(q["checked"])

    def test_legacy_numbered_items_attach(self):
        doc = plan_parser.parse_plan(LEGACY_PLAN)
        self.assertEqual(doc["sentinel_errors"], [])
        qs = {q["id"]: q for q in doc["questions"]}
        self.assertEqual(set(qs), {"q-kind", "q-pilot"})
        self.assertEqual(qs["q-kind"]["item_kind"], "numbered")
        self.assertEqual(qs["q-kind"]["recommended"],
                         "explainer")
        self.assertIn("filter by", qs["q-kind"]["detail"])
        self.assertFalse(qs["q-kind"]["checked"])

    def test_recommended_not_an_option_degrades(self):
        doc = plan_parser.parse_plan(one_question(
            "- [ ] Which port?\n"
            "  <!-- wb-question\n"
            "  id=q-port\n"
            "  type=choice\n"
            "  options=8792\n"
            "  recommended=8793\n"
            "  answer=\n"
            "  -->\n"))
        self.assertEqual(doc["questions"], [])
        reasons = [e["reason"] for e in doc["sentinel_errors"]]
        self.assertTrue(any("at least two" in r
                            for r in reasons), reasons)
        self.assertTrue(any("not one of the options" in r
                            for r in reasons), reasons)

    def test_checked_answer_disagreement_degrades(self):
        doc = plan_parser.parse_plan(one_question(
            "- [x] Decided already?\n"
            "  <!-- wb-question\n"
            "  id=q-decided\n"
            "  type=choice\n"
            "  options=yes | no\n"
            "  answer=\n"
            "  -->\n"))
        self.assertEqual(doc["questions"], [])
        self.assertTrue(any(
            "disagree" in e["reason"]
            for e in doc["sentinel_errors"]))

    def test_stray_and_unterminated_sentinels(self):
        doc = plan_parser.parse_plan(one_question(
            "  <!-- wb-question\n"
            "  id=q-stray\n"
            "  type=text\n"
            "  answer=\n"
            "  -->\n"
            "- [ ] Real question?\n"))
        self.assertEqual(doc["questions"], [])
        self.assertTrue(any(
            "stray" in e["reason"]
            for e in doc["sentinel_errors"]))
        doc = plan_parser.parse_plan(one_question(
            "- [ ] Never closed?\n"
            "  <!-- wb-question\n"
            "  id=q-open\n"
            "  type=text\n"
            "  answer=\n"))
        self.assertEqual(doc["questions"], [])
        self.assertTrue(any(
            "unterminated" in e["reason"]
            for e in doc["sentinel_errors"]))

    def test_fenced_sentinel_is_an_example(self):
        doc = plan_parser.parse_plan(one_question(
            "- [ ] Real question?\n\n"
            "```text\n"
            "- [ ] Example question?\n"
            "  <!-- wb-question\n"
            "  id=q-example\n"
            "  type=text\n"
            "  answer=\n"
            "  -->\n"
            "```\n"))
        self.assertEqual(doc["questions"], [])
        self.assertEqual(doc["sentinel_errors"], [])

    def test_duplicate_id_degrades_the_second(self):
        doc = plan_parser.parse_plan(one_question(
            "- [ ] One?\n"
            "  <!-- wb-question\n"
            "  id=q-same\n"
            "  type=text\n"
            "  answer=\n"
            "  -->\n"
            "- [ ] Two?\n"
            "  <!-- wb-question\n"
            "  id=q-same\n"
            "  type=text\n"
            "  answer=\n"
            "  -->\n"))
        self.assertEqual([q["id"] for q in doc["questions"]],
                         ["q-same"])
        self.assertTrue(any(
            "duplicate" in e["reason"]
            for e in doc["sentinel_errors"]))

    def test_type_field_rules(self):
        doc = plan_parser.parse_plan(one_question(
            "- [ ] Mislabeled?\n"
            "  <!-- wb-question\n"
            "  id=q-bad\n"
            "  type=toggle\n"
            "  options=a | b\n"
            "  answer=\n"
            "  -->\n"))
        self.assertEqual(doc["questions"], [])
        reasons = [e["reason"] for e in doc["sentinel_errors"]]
        self.assertTrue(any("labels" in r for r in reasons),
                        reasons)
        self.assertTrue(any("options" in r for r in reasons),
                        reasons)

    def test_sentinel_plan_round_trip_is_byte_exact(self):
        for text in (CHOICE_PLAN, ANSWERED_PLAN, LEGACY_PLAN):
            doc = plan_parser.parse_plan(text)
            rebuilt = plan_parser.reconstruct(doc)
            self.assertEqual(
                rebuilt.rstrip("\n"), text.rstrip("\n"))

    def test_summary_carries_questions(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "2026-10-25-x.md"
            p.write_text(CHOICE_PLAN, encoding="utf-8")
            (summary,) = plan_parser.list_plans(td)
        self.assertEqual(
            [q["id"] for q in summary["questions"]],
            ["q-store", "q-cleanup", "q-kind-name"])


MIXED_PLAN = """# A mixed questions section

Status: draft

## Open questions for the owner

Two things are still open; one is a style call.

- [ ] Which store holds the index?
  <!-- wb-question
  id=q-store
  type=choice
  options=messages store | registry
  answer=
  -->
- [ ] A plain question with no sentinel?
- [ ] A broken one?
  <!-- wb-question
  id=q-broken
  type=choice
  options=only one
  answer=
  -->

```text
- [ ] An example question, fenced off.
  <!-- wb-question
  id=q-example
  type=text
  answer=
  -->
```

## Critical files

- `lib/plans/parser.py`
"""

TWO_SECTIONS_PLAN = """# Two candidate sections

Status: draft

## Open questions for the owner

- [ ] First section question?
  <!-- wb-question
  id=q-first
  type=text
  answer=
  -->

## Open questions

- [ ] Second section question?
  <!-- wb-question
  id=q-second
  type=text
  answer=
  -->
"""


def section_of(doc, heading):
    return next(s for s in doc["sections"]
                if s["heading"] == heading)


def leftover_text(section):
    return "\n".join(
        b.get("text") or b.get("source") or ""
        for b in section["leftover_blocks"])


class TestUnifiedGate(unittest.TestCase):
    """One heading rule (the parser's predicate) drives
    the section flag and both extractions; the first
    matching section is the plan's questions section."""

    def test_exact_heading_flags(self):
        doc = plan_parser.parse_plan(CHOICE_PLAN)
        sec = section_of(doc, "Open questions")
        self.assertTrue(sec["is_open_questions"])

    def test_suffixed_heading_flags_and_extracts(self):
        doc = plan_parser.parse_plan(LEGACY_PLAN)
        sec = section_of(doc, "Open questions for the owner")
        self.assertTrue(sec["is_open_questions"])
        self.assertEqual(
            {q["id"] for q in doc["questions"]},
            {"q-kind", "q-pilot"})

    def test_case_variants_flag(self):
        for heading in ("OPEN QUESTIONS",
                        "open Questions for the Owner"):
            doc = plan_parser.parse_plan(
                "# P\n\nStatus: draft\n\n"
                f"## {heading}\n\n"
                "- [ ] Asked?\n"
                "  <!-- wb-question\n"
                "  id=q-asked\n"
                "  type=text\n"
                "  answer=\n"
                "  -->\n")
            self.assertTrue(
                doc["sections"][0]["is_open_questions"],
                heading)
            self.assertEqual(
                [q["id"] for q in doc["questions"]],
                ["q-asked"], heading)

    def test_words_later_in_the_heading_do_not_match(self):
        for heading in ("Plan open questions",
                        "Reopen questions",
                        "Questions"):
            doc = plan_parser.parse_plan(
                "# P\n\nStatus: draft\n\n"
                f"## {heading}\n\n"
                "- [ ] Asked?\n"
                "  <!-- wb-question\n"
                "  id=q-asked\n"
                "  type=text\n"
                "  answer=\n"
                "  -->\n")
            self.assertFalse(
                doc["sections"][0]["is_open_questions"],
                heading)
            self.assertEqual(doc["questions"], [], heading)
            self.assertNotIn("leftover_blocks",
                             doc["sections"][0])

    def test_task_list_extraction_uses_the_same_rule(self):
        doc = plan_parser.parse_plan(
            "# P\n\nStatus: draft\n\n"
            "## Open questions for the owner\n\n"
            "- [ ] A checkbox question?\n")
        self.assertEqual(
            [q["text"] for q in doc["open_questions"]],
            ["A checkbox question?"])

    def test_first_match_only(self):
        doc = plan_parser.parse_plan(TWO_SECTIONS_PLAN)
        first = section_of(doc, "Open questions for the owner")
        second = section_of(doc, "Open questions")
        self.assertTrue(first["is_open_questions"])
        self.assertFalse(second["is_open_questions"])
        self.assertEqual(
            [q["id"] for q in doc["questions"]], ["q-first"])
        self.assertEqual(doc["sentinel_errors"], [])
        self.assertNotIn("leftover_blocks", second)


class TestLeftoverBlocks(unittest.TestCase):
    """The flagged section's leftover blocks carry every
    line no valid question consumed, so the reader can
    render them in place of the section's blocks when
    the Questions card shows — each question once, and
    nothing else dropped."""

    def test_covered_questions_leave_no_trace(self):
        doc = plan_parser.parse_plan(LEGACY_PLAN)
        sec = section_of(doc, "Open questions for the owner")
        text = leftover_text(sec)
        self.assertNotIn("Kind name", text)
        self.assertNotIn("Pilot scope", text)
        self.assertNotIn("wb-question", text)

    def test_plain_item_stays_in_the_leftover(self):
        doc = plan_parser.parse_plan(CHOICE_PLAN)
        sec = section_of(doc, "Open questions")
        text = leftover_text(sec)
        self.assertIn("A plain question with no sentinel?",
                      text)
        self.assertNotIn("Which store holds the index?",
                         text)
        self.assertNotIn("Nightly cleanup", text)
        self.assertNotIn("What name should", text)

    def test_mixed_section_keeps_prose_plain_broken_fenced(
            self):
        doc = plan_parser.parse_plan(MIXED_PLAN)
        sec = section_of(doc, "Open questions for the owner")
        text = leftover_text(sec)
        # the intro prose survives
        self.assertIn("Two things are still open", text)
        # the valid question is covered, not leftover
        self.assertNotIn("Which store holds the index?",
                         text)
        # the sentinel-less item renders as plain markdown
        self.assertIn("A plain question with no sentinel?",
                      text)
        # the malformed sentinel's item stays plain too
        self.assertIn("A broken one?", text)
        self.assertTrue(any(
            "at least two" in e["reason"]
            for e in doc["sentinel_errors"]))
        # the fenced example stays, as a code block
        self.assertTrue(any(
            b["type"] == "code" and "q-example" in b["raw"]
            for b in sec["leftover_blocks"]))
        self.assertEqual(
            [q["id"] for q in doc["questions"]], ["q-store"])

    def test_leftover_only_on_the_flagged_section(self):
        doc = plan_parser.parse_plan(MIXED_PLAN)
        for sec in doc["sections"]:
            if sec["heading"] == "Critical files":
                self.assertNotIn("leftover_blocks", sec)

    def test_round_trip_stays_byte_exact(self):
        for text in (MIXED_PLAN, TWO_SECTIONS_PLAN):
            doc = plan_parser.parse_plan(text)
            self.assertEqual(
                plan_parser.reconstruct(doc).rstrip("\n"),
                text.rstrip("\n"))


class TestApplyAnswers(unittest.TestCase):
    def test_resolve_is_byte_exact_elsewhere(self):
        out = plan_parser.apply_answers(
            CHOICE_PLAN,
            {"q-store": "registry",
             "q-cleanup": "Disabled",
             "q-kind-name": "explainer"})
        expected = CHOICE_PLAN.replace(
            "- [ ] Which store holds the index?",
            "- [x] Which store holds the index?").replace(
            "  answer=\n  -->\n- [ ] Nightly cleanup",
            "  answer=registry\n  -->\n- [ ] Nightly cleanup"
            ).replace(
            "- [ ] Nightly cleanup of the message store",
            "- [x] Nightly cleanup of the message store"
            ).replace(
            "  answer=\n  -->\n- [ ] What name",
            "  answer=Disabled\n  -->\n- [ ] What name"
            ).replace(
            "- [ ] What name should the new entry kind carry?",
            "- [x] What name should the new entry kind carry?"
            ).replace(
            "  id=q-kind-name\n  type=text\n  answer=\n",
            "  id=q-kind-name\n  type=text\n"
            "  answer=explainer\n")
        self.assertEqual(out, expected)
        doc = plan_parser.parse_plan(out)
        self.assertEqual(doc["sentinel_errors"], [])
        answers = {q["id"]: q["answer"]
                   for q in doc["questions"]}
        self.assertEqual(answers, {
            "q-store": "registry",
            "q-cleanup": "Disabled",
            "q-kind-name": "explainer"})

    def test_subset_answers_leave_the_rest_untouched(self):
        out = plan_parser.apply_answers(
            CHOICE_PLAN, {"q-cleanup": "Enabled"})
        self.assertIn("- [ ] Which store holds the index?",
                      out)
        self.assertIn(
            "- [x] Nightly cleanup of the message store", out)
        self.assertEqual(out.count("answer=Enabled"), 1)

    def test_legacy_item_gets_an_answer_but_no_box(self):
        out = plan_parser.apply_answers(
            LEGACY_PLAN, {"q-kind": "ruling"})
        self.assertIn("answer=ruling", out)
        self.assertNotIn("[x]", out)
        doc = plan_parser.parse_plan(out)
        (q,) = [q for q in doc["questions"]
                if q["id"] == "q-kind"]
        self.assertEqual(q["answer"], "ruling")
        self.assertTrue(q["checked"])

    def test_reanswer_replaces_the_recorded_answer(self):
        out = plan_parser.apply_answers(
            ANSWERED_PLAN, {"q-store": "messages store"})
        self.assertIn("answer=messages store", out)
        self.assertIn(
            "- [x] Which store holds the index?", out)

    def test_unknown_id_refused(self):
        with self.assertRaises(ValueError):
            plan_parser.apply_answers(
                CHOICE_PLAN, {"q-nope": "x"})

    def test_answer_must_fit_the_type(self):
        with self.assertRaises(ValueError):
            plan_parser.apply_answers(
                CHOICE_PLAN, {"q-store": "a third store"})
        with self.assertRaises(ValueError):
            plan_parser.apply_answers(
                CHOICE_PLAN, {"q-cleanup": "Maybe"})
        with self.assertRaises(ValueError):
            plan_parser.apply_answers(
                CHOICE_PLAN, {"q-kind-name": "two\nlines"})
        with self.assertRaises(ValueError):
            plan_parser.apply_answers(
                CHOICE_PLAN, {"q-store": ""})
        with self.assertRaises(ValueError):
            plan_parser.apply_answers(CHOICE_PLAN, {})


if __name__ == "__main__":
    unittest.main()
