"""Step 2 gate tests: the registry store discipline.

Proves (subplan 09 / founding plan Step 2 verify): a mutation
commits atomically, a stale-version write fails naming the
newer version, export → rebuild round-trips, a canonical
transition without a ruling note is refused, the full mockup
lifecycle walks, two projects stay isolated, the todo
lifecycle walks, uniformity refuses canonical/approve, and
approval binds to the state snapshot.
"""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lib import export as export_mod
from lib import registry as reg
from lib import staleness as stale_mod

FIXED_NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


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

    def add(self, slug="sidebar", **kw):
        return reg.add_entry(self.db, self.layout, slug, **kw)


class TestLifecycle(Fixture):
    def test_add_creates_dir_file_fingerprint(self):
        e = self.add()
        self.assertEqual(e["status"], "unexplored")
        self.assertEqual(e["version"], 1)
        main = Path(e["entry_dir"]) / "mock.html"
        self.assertTrue(main.is_file())
        self.assertEqual(e["content_sha256"],
                         reg.sha256_file(main))

    def test_duplicate_add_refused(self):
        self.add()
        with self.assertRaises(reg.RegistryError):
            self.add()

    def test_set_fields_and_cas(self):
        e = self.add()
        e2 = reg.set_fields(self.db, "sidebar",
                            {"title": "Sidebar, final"},
                            expect_version=e["version"])
        self.assertEqual(e2["version"], e["version"] + 1)
        with self.assertRaises(reg.VersionConflict) as cm:
            reg.set_fields(self.db, "sidebar", {"title": "x"},
                           expect_version=e["version"])
        self.assertEqual(cm.exception.current_version,
                         e["version"] + 1)
        self.assertIn("current version is", str(cm.exception))

    def test_set_rejects_status_field(self):
        self.add()
        with self.assertRaises(reg.RegistryError):
            reg.set_fields(self.db, "sidebar",
                           {"status": "canonical"})

    def test_canonical_requires_ruling(self):
        self.add()
        with self.assertRaises(reg.RulingRequired):
            reg.set_status(self.db, "sidebar", "canonical")
        ok = reg.set_status(self.db, "sidebar", "canonical",
                            ruling="the owner: this is the design")
        self.assertEqual(ok["status"], "canonical")
        self.assertEqual(ok["ruling_text"],
                         "the owner: this is the design")

    def test_hard_gate_requires_gate_name(self):
        self.add()
        with self.assertRaises(reg.RulingRequired):
            reg.set_status(self.db, "sidebar", "hard-gate",
                           ruling="blocked")
        ok = reg.set_status(self.db, "sidebar", "hard-gate",
                            ruling="blocked", gate="§F rulings")
        self.assertEqual(ok["gate"], "§F rulings")

    def test_history_records_every_mutation(self):
        self.add()
        reg.set_fields(self.db, "sidebar", {"title": "T"})
        reg.set_status(self.db, "sidebar", "deferred",
                       ruling="later")
        verbs = [h["verb"] for h in reg.history_for(self.db,
                                                    "sidebar")]
        self.assertEqual(verbs, ["add", "set", "set-status"])

    def test_supersede_walks_and_refuses_repeat(self):
        self.add()
        self.add("sidebar-v2")
        old = reg.supersede(self.db, "sidebar", "sidebar-v2",
                            ruling="v2 wins")
        self.assertEqual(old["status"], "abandoned")
        self.assertEqual(old["superseded_by"], "sidebar-v2")
        new_hist = reg.history_for(self.db, "sidebar-v2")
        self.assertTrue(any(h["verb"] == "supersede"
                            for h in new_hist))
        with self.assertRaises(reg.RegistryError):
            reg.supersede(self.db, "sidebar", "sidebar-v2")

    def test_archive_unarchive_round_trip(self):
        e = self.add()
        src = Path(e["entry_dir"])
        a = reg.archive_entry(self.db, self.layout, "sidebar")
        self.assertTrue(a["archived"])
        self.assertFalse(src.exists())
        dst = Path(a["entry_dir"])
        self.assertTrue(dst.is_dir())
        self.assertIn("archive", dst.parts)
        u = reg.unarchive_entry(self.db, self.layout, "sidebar")
        self.assertFalse(u["archived"])
        self.assertTrue(src.is_dir())

    def test_verify_drift_gate(self):
        e = self.add()
        main = Path(e["entry_dir"]) / "mock.html"
        main.write_text("<html>changed</html>\n")
        with self.assertRaises(reg.RegistryError):
            reg.verify_entry(self.db, "sidebar")
        ok = reg.verify_entry(self.db, "sidebar",
                              accept_drift=True)
        self.assertIsNotNone(ok["last_verified_at"])
        self.assertEqual(ok["content_sha256"],
                         reg.sha256_file(main))
        # and now a clean verify passes without the flag
        ok2 = reg.verify_entry(self.db, "sidebar")
        self.assertEqual(ok2["version"], ok["version"] + 1)


class TestExportRebuild(Fixture):
    def test_round_trip_identical_with_fixed_clock(self):
        self.add()
        self.add("other")
        reg.set_status(self.db, "sidebar", "canonical",
                       ruling="ruled")
        reg.add_todo(self.db, "t1", "Do a thing")
        first = export_mod.build_export(self.db, now=FIXED_NOW)
        export_path = self.root / "registry.json"
        export_path.write_text(export_mod.canonical_text(first))
        db2 = self.root / "rebuilt" / "registry.db"
        export_mod.rebuild(db2, export_path)
        second = export_mod.build_export(db2, now=FIXED_NOW)
        self.assertEqual(export_mod.ruled_sections(first),
                         export_mod.ruled_sections(second))
        self.assertEqual(export_mod.canonical_text(first),
                         export_mod.canonical_text(second))

    def test_rebuild_refuses_nonempty(self):
        self.add()
        export_path = export_mod.regenerate(self.db)
        with self.assertRaises(reg.RegistryError):
            export_mod.rebuild(self.db, export_path)


class TestUniformityGate(Fixture):
    def _bad_entry(self, slug="bad"):
        e = reg.add_entry(self.db, self.layout, slug)
        main = Path(e["entry_dir"]) / "mock.html"
        main.write_text(
            "<html><body style='color: #ff0000'>x</body>"
            "</html>\n")
        reg.verify_entry(self.db, slug, accept_drift=True)
        return e

    def test_canonical_refused_for_hardcoded_color(self):
        self._bad_entry()
        with self.assertRaises(reg.UniformityRefused):
            reg.set_status(self.db, "bad", "canonical",
                           ruling="looks fine to me",
                           layout=self.layout)

    def test_approve_refused_for_hardcoded_color(self):
        self._bad_entry()
        with self.assertRaises(reg.UniformityRefused):
            reg.review_entry(self.db, "bad", "approve",
                             actor="viewer", layout=self.layout)

    def test_token_block_color_is_fine(self):
        e = self.add("good")
        main = Path(e["entry_dir"]) / "mock.html"
        main.write_text(
            "<style>:root{--accent:#5b9dff}</style>"
            "<p style='color:var(--accent)'>x</p>\n")
        reg.verify_entry(self.db, "good", accept_drift=True)
        ok = reg.set_status(self.db, "good", "canonical",
                            ruling="uniform", layout=self.layout)
        self.assertEqual(ok["status"], "canonical")

    def test_variant_suffix_file_refused(self):
        e = self.add("var")
        (Path(e["entry_dir"]) / "SidebarFinal.html").write_text(
            "<p>v</p>\n")
        with self.assertRaises(reg.UniformityRefused):
            reg.set_status(self.db, "var", "canonical",
                           ruling="r", layout=self.layout)


class TestArtifactKind(Fixture):
    """Kind artifact (Artifacts collection): the lifecycle
    is kind-blind, but uniformity scopes per kind — the
    design discipline does not bind a disposition sheet,
    and question-completeness binds it instead (SPEC §10).
    """
    PROSE_HTML = ("<html><body><p style='color: #cc0000'>"
                  "A long explanation, styled its own way."
                  "</p></body></html>\n")
    SCHEMA = {"decision": {"type": "select",
                           "options": ["go", "hold"],
                           "question": "Proceed?",
                           "recommended": "go",
                           "option_notes": {"go": "unblocks"}}}

    def _plant(self, slug, kind, schema):
        e = self.add(slug, kind=kind, state_schema=schema)
        main = Path(e["entry_dir"]) / "mock.html"
        main.write_text(self.PROSE_HTML)
        reg.verify_entry(self.db, slug, accept_drift=True)
        return e

    def test_add_accepts_artifact_refuses_unknown_kind(self):
        e = self.add("sheet", kind="artifact")
        self.assertEqual(e["kind"], "artifact")
        with self.assertRaises(reg.RegistryError):
            self.add("other", kind="widget")

    def test_artifact_canonical_despite_design_discipline(self):
        self._plant("sheet", "artifact", self.SCHEMA)
        ok = reg.set_status(self.db, "sheet", "canonical",
                            ruling="answered",
                            layout=self.layout)
        self.assertEqual(ok["status"], "canonical")

    def test_artifact_approve_despite_design_discipline(self):
        self._plant("sheet", "artifact", self.SCHEMA)
        reg.review_entry(self.db, "sheet", "approve",
                         actor="viewer", layout=self.layout)
        latest = reg.latest_review(self.db, "sheet")
        self.assertEqual(latest["payload"]["disposition"],
                         "approve")

    def test_same_file_refused_for_design_kind(self):
        self._plant("mock", "mockup", None)
        with self.assertRaises(reg.UniformityRefused):
            reg.set_status(self.db, "mock", "canonical",
                           ruling="looks fine",
                           layout=self.layout)
        with self.assertRaises(reg.UniformityRefused):
            reg.review_entry(self.db, "mock", "approve",
                             actor="viewer", layout=self.layout)

    def test_question_without_recommendation_refused(self):
        bare = {"decision": {"type": "select",
                             "options": ["go", "hold"],
                             "question": "Proceed?"}}
        self._plant("sheet", "artifact", bare)
        with self.assertRaises(reg.UniformityRefused):
            reg.set_status(self.db, "sheet", "canonical",
                           ruling="answered", layout=self.layout)


class TestStateAndApproval(Fixture):
    SCHEMA = {"density": {"type": "select",
                          "options": ["cozy", "compact"]},
              "stacking": {"type": "toggle"}}

    def setUp(self):
        super().setUp()
        self.add("tile", state_schema=self.SCHEMA)

    def test_schema_validation(self):
        with self.assertRaises(reg.RegistryError):
            reg.set_state_schema(self.db, "tile",
                                 {"x": {"type": "bogus"}})
        with self.assertRaises(reg.RegistryError):
            reg.set_state(self.db, "tile",
                          {"density": "roomy"})
        with self.assertRaises(reg.RegistryError):
            reg.set_state(self.db, "tile", {"stacking": "yes"})
        ok = reg.set_state(self.db, "tile",
                           {"density": "compact",
                            "stacking": True})
        self.assertEqual(ok["state_json"]["density"], "compact")

    def test_approval_binds_to_state(self):
        reg.set_state(self.db, "tile",
                      {"density": "compact", "stacking": True})
        reg.review_entry(self.db, "tile", "approve",
                         actor="viewer", comment="ship it",
                         layout=self.layout)
        entry = reg.get_entry(self.db, "tile")
        cov = stale_mod.approval_coverage(
            entry, reg.latest_review(self.db, "tile"))
        self.assertTrue(cov["approved"])
        self.assertTrue(cov["covers_current"])
        # change the state: coverage lapses, approval remains
        reg.set_state(self.db, "tile",
                      {"density": "cozy", "stacking": True})
        entry = reg.get_entry(self.db, "tile")
        cov = stale_mod.approval_coverage(
            entry, reg.latest_review(self.db, "tile"))
        self.assertTrue(cov["approved"])
        self.assertFalse(cov["covers_current"])
        # re-approve: covered again
        reg.review_entry(self.db, "tile", "approve",
                         actor="viewer", layout=self.layout)
        entry = reg.get_entry(self.db, "tile")
        cov = stale_mod.approval_coverage(
            entry, reg.latest_review(self.db, "tile"))
        self.assertTrue(cov["covers_current"])

    def test_needs_changes_round_trips(self):
        reg.review_entry(self.db, "tile", "needs-changes",
                         actor="viewer",
                         comment="tighten the spacing")
        latest = reg.latest_review(self.db, "tile")
        self.assertEqual(latest["payload"]["disposition"],
                         "needs-changes")
        self.assertEqual(latest["payload"]["comment"],
                         "tighten the spacing")
        hist = reg.history_for(self.db, "tile")
        self.assertTrue(any(h["verb"] == "review"
                            for h in hist))


class TestTodos(Fixture):
    def test_lifecycle(self):
        t = reg.add_todo(self.db, "write-spec", "Write the spec",
                         link_kind="plan", link_ref="p1")
        self.assertEqual(t["status"], "todo")
        t = reg.set_todo_status(self.db, "write-spec", "doing",
                                expect_version=1)
        self.assertEqual(t["status"], "doing")
        with self.assertRaises(reg.VersionConflict):
            reg.set_todo_status(self.db, "write-spec", "done",
                                expect_version=1)
        t = reg.set_todo_status(self.db, "write-spec", "done",
                                expect_version=2)
        self.assertEqual(t["status"], "done")
        self.assertEqual([x["id"] for x in
                          reg.list_todos(self.db)], ["write-spec"])
        self.assertEqual(reg.list_todos(self.db,
                                        status="todo"), [])


class TestIsolation(unittest.TestCase):
    def test_two_projects_no_cross_talk(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dbs = []
            for name in ("proj-a", "proj-b"):
                db = root / name / "workbench" / "registry.db"
                layout = (root / name / "workbench" / "entries",
                          root / name / "workbench" / "archive")
                reg.init_registry(db)
                reg.add_entry(db, layout, "shared-slug",
                              title=f"Only in {name}")
                dbs.append(db)
            a = reg.list_entries(dbs[0])
            b = reg.list_entries(dbs[1])
            self.assertEqual(a[0]["title"], "Only in proj-a")
            self.assertEqual(b[0]["title"], "Only in proj-b")
            reg.add_todo(dbs[0], "only-a", "A todo")
            self.assertEqual(reg.list_todos(dbs[1]), [])


if __name__ == "__main__":
    unittest.main()
