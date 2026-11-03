"""Re-location (spec §12, annotation plan Step 3): the
pure algorithm over the SAME fixtures the client mirror
runs (tests/fixtures/relocation.json), plus the plan
scoping + pickup context against real fixture projects.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from lib import annotations as ann
from lib import registry as reg
from lib.manifest import Manifest

FIXTURES = Path(__file__).parent / "fixtures" \
    / "relocation.json"

PLAN = """# Fixture Plan

Status: in progress
Created: 2026-10-25

## Steps

1. **Compare against the checkpoint.** First compare the
   result against the checkpoint recorded at the previous
   seal. Anything that moved since the checkpoint is
   listed, not silently carried into the seal. Only when
   the list is empty does the step close.
   files: lib/seal.py
   verify: the comparison report prints
   done when: the step closes on an empty list

2. **Publish the report.** The report is published to the
   library.
   files: lib/report.py
   verify: the library lists the report
   done when: the report is live
"""

QUOTE = ("Anything that moved since the checkpoint is "
         "listed, not silently carried into the seal.")

TEXT_SELECTION = {
    "kind": "text",
    "component_id": "plans/step-1",
    "component_label": "Step 1",
    "section_heading": "Steps",
    "quote": QUOTE,
    "prefix": "seal. ",
    "suffix": " Only when",
}


class TestRelocateFixtures(unittest.TestCase):
    def test_shared_fixtures(self):
        data = json.loads(FIXTURES.read_text(
            encoding="utf-8"))
        self.assertGreaterEqual(len(data["cases"]), 8)
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                result = ann.relocate(case["source"],
                                      case["selection"])
                self.assertEqual(result["status"],
                                 case["expect"])
                if case["expect"] == "located":
                    start, end = result["span"]
                    matched = ann.normalize(
                        case["source"][start:end])
                    self.assertEqual(
                        matched,
                        ann.normalize(
                            case["selection"]["quote"]))
                else:
                    self.assertIsNone(result["span"])


class ContextCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-ann-"))
        self.root = self.tmp / "alpha"
        (self.root / ".plans").mkdir(parents=True)
        (self.root / "workbench" / "entries").mkdir(
            parents=True)
        (self.root / "workbench" / "archive").mkdir()
        self.plan_path = self.root / ".plans" / "plan.md"
        self.plan_path.write_text(PLAN, encoding="utf-8")
        self.db = self.root / "workbench" / "registry.db"
        reg.init_registry(self.db)
        self.manifest = Manifest(
            root=self.root, name="Alpha", slug="alpha",
            registry=self.db,
            plans=self.root / ".plans",
            mockups=self.root / "workbench" / "entries",
            archive=self.root / "workbench" / "archive")
        self.project = SimpleNamespace(
            manifest=self.manifest, slug="alpha",
            root=self.root)

    def message(self, selection, **kw):
        base = {"anchor_type": "text",
                "anchor_ref": "plan.md",
                "selection": selection}
        base.update(kw)
        return base


class TestTextContext(ContextCase):
    def test_located_with_step_and_excerpt(self):
        ctx = ann.resolve_context(
            self.project, self.message(dict(TEXT_SELECTION)))
        self.assertEqual(ctx["status"], "located")
        self.assertTrue(ctx["relocated"])
        self.assertFalse(ctx["component_missing"])
        self.assertEqual(ctx["step"], 1)
        self.assertEqual(ctx["section_heading"], "Steps")
        self.assertIn("Anything that moved", ctx["excerpt"])
        self.assertIn("Only when the list is empty",
                      ann.normalize(ctx["excerpt"]))

    def test_quote_edited_away_is_orphan(self):
        self.plan_path.write_text(
            PLAN.replace("Anything that moved since the "
                         "checkpoint is",
                         "Everything is carried forward "
                         "from the checkpoint, which is"),
            encoding="utf-8")
        ctx = ann.resolve_context(
            self.project, self.message(dict(TEXT_SELECTION)))
        self.assertEqual(ctx["status"], "orphan")
        self.assertFalse(ctx["relocated"])
        self.assertEqual(ctx["quote"], QUOTE)
        self.assertIsNone(ctx["excerpt"])

    def test_component_renamed_widens_and_locates(self):
        sel = dict(TEXT_SELECTION,
                   component_id="plans/step-9")
        ctx = ann.resolve_context(self.project,
                                  self.message(sel))
        self.assertEqual(ctx["status"], "located")
        self.assertTrue(ctx["component_missing"])
        self.assertEqual(ctx["step"], 1)

    def test_component_renamed_and_quote_gone_is_orphan(
            self):
        sel = dict(TEXT_SELECTION,
                   component_id="plans/step-9",
                   quote="No such sentence anywhere.")
        ctx = ann.resolve_context(self.project,
                                  self.message(sel))
        self.assertEqual(ctx["status"], "orphan")
        self.assertTrue(ctx["component_missing"])

    def test_missing_plan_is_target_missing(self):
        ctx = ann.resolve_context(
            self.project,
            self.message(dict(TEXT_SELECTION),
                         anchor_ref="nope.md"))
        self.assertEqual(ctx["status"], "target_missing")
        self.assertFalse(ctx["relocated"])

    def test_plain_message_has_no_context(self):
        self.assertIsNone(ann.resolve_context(
            self.project,
            {"anchor_type": "plan", "anchor_ref": "p.md",
             "selection": None}))


class TestComponentContext(ContextCase):
    def setUp(self):
        super().setUp()
        layout = (self.root / "workbench" / "entries",
                  self.root / "workbench" / "archive")
        reg.add_entry(self.db, layout, "bars-entry",
                      title="Bars")
        entry_dir = self.root / "workbench" / "entries" \
            / "bars-entry"
        (entry_dir / "mock.html").write_text(
            '<div data-anchor="summary/bars-by-year">'
            "chart</div>", encoding="utf-8")

    def component_message(self, selection):
        return {"anchor_type": "component",
                "anchor_ref": "bars-entry",
                "selection": selection}

    def test_present(self):
        sel = {"kind": "component",
               "component_id": "summary/bars-by-year",
               "component_label": "chart · bars-by-year",
               "entry_id": "bars-entry"}
        ctx = ann.resolve_context(
            self.project, self.component_message(sel))
        self.assertTrue(ctx["present"])
        self.assertEqual(ctx["entry_title"], "Bars")
        self.assertEqual(ctx["component_label"],
                         "chart · bars-by-year")

    def test_renamed_component_is_not_present(self):
        sel = {"kind": "component",
               "component_id": "summary/bars-renamed",
               "component_label": "chart · bars-renamed",
               "entry_id": "bars-entry"}
        ctx = ann.resolve_context(
            self.project, self.component_message(sel))
        self.assertFalse(ctx["present"])
        self.assertEqual(ctx["entry_title"], "Bars")
        # The label snapshot survives the rename.
        self.assertEqual(ctx["component_label"],
                         "chart · bars-renamed")

    def test_missing_entry_is_target_missing(self):
        sel = {"kind": "component",
               "component_id": "summary/bars-by-year",
               "component_label": "chart · bars-by-year",
               "entry_id": "ghost-entry"}
        ctx = ann.resolve_context(
            self.project, self.component_message(sel))
        self.assertEqual(ctx["status"], "target_missing")
        self.assertFalse(ctx["present"])


if __name__ == "__main__":
    unittest.main()
