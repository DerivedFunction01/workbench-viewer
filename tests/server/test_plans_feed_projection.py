"""Plans feed projection tests (heavy-feed batching
follow-up, 2026-11-03): the Plans section's feed serves
its bundles' todos as checklist cards, per the board
portion treatment — the fields the plan list and the
reader's checklist strip render, with the body riding
only on archived bundles' cards (the Finished list is
the one place the Plans UI renders a todo body). The
raw frontmatter dict and the whole-file markdown never
ride; the full todo record stays on the Todos section
feed, untouched.

Fixtures are built through the lib writer, so the todo
files carry the production §3.2 shape (front-matter,
body, checkpoint lines)."""

import shutil
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
from lib.plans import bundles as bundle_parser  # noqa: E402

import server as server_mod  # noqa: E402

CARD_KEYS = {"id", "title", "status", "valid", "path",
             "bundle", "archived", "derived"}
BODY = ("Step notes for the work.\n\n"
        "progress-checkpoint: 2026-10-25T09:00:00+00:00 "
        "— started\n")


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


class PlansFeedProjection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.project = make_project(self.root)
        plans = self.project.manifest.plans
        bundle_mod.create_bundle(plans, "work", plan=True,
                                 today="2026-10-25")
        self.active = bundle_mod.create_todo(
            plans, "work", "Active thing", body=BODY)
        bundle_mod.create_bundle(plans, "old-work",
                                 today="2026-10-25")
        self.done = bundle_mod.create_todo(
            plans, "old-work", "Finished thing",
            status="done", body=BODY)
        finished = plans / "finished"
        finished.mkdir()
        shutil.move(str(plans / "2026-10-25-old-work"),
                    str(finished / "2026-10-25-old-work"))

    def tearDown(self):
        self.tmp.cleanup()

    def _bundles_by_id(self, feed):
        return {b["id"]: b for b in feed["bundles"]}

    def _full_todo(self, bundle_id, todo_id):
        bundles = bundle_parser.list_bundles(
            self.project.manifest.plans)
        bundle = {b["id"]: b for b in bundles}[bundle_id]
        return {t["id"]: t for t in bundle["todos"]}[todo_id]

    def test_active_todo_card_is_projection_only(self):
        feed = server_mod.plans_feed(self.project)
        bundle = self._bundles_by_id(
            feed)["2026-10-25-work"]
        (card,) = bundle["todos"]
        self.assertEqual(set(card), CARD_KEYS)
        full = self._full_todo("2026-10-25-work",
                               self.active["id"])
        for key in CARD_KEYS - {"derived"}:
            self.assertEqual(card[key], full[key])
        # `derived` is the feed's own staleness attach —
        # the parser record does not carry it
        self.assertEqual(set(card["derived"]),
                         {"age_days", "stale"})
        # the full record really carries what was dropped
        self.assertIn("markdown", full)
        self.assertIn("fields", full)
        self.assertEqual(full["body"], BODY.strip("\n"))

    def test_archived_todo_card_keeps_body_only(self):
        feed = server_mod.plans_feed(self.project)
        bundle = self._bundles_by_id(
            feed)["2026-10-25-old-work"]
        (card,) = bundle["todos"]
        self.assertEqual(set(card), CARD_KEYS | {"body"})
        self.assertEqual(card["body"],
                         BODY.strip("\n"))

    def test_counts_and_plan_summaries_ride_whole(self):
        feed = server_mod.plans_feed(self.project)
        bundles = self._bundles_by_id(feed)
        work = bundles["2026-10-25-work"]
        self.assertEqual(work["todo_count"], 1)
        self.assertEqual(work["open_count"], 1)
        full = {b["id"]: b for b in bundle_parser.list_bundles(
            self.project.manifest.plans)}["2026-10-25-work"]
        for key in ("title", "status_bucket", "step_count",
                    "questions", "subplans", "conforming",
                    "modified"):
            self.assertEqual(work["plan"][key],
                             full["plan"][key])
        self.assertIn("derived", work)
        self.assertIn("derived", work["plan"])

    def test_shared_bundles_are_not_mutated(self):
        shared = bundle_parser.list_bundles(
            self.project.manifest.plans)
        feed = server_mod.plans_feed(self.project,
                                     bundles=shared)
        self.assertTrue(feed["available"])
        for bundle in shared:
            for todo in bundle["todos"]:
                self.assertIn("markdown", todo)
        # the board portion still assembles off the same
        # shared parse: its counts see both bundles
        portion = server_mod.board_project_feed(
            self.project)
        self.assertEqual(portion["counts"]["todos"]["todo"],
                         1)
        self.assertEqual(portion["counts"]["todos"]["done"],
                         1)

    def test_full_record_stays_on_todos_feed(self):
        feed = server_mod.todos_feed(self.project)
        full = {t["id"]: t for t in feed["todos"]}[
            self.active["id"]]
        self.assertIn("markdown", full)
        self.assertIn("fields", full)
        self.assertEqual(full["body"], BODY.strip("\n"))


if __name__ == "__main__":
    unittest.main()
