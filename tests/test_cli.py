"""Step 2 gate tests: the `wb` CLI walk — the full lifecycle
from the CLI alone (subplan 09 Step 6 verify), for two
fixture projects with no cross-talk; a canonical transition
without --ruling is refused with a nonzero exit."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WB = REPO / "wb"
PY = sys.executable


def make_project(root: Path, name: str):
    root.mkdir(parents=True)
    (root / "workbench.yaml").write_text(
        f"name: {name}\nregistry: workbench/registry.db\n"
        f"plans: .plans\n")
    (root / ".plans").mkdir()
    return root


class CliWalk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        make_project(self.ws / "proj-a", "Project A")
        make_project(self.ws / "proj-b", "Project B")
        self.env = dict(os.environ,
                        WB_VIEWER_SWEEP_ROOTS=str(self.ws))

    def tearDown(self):
        self.tmp.cleanup()

    def wb(self, *argv, expect=0):
        r = subprocess.run([PY, str(WB), *argv],
                           capture_output=True, text=True,
                           env=self.env)
        if expect is not None:
            self.assertEqual(
                r.returncode, expect,
                f"wb {argv} -> {r.returncode}\n{r.stdout}\n"
                f"{r.stderr}")
        return r

    def test_full_lifecycle_two_projects(self):
        p = ("--project", "proj-a")
        self.wb(*p, "init")
        self.wb(*p, "add", "alpha", "--title", "Alpha mock")
        # canonical without a ruling is refused (exit 2)
        r = self.wb(*p, "set-status", "alpha", "canonical",
                    expect=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ruling", r.stderr.lower())
        self.wb(*p, "set-status", "alpha", "canonical",
                "--ruling", "the owner approved")
        self.wb(*p, "add", "alpha-v2", "--title", "Alpha v2")
        self.wb(*p, "supersede", "alpha", "alpha-v2",
                "--ruling", "v2 replaces it")
        self.wb(*p, "archive", "alpha")
        archived_dir = (self.ws / "proj-a" / "workbench"
                        / "archive")
        self.assertTrue(any(archived_dir.rglob("mock.html")))
        self.wb(*p, "unarchive", "alpha")
        self.wb(*p, "verify", "alpha-v2")
        # file todos (spec §3.4 verbs; the legacy DB todo
        # verbs are retired, §3.7)
        self.wb(*p, "bundle", "new", "ship-work",
                "--date", "2026-10-25")
        r = self.wb(*p, "todo", "new", "ship-work", "Ship it")
        ship = json.loads(r.stdout)
        self.wb(*p, "todo", "set", ship["id"], "doing")
        r = self.wb(*p, "todo", "list")
        self.assertIn("Ship it", r.stdout)
        self.assertIn("doing", r.stdout)
        r = self.wb(*p, "todo-add", "x", "retired",
                    expect=None)
        self.assertEqual(r.returncode, 2)
        r = self.wb(*p, "validate")
        self.assertIn("clean", r.stdout)
        # history grew at every step + export is consistent
        r = self.wb(*p, "show", "alpha")
        shown = json.loads(r.stdout)
        verbs = [h["verb"] for h in shown["history"]]
        for expected in ("add", "set-status", "supersede",
                         "archive", "unarchive"):
            self.assertIn(expected, verbs)
        export_file = (self.ws / "proj-a" / "workbench"
                       / "registry.json")
        data = json.loads(export_file.read_text())
        ids = [e["id"] for e in data["entries"]]
        self.assertEqual(sorted(ids), ["alpha", "alpha-v2"])
        # project B untouched by project A's lifecycle
        r = self.wb("--project", "proj-b", "list")
        self.assertIn("no entries", r.stdout)
        r = self.wb("--project", "proj-b", "todo", "list")
        self.assertIn("no file todos", r.stdout)

    def test_projects_lists_sweep(self):
        r = self.wb("projects", "--root", str(self.ws))
        summary = json.loads(r.stdout)
        slugs = [p["slug"] for p in summary["projects"]]
        self.assertEqual(slugs, ["proj-a", "proj-b"])


if __name__ == "__main__":
    unittest.main()
