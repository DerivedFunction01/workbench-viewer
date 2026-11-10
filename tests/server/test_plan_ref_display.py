"""plan_ref display hygiene tests (home-hygiene plan,
Step 5): an absolute filesystem path stored as an
entry's plan_ref is never served raw — the feed replaces
it with the path's basename. Relative refs pass through
unchanged, and the stored value is not rewritten."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "server"))

from lib import registry as reg  # noqa: E402
from lib.manifest import load_manifest  # noqa: E402

import feeds  # noqa: E402


def make_project(root: Path):
    root.mkdir(parents=True)
    (root / "workbench").mkdir()
    (root / ".plans").mkdir()
    (root / "workbench.yaml").write_text(
        "name: Fixture\nregistry: workbench/registry.db\n"
        "plans: .plans\nmockups: workbench/entries\n"
        "archive: workbench/archive\n", encoding="utf-8")
    db = root / "workbench" / "registry.db"
    reg.init_registry(db)
    layout = (root / "workbench" / "entries",
              root / "workbench" / "archive")
    reg.add_entry(
        db, layout, "abs-ref", title="Absolute ref",
        kind="artifact",
        plan_ref="/elsewhere/deep/secret-plan-name.md")
    (Path(reg.get_entry(db, "abs-ref")["entry_dir"])
     / "mock.html").write_text("x", encoding="utf-8")
    reg.add_entry(
        db, layout, "rel-ref", title="Relative ref",
        kind="artifact", plan_ref="some-plan")
    (Path(reg.get_entry(db, "rel-ref")["entry_dir"])
     / "mock.html").write_text("x", encoding="utf-8")
    manifest = load_manifest(root / "workbench.yaml")
    return SimpleNamespace(slug="fixture", name="Fixture",
                           manifest=manifest), db


class PlanRefDisplay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project, self.db = make_project(
            Path(self.tmp.name) / "proj")

    def tearDown(self):
        self.tmp.cleanup()

    def test_absolute_plan_ref_serves_basename_only(self):
        feed = feeds.entries_feed(self.project,
                                  archived=False)
        self.assertTrue(feed["available"])
        by_id = {e["id"]: e for e in feed["entries"]}
        served = by_id["abs-ref"]["plan_ref"]
        self.assertEqual(served, "secret-plan-name.md")
        self.assertFalse(Path(served).is_absolute())
        # the relative ref passes through unchanged
        self.assertEqual(by_id["rel-ref"]["plan_ref"],
                         "some-plan")
        # the stored value is untouched by the display fix
        stored = reg.get_entry(self.db, "abs-ref")
        self.assertEqual(
            stored["plan_ref"],
            "/elsewhere/deep/secret-plan-name.md")


if __name__ == "__main__":
    unittest.main()
