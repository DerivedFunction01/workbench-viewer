"""Owner attribution: schema v2, the three entry fields,
and the set-owner / set-class mutations.

The cleanup consumer's contract: owner_thread is the stable
route to the owning thread, owner_label its display snapshot,
deploy_class ('standard' | 'deployed') the mechanical
exclusion — deployed entries are never stale by class.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lib import registry as reg
from lib.registry import store as store_mod


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "workbench" / "registry.db"
        self.layout = (self.root / "workbench" / "entries",
                       self.root / "workbench" / "archive")
        reg.init_registry(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, slug="tile", **kw):
        return reg.add_entry(self.db, self.layout, slug, **kw)


class TestSchemaV2(Fixture):
    def test_fresh_db_is_v2_with_defaults(self):
        conn = sqlite3.connect(self.db)
        version = conn.execute(
            "PRAGMA user_version").fetchone()[0]
        conn.close()
        self.assertEqual(version, 2)
        e = self.add()
        self.assertIsNone(e["owner_thread"])
        self.assertIsNone(e["owner_label"])
        self.assertEqual(e["deploy_class"], "standard")

    def test_v1_db_migrates_keeping_rows(self):
        legacy = self.root / "legacy.db"
        conn = sqlite3.connect(legacy)
        conn.executescript(store_mod.SCHEMA_V1)
        # The v1 shape predates the attribution columns:
        # rebuild the entries table without them.
        conn.executescript("""
DROP TABLE entries;
CREATE TABLE entries (
  id TEXT PRIMARY KEY, title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'mockup',
  status TEXT NOT NULL DEFAULT 'unexplored',
  gate TEXT, ruling_text TEXT, ruling_date TEXT,
  spec_ref TEXT, plan_ref TEXT,
  source_kind TEXT NOT NULL DEFAULT 'entry-dir',
  source_ref TEXT, entry_dir TEXT, main_file TEXT,
  content_sha256 TEXT, config_path TEXT,
  state_schema TEXT, state_json TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  status_changed_at TEXT NOT NULL,
  last_verified_at TEXT, archived INTEGER NOT NULL
  DEFAULT 0, archived_at TEXT, superseded_by TEXT,
  version INTEGER NOT NULL DEFAULT 1);
INSERT INTO entries (id, title, created_at, updated_at,
  status_changed_at) VALUES ('old', 'Old',
  '2026-01-01', '2026-01-01', '2026-01-01');
""")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()
        conn = store_mod.connect(legacy)
        version = conn.execute(
            "PRAGMA user_version").fetchone()[0]
        row = conn.execute(
            "SELECT owner_thread, deploy_class FROM entries"
            " WHERE id = 'old'").fetchone()
        conn.close()
        self.assertEqual(version, 2)
        self.assertEqual(tuple(row), (None, "standard"))


class TestAttributionMutations(Fixture):
    def test_add_with_attribution(self):
        e = self.add(owner_thread="chat-1",
                     owner_label="Owning thread",
                     deploy_class="deployed")
        self.assertEqual(e["owner_thread"], "chat-1")
        self.assertEqual(e["owner_label"], "Owning thread")
        self.assertEqual(e["deploy_class"], "deployed")

    def test_add_refuses_unknown_deploy_class(self):
        with self.assertRaises(reg.RegistryError):
            self.add(deploy_class="live")

    def test_set_owner_and_clear(self):
        self.add()
        e = reg.set_owner(self.db, "tile", "chat-9", "Home")
        self.assertEqual(e["owner_thread"], "chat-9")
        self.assertEqual(e["owner_label"], "Home")
        self.assertEqual(e["version"], 2)
        e = reg.set_owner(self.db, "tile", None)
        self.assertIsNone(e["owner_thread"])
        self.assertIsNone(e["owner_label"])
        verbs = [h["verb"] for h in
                 reg.history_for(self.db, "tile")]
        self.assertIn("set-owner", verbs)

    def test_set_deploy_class(self):
        self.add()
        e = reg.set_deploy_class(self.db, "tile", "deployed")
        self.assertEqual(e["deploy_class"], "deployed")
        with self.assertRaises(reg.RegistryError):
            reg.set_deploy_class(self.db, "tile", "live")
        verbs = [h["verb"] for h in
                 reg.history_for(self.db, "tile")]
        self.assertIn("set-class", verbs)

    def test_unknown_entry_refused(self):
        with self.assertRaises(reg.RegistryError):
            reg.set_owner(self.db, "ghost", "chat-1")


if __name__ == "__main__":
    unittest.main()


class TestPlanLink(unittest.TestCase):
    """The plan anchor: resolve_plan_link against a plans
    corpus with an active bundle, a finished flat plan, and
    a missing ref."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plans = Path(self.tmp.name) / ".plans"
        bundle = self.plans / "2026-01-02-widget-study"
        (bundle / "todos").mkdir(parents=True)
        (bundle / "plan.md").write_text(
            "# Widget study\n\nStatus: in progress\n")
        fin = self.plans / "finished"
        fin.mkdir()
        (fin / "2026-01-01-old-study.md").write_text(
            "# Old study\n\nStatus: draft\n")
        (self.plans / "2026-01-03-flat-study.md").write_text(
            "# Flat study\n\nStatus: draft\n")
        from lib.plans import bundles as bundle_parser
        self.bp = bundle_parser

    def tearDown(self):
        self.tmp.cleanup()

    def test_active_bundle_by_id_not_terminal(self):
        link = self.bp.resolve_plan_link(
            self.plans, "2026-01-02-widget-study")
        self.assertTrue(link["found"])
        self.assertEqual(link["status"], "in progress")
        self.assertFalse(link["terminal"])
        self.assertFalse(link["archived"])

    def test_finished_plan_terminal_by_location(self):
        link = self.bp.resolve_plan_link(
            self.plans, "2026-01-01-old-study.md")
        self.assertTrue(link["found"])
        self.assertTrue(link["archived"])
        self.assertTrue(link["terminal"])

    def test_bundle_plan_path_form(self):
        link = self.bp.resolve_plan_link(
            self.plans, "2026-01-02-widget-study/plan.md")
        self.assertTrue(link["found"])

    def test_root_relative_flat_plan_form(self):
        # The corpus's written form: a registry entry's
        # plan_ref spelled project-root-relative
        # (`.plans/<file>.md`) must resolve to the plan
        # at exactly that path — the resolver once
        # matched only the plans-dir-relative spellings,
        # so entry-plan-missing fired for every entry
        # carrying the corpus form.
        link = self.bp.resolve_plan_link(
            self.plans,
            ".plans/2026-01-03-flat-study.md")
        self.assertTrue(link["found"])
        self.assertEqual(link["status"], "draft")
        self.assertFalse(link["archived"])

    def test_root_relative_bundle_forms(self):
        for ref in (".plans/2026-01-02-widget-study",
                    ".plans/2026-01-02-widget-study/plan.md"):
            link = self.bp.resolve_plan_link(
                self.plans, ref)
            self.assertTrue(link["found"], ref)

    def test_root_relative_finished_plan_form(self):
        link = self.bp.resolve_plan_link(
            self.plans,
            ".plans/2026-01-01-old-study.md")
        self.assertTrue(link["found"])
        self.assertTrue(link["terminal"])

    def test_fragment_form_resolves_to_the_plan(self):
        # The spec-extraction corpus form: the ref
        # names a plan plus a section inside it.
        link = self.bp.resolve_plan_link(
            self.plans,
            ".plans/2026-01-03-flat-study.md#item-7")
        self.assertTrue(link["found"])
        self.assertEqual(link["bundle_id"],
                         "2026-01-03-flat-study.md")

    def test_root_relative_missing_still_misses(self):
        link = self.bp.resolve_plan_link(
            self.plans, ".plans/2026-01-09-nope.md")
        self.assertFalse(link["found"])

    def test_missing_ref_is_a_miss_not_a_disposition(self):
        link = self.bp.resolve_plan_link(
            self.plans, "2026-01-03-nope")
        self.assertFalse(link["found"])
        self.assertFalse(link["terminal"])

    def test_no_ref(self):
        self.assertFalse(self.bp.resolve_plan_link(
            self.plans, None)["found"])
