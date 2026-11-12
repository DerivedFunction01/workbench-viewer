"""Goal contracts on wb bundles (goal-prompt
contract plan 2026-11-12, Step 4): a programme's
standing bundle carries the six-field contract
(contract.md — four fields filled per programme,
three clauses verbatim from the template), and the
doing transition's progress-check arming verifies
completeness: an incomplete contract refuses the
arm, naming the empty field. A bundle carrying no
contract arms exactly as before.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lib import bundles as bundle_mod  # noqa: E402
from lib.plans import bundles as parser  # noqa: E402

FILLED = {
    "programme": "fixture-programme",
    "objective": "Land the fixture outcome.",
    "complete_when": "The fixture gate passes on the "
                     "union tree.",
    "work_record": "This bundle's todos and the "
                   "progress-check record.",
}


class SeamCase(unittest.TestCase):
    """A tmp workspace + tmp scheduler/armed dirs
    under the env seams, with one fixture project
    (the progress suites' shape)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.ws = base / "ws"
        self.jobs = base / "jobs"
        self.jobs.mkdir(parents=True)
        self.armed = base / "armed"
        self.proj = self.ws / "fixture-proj"
        self.plans = self.proj / ".plans"
        self.plans.mkdir(parents=True)
        (self.proj / "workbench.yaml").write_text(
            "name: Fixture Proj\nslug: fixture-proj\n"
            "plans: .plans\n", encoding="utf-8")
        (self.ws / "workbench-viewer").mkdir()
        patcher = mock.patch.dict(os.environ, {
            "WB_SCHEDULER_JOBS_DIR": str(self.jobs),
            "WB_ATTENTION_ARMED_DIR": str(self.armed),
            "WB_WORKSPACE_ROOT": str(self.ws),
            "WB_VIEWER_ROOT": str(self.ws
                                  / "workbench-viewer")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        bundle_mod.create_bundle(self.plans, "work",
                                 today="2026-11-12")
        self.bundle = "2026-11-12-work"
        self.bundle_dir = self.plans / self.bundle

    def set_contract(self, **over):
        kw = dict(FILLED)
        kw.update(over)
        return bundle_mod.set_bundle_contract(
            self.plans, self.bundle, **kw)

    def write_contract_text(self, text):
        (self.bundle_dir / "contract.md").write_text(
            text, encoding="utf-8")

    def incomplete_contract(self, blank="Objective"):
        lines = [f"# Goal contract — {FILLED['programme']}",
                 ""]
        values = {
            "Programme": FILLED["programme"],
            "Objective": FILLED["objective"],
            "Complete when": FILLED["complete_when"],
            "Work record": FILLED["work_record"],
            **parser.CONTRACT_FIXED,
        }
        values[blank] = ""
        for field in parser.CONTRACT_FIELDS:
            lines.append(f"- {field}: {values[field]}")
        self.write_contract_text("\n".join(lines) + "\n")


class TestContractRecord(SeamCase):
    def test_writer_round_trip_verbatim_clauses(self):
        out = self.set_contract()
        contract = out["contract"]
        self.assertTrue(contract["complete"])
        self.assertEqual(contract["missing"], [])
        for field, text in parser.CONTRACT_FIXED.items():
            self.assertEqual(
                contract["fields"][field], text)
        self.assertEqual(
            contract["fields"]["Objective"],
            FILLED["objective"])
        # The bundle record carries the contract for
        # the feeds (Step 5's read source).
        records = parser.list_bundles(self.plans)
        record = next(b for b in records
                      if b["id"] == self.bundle)
        self.assertTrue(record["contract"]["complete"])

    def test_no_contract_parses_none(self):
        self.assertIsNone(
            parser.parse_contract(self.bundle_dir))
        records = parser.list_bundles(self.plans)
        record = next(b for b in records
                      if b["id"] == self.bundle)
        self.assertIsNone(record["contract"])

    def test_writer_refuses_empty_field_naming_it(self):
        with self.assertRaises(bundle_mod.BundleError) \
                as cm:
            self.set_contract(objective="  ")
        self.assertIn("Objective", str(cm.exception))
        self.assertFalse(
            (self.bundle_dir / "contract.md").exists())

    def test_incomplete_parse_names_missing_in_order(self):
        self.incomplete_contract(blank="Work record")
        contract = parser.parse_contract(self.bundle_dir)
        self.assertFalse(contract["complete"])
        self.assertEqual(contract["missing"],
                         ["Work record"])

    def test_absent_field_line_is_missing(self):
        text = parser.render_contract(
            FILLED["programme"], FILLED["objective"],
            FILLED["complete_when"], FILLED["work_record"])
        text = "\n".join(
            line for line in text.splitlines()
            if not line.startswith("- Cadence:")) + "\n"
        self.write_contract_text(text)
        contract = parser.parse_contract(self.bundle_dir)
        self.assertEqual(contract["missing"], ["Cadence"])


class TestArmingGate(SeamCase):
    def test_no_contract_arms_as_before(self):
        # The behavioral pair's control: without a
        # contract nothing changes — the doing move
        # arms at the default and the progress check
        # reads checkpoints as before.
        todo = bundle_mod.create_todo(
            self.plans, self.bundle, "Plain task")
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing",
            note="progress-checkpoint: "
                 "2026-11-12T15:00:00Z — started")
        self.assertEqual(moved["progress_check"], "15m")
        from lib.progress import report as report_mod
        derived = report_mod.todo_progress(moved)
        self.assertIsNotNone(derived)
        self.assertEqual(derived["cadence"], "15m")
        self.assertEqual(derived["last_checkpoint"],
                         "2026-11-12T15:00:00+00:00")
        self.assertFalse(derived["stalled"])

    def test_complete_contract_arms(self):
        self.set_contract()
        todo = bundle_mod.create_todo(
            self.plans, self.bundle, "Programme task")
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing")
        self.assertEqual(moved["progress_check"], "15m")
        self.assertIsNotNone(moved["progress_armed"])

    def test_incomplete_contract_refuses_arm_naming_field(
            self):
        self.incomplete_contract(blank="Objective")
        todo = bundle_mod.create_todo(
            self.plans, self.bundle, "Programme task")
        with self.assertRaises(bundle_mod.BundleError) \
                as cm:
            bundle_mod.set_todo_status(
                self.plans, todo["id"], "doing")
        self.assertIn("Objective", str(cm.exception))
        self.assertIn("arming refused",
                      str(cm.exception))
        # The refusal is pre-write: the todo on disk
        # is untouched — still todo, no progress
        # fields stamped.
        on_disk = parser.list_todos(
            self.plans, bundle=self.bundle)[0]
        self.assertEqual(on_disk["status"], "todo")
        self.assertIsNone(on_disk["progress_check"])

    def test_incomplete_contract_refuses_armed_create(
            self):
        self.incomplete_contract(blank="Complete when")
        with self.assertRaises(bundle_mod.BundleError) \
                as cm:
            bundle_mod.create_todo(
                self.plans, self.bundle, "Born doing",
                status="doing")
        self.assertIn("Complete when", str(cm.exception))

    def test_incomplete_contract_does_not_gate_unarmed_work(
            self):
        self.incomplete_contract(blank="Objective")
        # Creating unarmed, and arming's explicit
        # opt-out, are not arms — neither is gated.
        todo = bundle_mod.create_todo(
            self.plans, self.bundle, "Quiet task")
        self.assertEqual(todo["status"], "todo")
        moved = bundle_mod.set_todo_status(
            self.plans, todo["id"], "doing",
            no_progress=True)
        self.assertEqual(moved["progress_check"], "off")


if __name__ == "__main__":
    unittest.main()
