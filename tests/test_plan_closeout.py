"""Plan closeout enforcement (plan syntax standard,
Closeout section): the bundles feed flags a plan file
whose declared Status contradicts its filing location.
Exactly two contradictions flag — an active plan
declaring complete, and a finished plan declaring
anything other than complete or superseded — each as ONE
bundle error naming the fix. A plan with no Status
header declares nothing and never flags; bundle
directories are not plan files and never flag.

The fixture matrix runs on a scratch .plans tree; the
real-corpus pass runs the same feed over this repo's own
.plans/ (post-2026-10-25 closeout sweep) and requires
zero flags.
"""

import tempfile
import unittest
from pathlib import Path

from lib.plans import bundles
from lib.plans.parser import declared_status

ACTIVE_COMPLETE_MSG = (
    "closeout: Status declares complete, but the plan "
    "is filed under .plans/ — close it out by moving "
    "it to .plans/finished/")


def finished_msg(declared):
    return (
        f"closeout: Status declares {declared}, but "
        f"the plan is filed under .plans/finished/ — "
        f"a finished plan must declare complete or "
        f"superseded: fix the Status line, or move it "
        f"back to .plans/")


def _plan(title, status=None):
    lines = [f"# {title}", ""]
    if status is not None:
        lines.append(f"Status: {status}")
        lines.append("")
    lines.append("Body.")
    return "\n".join(lines) + "\n"


TODO = """---
id: t-01K8Q00000000000000000000C
title: Bundle work
status: doing
created: 2026-10-24
updated: 2026-10-25
---
Work.
"""


def _write(root: Path, rel: str, text: str):
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class TestDeclaredStatus(unittest.TestCase):
    def test_no_header_declares_nothing(self):
        self.assertIsNone(declared_status(None))
        self.assertIsNone(declared_status(""))

    def test_leading_word_with_closeout_parenthetical(self):
        self.assertEqual(
            declared_status(
                "complete (closed 2026-10-25 — shipped)"),
            "complete")
        self.assertEqual(
            declared_status(
                "superseded (closed 2026-10-25 — by x)"),
            "superseded")

    def test_the_standard_vocabulary(self):
        self.assertEqual(declared_status("draft"),
                         "draft")
        self.assertEqual(
            declared_status("approved (the owner, 2026-10-25)"),
            "approved")
        self.assertEqual(declared_status("in progress"),
                         "in progress")
        self.assertEqual(declared_status("completed"),
                         "complete")

    def test_unrecognized_word_is_named_verbatim(self):
        self.assertEqual(
            declared_status(
                "**DETERMINED — for the owner's approval.**"),
            "determined")


class TestCloseoutFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        plans = Path(cls._tmp.name)
        _write(plans, "draft.md", _plan("Draft", "draft"))
        _write(plans, "doing.md",
               _plan("Doing", "in progress"))
        _write(plans, "okayed.md",
               _plan("Okayed", "approved (a ruling)"))
        _write(plans, "done-active.md",
               _plan("Done but active",
                     "complete (closed 2026-10-25 — "
                     "landed, never filed)"))
        _write(plans, "silent-active.md",
               _plan("No header at all"))
        _write(plans, "finished/complete.md",
               _plan("Filed complete",
                     "complete (closed 2026-10-25)"))
        _write(plans, "finished/superseded.md",
               _plan("Filed superseded",
                     "superseded (closed 2026-10-25)"))
        _write(plans, "finished/stale-draft.md",
               _plan("Filed but draft", "draft"))
        _write(plans, "finished/stale-doing.md",
               _plan("Filed but doing", "in progress"))
        _write(plans, "finished/run-record.md",
               _plan("Run record, no header"))
        _write(plans, "2026-10-25-bundle/todos/one.md",
               TODO)
        _write(plans,
               "2026-10-25-planned-bundle/plan.md",
               _plan("Bundle plan", "complete"))
        _write(plans,
               "2026-10-25-planned-bundle/todos/one.md",
               TODO)
        cls.feed = bundles.list_bundles(plans)
        cls.by_id = {b["id"]: b for b in cls.feed}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def errors(self, bundle_id):
        return self.by_id[bundle_id]["errors"]

    def test_active_draft_in_progress_approved_no_flag(self):
        for bundle_id in ("draft.md", "doing.md",
                          "okayed.md"):
            self.assertEqual(self.errors(bundle_id), [],
                             bundle_id)

    def test_active_complete_flags_once_naming_the_fix(self):
        self.assertEqual(
            self.errors("done-active.md"),
            [{"path": "done-active.md",
              "error": ACTIVE_COMPLETE_MSG}])

    def test_active_without_status_header_no_flag(self):
        self.assertEqual(self.errors("silent-active.md"),
                         [])

    def test_finished_complete_and_superseded_no_flag(self):
        self.assertEqual(self.errors("complete.md"), [])
        self.assertEqual(self.errors("superseded.md"), [])

    def test_finished_draft_flags_once_naming_the_fix(self):
        self.assertEqual(
            self.errors("stale-draft.md"),
            [{"path": "finished/stale-draft.md",
              "error": finished_msg("draft")}])

    def test_finished_in_progress_flags(self):
        self.assertEqual(
            self.errors("stale-doing.md"),
            [{"path": "finished/stale-doing.md",
              "error": finished_msg("in progress")}])

    def test_finished_without_status_header_no_flag(self):
        # the build program's run-record shape: filed
        # under finished/ carrying no Status header —
        # it declares nothing and must not flag.
        self.assertEqual(self.errors("run-record.md"), [])

    def test_bundle_directory_no_flag(self):
        self.assertEqual(
            self.errors("2026-10-25-bundle"), [])

    def test_bundle_directory_with_plan_file_no_flag(self):
        # Bundle directories draw no closeout flag even
        # when they carry a plan.md: their state rides
        # their todos, never the plan-file filing rule.
        self.assertEqual(
            self.errors("2026-10-25-planned-bundle"), [])


WS = Path(__file__).resolve().parent.parent.parent
REAL_PLANS = WS / "workbench-viewer" / ".plans"


class TestRealCorpusCloseout(unittest.TestCase):
    def test_viewer_corpus_yields_zero_closeout_flags(self):
        self.assertTrue(REAL_PLANS.is_dir())
        feed = bundles.list_bundles(REAL_PLANS)
        flagged = [
            (e["path"], e["error"]) for b in feed
            for e in b["errors"]
            if e["error"].startswith("closeout:")]
        self.assertEqual(flagged, [])

    def test_the_pass_covers_the_swept_corpus(self):
        # Guard against a vacuous pass: the swept corpus
        # is really there — the finished archive holds
        # the closed plans, the run record among them,
        # and it carries no error at all.
        feed = bundles.list_bundles(REAL_PLANS)
        finished = [b for b in feed if b["archived"]]
        self.assertGreaterEqual(len(finished), 17)
        run_record = next(
            b for b in feed
            if b["id"] == "2026-10-25-viewer-build-08-"
                          "run-record.md")
        self.assertEqual(run_record["errors"], [])


if __name__ == "__main__":
    unittest.main()
