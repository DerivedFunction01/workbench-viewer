"""Plan grouping (§21), feed level: the bundles feed must
carry each plan's `## Subplans` declaration so the client
can derive groups. The family below exercises the named
cases — declaring parent, finished child, missing child,
self-declaration, two-parent child — on a scratch .plans
tree. The derivation itself is client-side and pinned by
viewer/tools/test-grouping.ts over the same family."""

import tempfile
import unittest
from pathlib import Path

from lib.plans import bundles

PARENT = """\
# Parent plan

Status: in progress

## Subplans

- `child.md`
- `finished/fin-child.md`
- `gone.md`
- `parent.md`
"""

CHILD = """\
# Child plan

Status: in progress

## Subplans

- `grandchild.md`
"""

GRANDCHILD = """\
# Grandchild plan

Status: draft
"""

RIVAL = """\
# Rival parent

Status: draft

## Subplans

- `child.md`
"""

FIN_CHILD = """\
# Finished child

Status: complete
"""


def _write(root: Path, rel: str, text: str):
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class TestGroupingFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        plans = Path(cls._tmp.name)
        _write(plans, "parent.md", PARENT)
        _write(plans, "child.md", CHILD)
        _write(plans, "grandchild.md", GRANDCHILD)
        _write(plans, "rival.md", RIVAL)
        _write(plans, "finished/fin-child.md", FIN_CHILD)
        cls.feed = bundles.list_bundles(plans)
        cls.by_plan_path = {
            b["plan"]["path"]: b for b in cls.feed if b["plan"]
        }

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_declaring_parent_carries_declaration(self):
        plan = self.by_plan_path["parent.md"]["plan"]
        self.assertEqual(
            plan["subplans"],
            ["child.md", "finished/fin-child.md", "gone.md",
             "parent.md"])
        self.assertEqual(plan["subplans_count"], 4)

    def test_child_declares_its_own(self):
        plan = self.by_plan_path["child.md"]["plan"]
        self.assertEqual(plan["subplans"], ["grandchild.md"])

    def test_two_parents_declare_the_same_child(self):
        plan = self.by_plan_path["rival.md"]["plan"]
        self.assertEqual(plan["subplans"], ["child.md"])
        # the child exists once in the resolution set; the
        # client derivation nests it under the first
        # declaring parent in feed order
        self.assertIn("child.md", self.by_plan_path)

    def test_finished_child_resolves_with_its_path(self):
        bundle = self.by_plan_path["finished/fin-child.md"]
        self.assertTrue(bundle["archived"])
        self.assertEqual(bundle["plan"]["status_bucket"],
                         "done")

    def test_missing_child_is_in_no_resolution_slot(self):
        self.assertNotIn("gone.md", self.by_plan_path)

    def test_self_declaration_is_carried_faithfully(self):
        # extraction is faithful; ignoring the self-claim
        # is the derivation's job (grouping.ts)
        plan = self.by_plan_path["parent.md"]["plan"]
        self.assertIn("parent.md", plan["subplans"])


if __name__ == "__main__":
    unittest.main()
