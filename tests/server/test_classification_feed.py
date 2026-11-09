"""Classification feed tests (harness connector plan,
Step 4): the served read a venue-side consumer judges
escalations against — per project, every todo across
the ACTIVE bundles with its status and raw progress
fields, the opt-out derived explicitly, and the harness
progress derivation for the armed set. Fixtures are
built through the lib writer, so the todo files carry
the production front-matter shape."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "server"))

from lib import bundles as bundle_mod  # noqa: E402
from lib import registry as reg  # noqa: E402
from lib.manifest import load_manifest  # noqa: E402

import feeds  # noqa: E402


def make_project(root: Path):
    root.mkdir(parents=True)
    (root / "workbench").mkdir()
    (root / ".plans").mkdir()
    (root / "workbench.yaml").write_text(
        "name: Fixture\nregistry: workbench/registry.db\n"
        "plans: .plans\n", encoding="utf-8")
    reg.init_registry(root / "workbench" / "registry.db")
    manifest = load_manifest(root / "workbench.yaml")
    return SimpleNamespace(slug="fixture", name="Fixture",
                           manifest=manifest)


class ClassificationFeed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.project = make_project(self.root)
        self.plans = self.project.manifest.plans

    def tearDown(self):
        self.tmp.cleanup()

    def test_active_todos_with_progress_fields(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 plan=True)
        doing = bundle_mod.create_todo(
            self.plans, "work", "Armed work", status="doing")
        opted = bundle_mod.create_todo(
            self.plans, "work", "Opted out work",
            status="doing", no_progress=True)
        plain = bundle_mod.create_todo(
            self.plans, "work", "Plain queued work")
        feed = feeds.classification_feed(self.project)
        self.assertTrue(feed["available"])
        self.assertEqual(feed["slug"], "fixture")
        by_id = {t["id"]: t for t in feed["todos"]}
        self.assertEqual(set(by_id),
                         {doing["id"], opted["id"],
                          plain["id"]})
        armed = by_id[doing["id"]]
        self.assertEqual(armed["status"], "doing")
        self.assertEqual(armed["progress_check"], "15m")
        self.assertFalse(armed["opted_out"])
        self.assertIsNotNone(armed["progress_armed"])
        self.assertEqual(armed["bundle"],
                         doing["bundle"])
        out = by_id[opted["id"]]
        self.assertEqual(out["progress_check"], "off")
        self.assertTrue(out["opted_out"])
        self.assertIsNone(out["progress_armed"])
        queued = by_id[plain["id"]]
        self.assertEqual(queued["status"], "todo")
        self.assertIsNone(queued["progress_check"])
        self.assertFalse(queued["opted_out"])

    def test_progress_derivation_rides_for_armed(self):
        bundle_mod.create_bundle(self.plans, "work",
                                 plan=True)
        doing = bundle_mod.create_todo(
            self.plans, "work", "Armed work", status="doing",
            body="progress-checkpoint: "
                 "2026-11-09T00:00:00+00:00 — started\n")
        feed = feeds.classification_feed(self.project)
        armed = feed["progress"]["armed"]
        self.assertEqual(len(armed), 1)
        block = armed[0]
        self.assertEqual(block["id"], doing["id"])
        self.assertEqual(block["cadence"], "15m")
        self.assertEqual(block["interval_seconds"], 900.0)
        self.assertEqual(block["last_checkpoint"],
                         "2026-11-09T00:00:00+00:00")
        self.assertIsNotNone(block["last_activity"])
        self.assertIsNotNone(block["missed_checks"])
        self.assertIn("stalled", block)
        self.assertEqual(feed["progress"]["summary"],
                         {"armed": 1, "stalled": 0})

    def test_archived_bundles_are_excluded(self):
        old = bundle_mod.create_bundle(self.plans, "old",
                                       plan=True)
        bundle_mod.create_todo(self.plans, old["id"],
                               "Finished work", status="done")
        done_dir = self.plans / "finished"
        done_dir.mkdir()
        (self.plans / old["id"]).rename(done_dir / old["id"])
        live_bundle = bundle_mod.create_bundle(
            self.plans, "live", plan=True)
        live = bundle_mod.create_todo(
            self.plans, live_bundle["id"], "Live work",
            status="doing")
        feed = feeds.classification_feed(self.project)
        self.assertEqual([t["id"] for t in feed["todos"]],
                         [live["id"]])

    def test_no_plans_dir_is_honest_absence(self):
        bare = self.root / "bare"
        bare.mkdir()
        (bare / "workbench.yaml").write_text(
            "name: Bare\n", encoding="utf-8")
        project = SimpleNamespace(
            slug="bare", name="Bare",
            manifest=load_manifest(bare / "workbench.yaml"))
        feed = feeds.classification_feed(project)
        self.assertFalse(feed["available"])
        self.assertEqual(feed["todos"], [])
        self.assertEqual(feed["progress"]["summary"],
                         {"armed": 0, "stalled": 0})


if __name__ == "__main__":
    unittest.main()
