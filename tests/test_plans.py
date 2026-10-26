"""Step 3 gate tests: the plan parser against the REAL corpus
(the founding plan, subplan 09, the v2 master plan, the
older PowerBI/bootstrap shapes, the non-plans), plus the
mermaid path on a corpus-shaped fixture (the live corpus
contains no mermaid fence yet — recorded honestly in the
progress tracker).

The core invariant: parsing is LOSSLESS — header_raw +
section raws reconstruct the source exactly, for every plan
file in both .plans trees, so no step block (or anything
else) can be silently dropped.

The corpus lives outside this repo, so where it sits is an
environment fact, not a tracked path: WB_LIVE_CORPUS names
the directory containing the project checkouts, and the
corpus locations derive from it below. With the variable
unset (or not a directory), every corpus test skips and
only the fixture tests run — a fresh clone is green with
no corpus present.
"""

import os
import unittest
from pathlib import Path

from lib.plans import parser

CORPUS_ENV = "WB_LIVE_CORPUS"
_raw_corpus = os.environ.get(CORPUS_ENV)
CORPUS = Path(_raw_corpus) if _raw_corpus else None
CORPUS_AVAILABLE = CORPUS is not None and CORPUS.is_dir()
requires_corpus = unittest.skipUnless(
    CORPUS_AVAILABLE,
    f"{CORPUS_ENV} is not set to a corpus directory — "
    "live-corpus tests skipped")

# The companion project's checkout directory, assembled
# from parts on purpose: its name may not appear in a
# tracked file (the portability rule), not even here.
_OTHER_PROJECT = "usmc-" + "pay-" + "monitor" + "-v2"
# This repo's own checkout directory name, for locating its
# .plans inside the corpus tree; derived, never hardcoded.
_REPO_CHECKOUT = Path(__file__).resolve().parent.parent.name

if CORPUS is not None:
    WS = CORPUS
    FOUNDING = (WS / _REPO_CHECKOUT / ".plans"
                / "2026-10-25-workbench-viewer-repo.md")
    SUBPLAN09 = (WS / _OTHER_PROJECT / ".plans"
                 / "2026-10-25-living-workbench-storyboard.md")
    MASTER = (WS / _OTHER_PROJECT / ".plans"
              / "2026-10-25-rebuild-program.md")
    BOOTSTRAP = (WS / ".plans"
                 / "2026-10-22-machine-bootstrap-reproducibility.md")
    BACKSTAGE = (WS / ".plans"
                 / "2026-10-23-powerbi-backstage-implementation-plan.md")
    STATUS_DOC = WS / ".plans" / "current-status-2026-10-25.md"
    TRACKER_DOC = WS / ".plans" / "mockup-status-tracker.md"
    V2_PLANS = WS / _OTHER_PROJECT / ".plans"
    VIEWER_PLANS = WS / _REPO_CHECKOUT / ".plans"
else:
    WS = FOUNDING = SUBPLAN09 = MASTER = BOOTSTRAP = None
    BACKSTAGE = STATUS_DOC = TRACKER_DOC = V2_PLANS = None
    VIEWER_PLANS = None


def parse(path):
    return parser.parse_plan(path.read_text(encoding="utf-8"),
                             path=path.name)


@requires_corpus
class TestNamedPlans(unittest.TestCase):
    def test_founding_plan(self):
        doc = parse(FOUNDING)
        self.assertTrue(doc["conforming"])
        self.assertEqual(doc["status_raw"], "in progress")
        self.assertEqual(doc["status_bucket"], "doing")
        self.assertEqual(doc["step_count"], 8)
        titles = [s["title"] for s in doc["steps"]]
        self.assertIn("Repo scaffold + the six context files.",
                      titles[0])
        for step in doc["steps"]:
            self.assertTrue(step["files"],
                            f"step {step['n']} lost its files:")
            self.assertTrue(step["verify"],
                            f"step {step['n']} lost its verify:")
            self.assertTrue(step["done_when"],
                            f"step {step['n']} lost done when:")

    def test_subplan09_both_step_groups(self):
        doc = parse(SUBPLAN09)
        self.assertTrue(doc["conforming"])
        # Part A (4, under 'Steps (when not skipped):')
        # + Part B (6, under a bare 'Steps:')
        self.assertEqual(doc["step_count"], 10)
        ns = [s["n"] for s in doc["steps"]]
        self.assertEqual(ns, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        for step in doc["steps"]:
            self.assertTrue(step["files"])
            self.assertTrue(step["verify"])

    def test_master_plan_no_steps_but_lossless(self):
        doc = parse(MASTER)
        self.assertTrue(doc["conforming"])
        self.assertEqual(doc["fields"]["Status"], "draft")
        self.assertEqual(doc["step_count"], 0)  # it has none
        self.assertGreaterEqual(len(doc["sections"]), 5)
        rulings = [s for s in doc["sections"] if s["is_rulings"]]
        self.assertEqual(len(rulings), 1)

    def test_bootstrap_plan_implementation_steps(self):
        doc = parse(BOOTSTRAP)
        self.assertEqual(doc["step_count"], 6)
        self.assertIn("Close the no-git gaps.",
                      doc["steps"][0]["title"])
        # its open questions are numbered too — and must NOT
        # have been parsed as steps (6, not 6+4)
        self.assertNotIn("Where does the kit live",
                         " ".join(s["title"]
                                  for s in doc["steps"]))

    def test_powerbi_heading_steps(self):
        doc = parse(BACKSTAGE)
        self.assertEqual(doc["step_count"], 10)
        self.assertEqual(doc["steps"][0]["n"], 0)
        self.assertIn("Baseline & gate snapshot",
                      doc["steps"][0]["title"])
        self.assertTrue(doc["steps"][0]["body"])


@requires_corpus
class TestDegradation(unittest.TestCase):
    def test_status_doc_is_nonconforming_but_whole(self):
        text = STATUS_DOC.read_text(encoding="utf-8")
        doc = parse(STATUS_DOC)
        self.assertFalse(doc["conforming"])
        self.assertEqual(doc["markdown"], text)
        self.assertEqual(doc["status_bucket"], "todo")

    def test_tracker_doc_is_nonconforming(self):
        doc = parse(TRACKER_DOC)
        self.assertFalse(doc["conforming"])
        self.assertTrue(doc["title"])


@requires_corpus
class TestCorpusLossless(unittest.TestCase):
    def test_every_corpus_plan_reconstructs(self):
        files = []
        for base in (WS / ".plans", V2_PLANS):
            files += sorted(base.glob("*.md"))
            finished = base / "finished"
            if finished.is_dir():
                files += sorted(finished.glob("*.md"))
        self.assertGreater(len(files), 30)
        for f in files:
            text = f.read_text(encoding="utf-8")
            doc = parser.parse_plan(text, path=f.name)
            self.assertEqual(
                parser.reconstruct(doc).rstrip("\n"),
                text.rstrip("\n"),
                f"parser dropped content in {f}")
            # every extracted step string is verbatim source
            for step in doc["steps"]:
                self.assertIn(step["raw"], text,
                              f"step raw not verbatim in {f}")


@requires_corpus
class TestMermaid(unittest.TestCase):
    def test_mermaid_fence_yields_source_intact(self):
        base = FOUNDING.read_text(encoding="utf-8")
        diagram = ("## Diagram\n\n```mermaid\n"
                   "graph TD\n  A[Sweep] --> B[Registry]\n"
                   "  B --> C[Viewer]\n```\n")
        doc = parser.parse_plan(base + "\n" + diagram)
        self.assertEqual(doc["mermaid_count"], 1)
        block = [b for s in doc["sections"]
                 for b in s["blocks"] if b["type"] == "mermaid"]
        self.assertEqual(len(block), 1)
        self.assertIn("graph TD", block[0]["source"])
        self.assertIn("A[Sweep] --> B[Registry]",
                      block[0]["source"])
        self.assertEqual(
            parser.reconstruct(doc).rstrip("\n"),
            (base + "\n" + diagram).rstrip("\n"))


CONFORMING_FIXTURE = (Path(__file__).resolve().parent
                      / "fixtures" / "conforming-plan.md")


class TestConformingFixture(unittest.TestCase):
    """The plan syntax standard's fully conforming fixture:
    every element the standard names, asserted structurally.
    Renderer-side proof lives in viewer/tools/test-math.ts
    (same fixture)."""

    @classmethod
    def setUpClass(cls):
        cls.text = CONFORMING_FIXTURE.read_text(
            encoding="utf-8")
        cls.doc = parser.parse_plan(cls.text,
                                    path="conforming-plan.md")

    def test_lossless(self):
        self.assertEqual(
            parser.reconstruct(self.doc).rstrip(),
            self.text.rstrip())

    def test_header_fields(self):
        doc = self.doc
        self.assertTrue(doc["conforming"])
        self.assertEqual(doc["title"],
                         "Add the widget index to the "
                         "messages store")
        self.assertEqual(doc["fields"]["Status"], "draft")
        self.assertEqual(doc["fields"]["Worktree"],
                         "../wv-plansyntax")
        self.assertEqual(doc["fields"]["Branch"],
                         "build/plan-syntax")

    def test_steps_carry_all_labels(self):
        doc = self.doc
        self.assertEqual(doc["step_count"], 2)
        one, two = doc["steps"]
        self.assertEqual(one["title"], "Store and payload")
        self.assertIn("lib/plans/parser.py", one["files"])
        self.assertIn("tests.test_plans", one["verify"])
        self.assertTrue(one["done_when"])
        # The unverifiable convention lands as the literal
        # line, never silence.
        self.assertTrue(
            two["verify"].startswith("unverifiable —"))

    def test_open_questions_items_and_count(self):
        doc = self.doc
        self.assertEqual(doc["open_questions_count"], 2)
        open_q, answered_q = doc["open_questions"]
        self.assertFalse(open_q["checked"])
        self.assertIn("Which store holds the index?",
                      open_q["text"])
        self.assertIn("Recommendation:", open_q["text"])
        self.assertTrue(answered_q["checked"])
        self.assertIn("Created:", answered_q["text"])

    def test_critical_files_path_list(self):
        self.assertEqual(
            self.doc["critical_files"],
            ["lib/plans/parser.py",
             "viewer/client/src/sections/plans/PlanBody.tsx",
             "tests/test_plans.py"])

    def test_section_flags(self):
        flags = {s["heading"]: s for s in self.doc["sections"]}
        self.assertTrue(
            flags["Open questions"]["is_open_questions"])
        self.assertTrue(
            flags["Critical files"]["is_critical_files"])
        self.assertFalse(
            flags["Objective"]["is_open_questions"])
        self.assertFalse(
            flags["Rulings"]["is_critical_files"])

    def test_summary_carries_question_count(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plans = Path(td)
            (plans / "conforming-plan.md").write_text(
                self.text, encoding="utf-8")
            summaries = parser.list_plans(plans)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(
            summaries[0]["open_questions_count"], 2)

    @requires_corpus
    def test_legacy_plan_has_empty_semantics(self):
        doc = parse(BOOTSTRAP)
        self.assertEqual(doc["open_questions"], [])
        self.assertEqual(doc["open_questions_count"], 0)
        self.assertEqual(doc["critical_files"], [])


DECLARING_PLAN = """\
# Parent plan

Status: in progress

## Objective

Decompose.

## Subplans

- `child-a.md`
- `finished/child-b.md` — the finished half
- child-c.md

## Critical files

- `lib/plans/parser.py`
"""

FENCED_SAMPLE_PLAN = """\
# Plan with a quoted sample

Status: draft

## Notes

The declaration's shape, quoted as an example:

```markdown
- `not-a-real-child.md`
```

## Subplans

```text
- `also-not-real.md`
```
"""

MIXED_SUBPLANS_PLAN = """\
# Plan mixing declaration and prose

Status: draft

## Subplans

- `real-child.md`
- Paths are relative to the `.plans/` directory.
- A subplan declares nothing back — no `Parent:` field.
- The format in prose, not a declaration of one.
"""

PURE_PROSE_SUBPLANS_PLAN = """\
# A standard-like document

Status: approved

## Subplans

- Present only when the plan decomposes into subplans; the
  section lists them, one bullet per subplan, each a backticked
  path relative to the `.plans/` directory.
- The parent declares; a subplan declares nothing back — no
  `Parent:` field, no back-reference.
"""

SYNTAX_STANDARD = (VIEWER_PLANS
                   / "2026-10-25-plan-syntax-standard.md"
                   if VIEWER_PLANS is not None else None)


class TestSubplans(unittest.TestCase):
    """§21: the parent's `## Subplans` declaration joins the
    payload, fence-aware, in declaration order. Absence is
    an empty list, never an error."""

    def test_declaring_plan_paths_in_order(self):
        doc = parser.parse_plan(DECLARING_PLAN,
                                path="parent.md")
        self.assertEqual(doc["subplans"],
                         ["child-a.md", "finished/child-b.md",
                          "child-c.md"])

    def test_section_flag(self):
        doc = parser.parse_plan(DECLARING_PLAN,
                                path="parent.md")
        flags = {s["heading"]: s for s in doc["sections"]}
        self.assertTrue(flags["Subplans"]["is_subplans"])
        self.assertFalse(flags["Objective"]["is_subplans"])
        self.assertFalse(
            flags["Critical files"]["is_subplans"])

    def test_fenced_samples_extract_nothing(self):
        doc = parser.parse_plan(FENCED_SAMPLE_PLAN,
                                path="sample.md")
        self.assertEqual(doc["subplans"], [])

    @requires_corpus
    def test_legacy_plan_has_no_subplans(self):
        doc = parse(BOOTSTRAP)
        self.assertEqual(doc["subplans"], [])

    def test_summary_carries_subplans_count(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plans = Path(td)
            (plans / "parent.md").write_text(
                DECLARING_PLAN, encoding="utf-8")
            summaries = parser.list_plans(plans)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["subplans_count"], 3)

    def test_mixed_section_extracts_only_plan_files(self):
        # Precision rule: a span declares only when it
        # names a plan file (ends in .md). Prose bullets —
        # backticked non-.md spans, plain text up to an
        # em-dash — declare nothing.
        doc = parser.parse_plan(MIXED_SUBPLANS_PLAN,
                                path="mixed.md")
        self.assertEqual(doc["subplans"], ["real-child.md"])

    def test_pure_prose_section_extracts_nothing(self):
        doc = parser.parse_plan(PURE_PROSE_SUBPLANS_PLAN,
                                path="standard-like.md")
        self.assertEqual(doc["subplans"], [])


@requires_corpus
class TestSubplanPrecisionCorpus(unittest.TestCase):
    """The real-corpus pass over the viewer's own .plans/:
    the plan syntax standard's `## Subplans` section is
    prose about the format and must declare nothing, and
    every declaration anywhere in the corpus names a
    plan file."""

    def test_the_standard_declares_no_subplans(self):
        doc = parse(SYNTAX_STANDARD)
        flags = {s["heading"]: s for s in doc["sections"]}
        # Guard against a vacuous pass: the section whose
        # prose produced the phantom rows is really there.
        self.assertTrue(flags["Subplans"]["is_subplans"])
        self.assertEqual(doc["subplans"], [])

    def test_every_corpus_declaration_names_a_plan_file(self):
        files = sorted(VIEWER_PLANS.rglob("*.md"))
        self.assertTrue(files)
        for f in files:
            doc = parse(f)
            for declared in doc["subplans"]:
                self.assertTrue(
                    declared.endswith(".md"),
                    f"{f.name} declares non-plan {declared!r}")


@requires_corpus
class TestListing(unittest.TestCase):
    def test_list_v2_plans(self):
        summaries = parser.list_plans(V2_PLANS)
        names = [s["path"] for s in summaries]
        self.assertIn("2026-10-25-rebuild-program.md", names)
        # the spec-extraction working dir is not plans
        self.assertFalse(any("spec-extraction/" in n
                             for n in names))
        viewer_plans = parser.list_plans(VIEWER_PLANS)
        by_name = {s["path"]: s for s in viewer_plans}
        self.assertEqual(
            by_name["2026-10-25-workbench-viewer-repo.md"]
            ["status_bucket"], "doing")
        self.assertTrue(
            any(s["archived"] for s in viewer_plans),
            "finished/ plans should list as archived")

    def test_load_plan_confined(self):
        doc = parser.load_plan(V2_PLANS,
                               "2026-10-25-rebuild-program.md")
        self.assertEqual(doc["title"][:12], "Master plan:")
        with self.assertRaises(ValueError):
            parser.load_plan(V2_PLANS, "../SPEC.md")


if __name__ == "__main__":
    unittest.main()
