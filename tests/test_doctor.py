"""wb doctor: the consistency checks over fixture plan
trees and registries, the run-state diff, and the digest
posting decisions (wb-doctor plan, steps 1-3). Every check
derives from the lib functions the feeds use, so the
fixtures plant the same shapes those functions read."""

import tempfile
import unittest
from pathlib import Path

from lib import doctor
from lib import messages as msg_mod
from lib import registry as reg
from lib.manifest import Manifest
from lib.sweep import Project

TODO_A = """---
id: {tid}
title: {title}
status: {status}
created: 2026-10-26
updated: 2026-10-26
{extra}---
"""


def make_project(root, *, plans=True, registry_path=None,
                 mockups=None, archive=None):
    manifest = Manifest(
        root=root, name="Fixture", slug="fixture",
        registry=registry_path,
        plans=(root / ".plans") if plans else None,
        mockups=mockups, archive=archive)
    return Project(manifest)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def todo_text(tid, *, title="A todo", status="todo",
              plan=None):
    extra = f"plan: {plan}\n" if plan else ""
    return TODO_A.format(tid=tid, title=title,
                         status=status, extra=extra)


class TestPlanTodoChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans = self.root / ".plans"
        self.plans.mkdir(parents=True)
        self.project = make_project(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self):
        return doctor.plan_todo_findings(self.project)

    def checks(self):
        return [(f["check"], f["subject"])
                for f in self.findings()]

    def test_contradicted_closeout(self):
        write(self.plans / "2026-01-01-done.md",
              "# Done thing\n\nStatus: complete\n\n"
              "## Objective\n\nLanded already.\n")
        self.assertEqual(
            self.checks(),
            [("plan-closeout", "2026-01-01-done.md")])

    def test_finished_plan_with_active_status(self):
        write(self.plans / "finished" / "2026-01-01-old.md",
              "# Old thing\n\nStatus: draft\n")
        self.assertEqual(
            self.checks(),
            [("plan-closeout", "finished/2026-01-01-old.md")])

    def test_status_less_plan(self):
        write(self.plans / "2026-01-01-bare.md",
              "# Bare\n\n## Objective\n\nNo header fields.\n")
        self.assertEqual(
            self.checks(),
            [("plan-status", "2026-01-01-bare.md")])

    def test_out_of_vocabulary_status(self):
        write(self.plans / "2026-01-01-odd.md",
              "# Odd\n\nStatus: banana\n")
        found = self.findings()
        self.assertEqual([f["check"] for f in found],
                         ["plan-status"])
        self.assertIn("banana", found[0]["detail"])

    def test_missing_subplan_child(self):
        write(self.plans / "2026-01-01-parent.md",
              "# Parent\n\nStatus: draft\n\n## Subplans\n\n"
              "- `2026-01-01-ghost.md` — never written\n")
        self.assertEqual(
            self.checks(),
            [("plan-missing-child",
              "2026-01-01-parent.md -> "
              "2026-01-01-ghost.md")])

    def test_done_bundle_with_open_plan(self):
        bundle = self.plans / "2026-01-02-work"
        write(bundle / "plan.md",
              "# Work\n\nStatus: in progress\n")
        write(bundle / "todos" / "a.md",
              todo_text("t-AAAAAAAAAA", status="done"))
        write(bundle / "todos" / "b.md",
              todo_text("t-BBBBBBBBBB", status="done"))
        self.assertEqual(
            self.checks(),
            [("plan-done-not-closed",
              "2026-01-02-work/plan.md")])

    def test_malformed_todo(self):
        bundle = self.plans / "2026-01-03-work"
        write(bundle / "plan.md", "# Work\n\nStatus: draft\n")
        write(bundle / "todos" / "bad.md",
              "---\ntitle: No id here\nstatus: todo\n"
              "created: 2026-10-26\nupdated: 2026-10-26\n"
              "---\n")
        found = self.findings()
        self.assertEqual([f["check"] for f in found],
                         ["todo-frontmatter"])
        self.assertIn("missing required field: id",
                      found[0]["detail"])

    def test_todo_with_missing_plan(self):
        bundle = self.plans / "2026-01-04-work"
        write(bundle / "plan.md", "# Work\n\nStatus: draft\n")
        write(bundle / "todos" / "a.md",
              todo_text("t-AAAAAAAAAA",
                        plan=".plans/ghost.md"))
        self.assertEqual(
            [f["check"] for f in self.findings()],
            ["todo-missing-plan"])

    def test_todo_with_no_plan_reference(self):
        # The ruling: a todo may be a task without a plan
        # file — no plan reference, no finding.
        bundle = self.plans / "2026-01-09-work"
        write(bundle / "plan.md", "# Work\n\nStatus: draft\n")
        write(bundle / "todos" / "a.md",
              todo_text("t-AAAAAAAAAA"))
        self.assertEqual(self.findings(), [])

    def test_todo_plan_resolved_under_finished(self):
        # Closeout moved the named flat plan under
        # finished/; the reference as written still
        # resolves.
        write(self.plans / "finished" / "2026-01-10-old.md",
              "# Old\n\nStatus: complete\n")
        bundle = self.plans / "2026-01-11-work"
        write(bundle / "plan.md", "# Work\n\nStatus: draft\n")
        write(bundle / "todos" / "a.md",
              todo_text("t-AAAAAAAAAA",
                        plan=".plans/2026-01-10-old.md"))
        self.assertEqual(self.findings(), [])

    def test_todo_bundle_plan_resolved_under_finished(self):
        # The closed-out bundle moved whole: its own todo
        # still names the plan by the pre-closeout path.
        bundle = self.plans / "finished" / "2026-01-12-work"
        write(bundle / "plan.md",
              "# Work\n\nStatus: complete\n")
        write(bundle / "todos" / "a.md",
              todo_text("t-AAAAAAAAAA", status="done",
                        plan=".plans/2026-01-12-work/plan.md"))
        self.assertEqual(self.findings(), [])

    def test_duplicate_todo_id_across_bundles(self):
        for name in ("2026-01-05-one", "2026-01-06-two"):
            bundle = self.plans / name
            write(bundle / "plan.md",
                  "# Work\n\nStatus: draft\n")
            write(bundle / "todos" / "a.md",
                  todo_text("t-AAAAAAAAAA"))
        found = self.findings()
        self.assertEqual([f["check"] for f in found],
                         ["todo-duplicate-id"])
        self.assertEqual(found[0]["subject"], "t-AAAAAAAAAA")

    def test_clean_tree_has_no_findings(self):
        write(self.plans / "2026-01-07-plan.md",
              "# Plan\n\nStatus: draft\n\n## Subplans\n\n"
              "- `finished/2026-01-07-child.md` — filed\n")
        write(self.plans / "finished" / "2026-01-07-child.md",
              "# Child\n\nStatus: complete\n")
        bundle = self.plans / "2026-01-08-work"
        write(bundle / "plan.md", "# Work\n\nStatus: draft\n")
        write(bundle / "todos" / "a.md",
              todo_text("t-AAAAAAAAAA",
                        plan=".plans/2026-01-07-plan.md"))
        self.assertEqual(self.findings(), [])


class TestRegistryChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "workbench" / "registry.db"
        self.layout = (self.root / "workbench" / "entries",
                       self.root / "workbench" / "archive")
        reg.init_registry(self.db)
        self.project = make_project(
            self.root, plans=False, registry_path=self.db,
            mockups=self.layout[0], archive=self.layout[1])

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self):
        return doctor.registry_findings(self.project)

    def test_validator_violation(self):
        reg.add_entry(self.db, self.layout, "a")
        import sqlite3
        conn = sqlite3.connect(str(self.db))
        conn.execute("UPDATE entries SET superseded_by = "
                     "'ghost' WHERE id = 'a'")
        conn.commit()
        conn.close()
        subjects = {(f["check"], f["subject"])
                    for f in self.findings()}
        self.assertIn(("registry-validator",
                       "supersedes-resolve:a"), subjects)

    def test_approval_no_longer_covers_state(self):
        schema = {"mode": {"type": "select",
                           "options": ["a", "b"],
                           "default": "a"}}
        reg.add_entry(self.db, self.layout, "cov",
                      state_schema=schema)
        reg.review_entry(self.db, "cov", "approve",
                         actor="test", layout=self.layout)
        reg.set_state(self.db, "cov", {"mode": "b"},
                      actor="test")
        found = self.findings()
        self.assertEqual(
            [(f["check"], f["subject"]) for f in found],
            [("approval-coverage", "cov")])

    def test_archive_mismatch_reported_once(self):
        reg.add_entry(self.db, self.layout, "arc")
        reg.archive_entry(self.db, self.layout, "arc")
        # Move the folder back by hand: the flag says
        # archived, the folder says active.
        import shutil
        src = Path(reg.get_entry(self.db, "arc")["entry_dir"])
        year_dir = src.parent
        shutil.move(str(src), str(self.layout[0] / "arc"))
        if year_dir.is_dir() and not any(year_dir.iterdir()):
            year_dir.rmdir()
        archive_related = [
            f for f in self.findings()
            if f["check"] == "entry-archive-mismatch"
            or f["subject"] ==
            "archived-folder-agreement:arc"]
        self.assertEqual(
            [(f["check"], f["subject"])
             for f in archive_related],
            [("registry-validator",
              "archived-folder-agreement:arc")])

    def test_clean_registry_has_no_findings(self):
        reg.add_entry(self.db, self.layout, "tidy")
        reg.verify_entry(self.db, "tidy")
        self.assertEqual(self.findings(), [])


class TestRunPost(unittest.TestCase):
    """The diff + digest decisions (step 3) against a
    scratch message store: baseline posts the full set,
    unchanged posts nothing, a swap names new + resolved."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans = self.root / ".plans"
        self.plans.mkdir(parents=True)
        write(self.plans / "2026-01-01-bare.md",
              "# Bare\n\n## Objective\n\nNo status.\n")
        self.project = make_project(self.root)
        self.state = self.root / "state" / "doctor.json"
        self.msg_db = self.root / "state" / "messages.db"

    def tearDown(self):
        self.tmp.cleanup()

    def run_post(self, now):
        return doctor.run_post(
            [self.project], state_path=self.state,
            messages_db=self.msg_db,
            harness_slug="fixture", now=now)

    def outbox(self):
        return msg_mod.list_outbox(self.msg_db)

    def body_of(self, message_id):
        import sqlite3
        conn = sqlite3.connect(str(self.msg_db))
        row = conn.execute(
            "SELECT body FROM messages WHERE id = ?",
            (message_id,)).fetchone()
        conn.close()
        return row[0]

    def test_baseline_posts_full_set(self):
        s = self.run_post("2026-10-26T00:00:00+00:00")
        self.assertTrue(s["baseline"])
        self.assertTrue(s["posted"])
        self.assertEqual(len(s["findings"]), 1)
        self.assertEqual(len(self.outbox()), 1)
        body = self.body_of(s["message_id"])
        self.assertIn("baseline", body)
        self.assertIn("2026-01-01-bare.md", body)
        self.assertTrue(self.state.is_file())

    def test_unchanged_second_run_posts_nothing(self):
        self.run_post("2026-10-26T00:00:00+00:00")
        s = self.run_post("2026-10-26T00:15:00+00:00")
        self.assertFalse(s["baseline"])
        self.assertFalse(s["posted"])
        self.assertEqual(len(self.outbox()), 1)

    def test_resolved_finding_posts_digest(self):
        self.run_post("2026-10-26T00:00:00+00:00")
        write(self.plans / "2026-01-01-bare.md",
              "# Bare\n\nStatus: draft\n")
        s = self.run_post("2026-10-26T00:15:00+00:00")
        self.assertTrue(s["posted"])
        self.assertEqual(len(s["resolved"]), 1)
        self.assertEqual(len(s["new"]), 0)
        body = self.body_of(s["message_id"])
        self.assertIn("Resolved:", body)
        self.assertIn("2026-01-01-bare.md", body)
        self.assertEqual(len(self.outbox()), 2)

    def test_new_finding_after_baseline(self):
        write(self.plans / "2026-01-01-bare.md",
              "# Bare\n\nStatus: draft\n")
        self.run_post("2026-10-26T00:00:00+00:00")
        write(self.plans / "2026-01-02-odd.md",
              "# Odd\n\nStatus: banana\n")
        s = self.run_post("2026-10-26T00:15:00+00:00")
        self.assertTrue(s["posted"])
        self.assertEqual(len(s["new"]), 1)
        self.assertEqual(s["new"][0]["check"], "plan-status")
        body = self.body_of(s["message_id"])
        self.assertIn("New:", body)
        self.assertIn("banana", body)

    def test_first_seen_survives_later_runs(self):
        self.run_post("2026-10-26T00:00:00+00:00")
        self.run_post("2026-10-26T01:00:00+00:00")
        records = doctor.load_state(self.state)
        self.assertEqual(len(records), 1)
        rec = next(iter(records.values()))
        self.assertEqual(rec["first_seen"],
                         "2026-10-26T00:00:00+00:00")


class TestDoctorCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "ws"
        proj = self.ws / "proj"
        (proj / ".plans").mkdir(parents=True)
        (proj / "workbench.yaml").write_text(
            "name: Proj\nslug: proj\n"
            "registry: workbench/registry.db\n"
            "plans: .plans\n", encoding="utf-8")
        self.plan = proj / ".plans" / "2026-01-01-bare.md"
        self.plan.write_text("# Bare\n\n## Objective\n",
                             encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_doctor(self):
        import subprocess
        import sys
        repo = Path(__file__).resolve().parent.parent
        return subprocess.run(
            [sys.executable, str(repo / "wb"), "doctor",
             "--root", str(self.ws)],
            capture_output=True, text=True, cwd=repo)

    def test_findings_exit_1(self):
        r = self.run_doctor()
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("plan-status", r.stdout)
        self.assertIn("2026-01-01-bare.md", r.stdout)

    def test_clean_exit_0(self):
        self.plan.write_text("# Bare\n\nStatus: draft\n",
                             encoding="utf-8")
        r = self.run_doctor()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("clean", r.stdout)


if __name__ == "__main__":
    unittest.main()
