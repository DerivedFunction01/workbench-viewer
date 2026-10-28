"""Stale-work warnings over real HTTP: the plans and
todos feeds serve `derived` blocks computed from the
fixture project's birthdates, with the default threshold
(3) and with a config override that lifts it — following
the test_server.py fixture pattern (a real server via
run.py, WB_VIEWER_CONFIG at a fixture config)."""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
from datetime import date
from pathlib import Path

from lib import registry as reg

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"

OLD = "2020-01-06"
TODO_TMPL = """---
id: {todo_id}
title: {title}
status: {status}
created: {created}
updated: {created}
---

Body of {title}.
"""


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_project(ws: Path) -> Path:
    root = ws / "alpha"
    plans = root / ".plans"
    (root / "workbench").mkdir(parents=True)
    plans.mkdir()
    (root / "workbench.yaml").write_text(
        "name: Alpha\n"
        "registry: workbench/registry.db\n"
        "plans: .plans\n"
        "mockups: workbench/entries\n"
        "archive: workbench/archive\n", encoding="utf-8")
    reg.init_registry(root / "workbench" / "registry.db")
    # an old bundle with an old open todo
    todos = plans / f"{OLD}-old-work" / "todos"
    todos.mkdir(parents=True)
    (todos / "01-old-todo.md").write_text(TODO_TMPL.format(
        todo_id="t-0123456789", title="Old open thing",
        status="doing", created=OLD), encoding="utf-8")
    # an old open flat plan, and an old terminal one
    (plans / f"{OLD}-old-plan.md").write_text(
        "# Old plan\n\nStatus: draft\n\n## Steps\n\n"
        "1. One thing.\n", encoding="utf-8")
    (plans / f"{OLD}-done-plan.md").write_text(
        "# Done plan\n\nStatus: complete\n", encoding="utf-8")
    # a fresh bundle + todo, born today
    today = date.today().isoformat()
    fresh = plans / f"{today}-fresh-work" / "todos"
    fresh.mkdir(parents=True)
    (fresh / "01-fresh-todo.md").write_text(TODO_TMPL.format(
        todo_id="t-9876543210", title="Fresh thing",
        status="todo", created=today), encoding="utf-8")
    return root


class StaleFeedCase(unittest.TestCase):
    def start_server(self, extra_cfg):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-stale-"))
        self.addCleanup(shutil.rmtree, self.tmp,
                        ignore_errors=True)
        ws = self.tmp / "ws"
        ws.mkdir()
        make_project(ws)
        self.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": self.port,
               "state_dir": str(self.tmp / "state"),
               "sweep_ttl_s": 1}
        cfg.update(extra_cfg)
        cfg_path = self.tmp / "config.json"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        env = {**os.environ, "WB_VIEWER_CONFIG": str(cfg_path)}
        proc = subprocess.Popen(
            [str(PY), str(REPO / "run.py")], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self._stop, proc)
        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    "server exited early: "
                    + proc.stderr.read().decode()[-2000:])
            try:
                self.get("/api/health")
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not come up")

    @staticmethod
    def _stop(proc):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())

    def test_default_threshold_flags_old_open_work(self):
        self.start_server({})
        plans = self.get("/api/projects/alpha/plans")
        self.assertEqual(plans["stale_warning_days"], 3)
        by_path = {p["path"]: p for p in plans["plans"]}
        old_plan = by_path[f"{OLD}-old-plan.md"]
        self.assertGreater(old_plan["derived"]["age_days"], 3)
        self.assertTrue(old_plan["derived"]["stale"])
        # terminal plans never flag, however old
        done_plan = by_path[f"{OLD}-done-plan.md"]
        self.assertGreater(done_plan["derived"]["age_days"], 3)
        self.assertFalse(done_plan["derived"]["stale"])
        bundles = {b["id"]: b for b in plans["bundles"]}
        old_bundle = bundles[f"{OLD}-old-work"]
        self.assertTrue(old_bundle["derived"]["stale"])
        old_todo = old_bundle["todos"][0]
        self.assertTrue(old_todo["derived"]["stale"])
        fresh = [b for b in plans["bundles"]
                 if b["id"].endswith("-fresh-work")][0]
        self.assertEqual(fresh["todos"][0]["derived"],
                         {"age_days": 0, "stale": False})
        self.assertFalse(fresh["derived"]["stale"])

        todos = self.get("/api/projects/alpha/todos")
        self.assertEqual(todos["stale_warning_days"], 3)
        by_title = {t["title"]: t for t in todos["todos"]}
        self.assertTrue(
            by_title["Old open thing"]["derived"]["stale"])
        self.assertFalse(
            by_title["Fresh thing"]["derived"]["stale"])

        all_todos = self.get("/api/todos")
        self.assertEqual(all_todos["stale_warning_days"], 3)
        by_title = {t["title"]: t for t in all_todos["todos"]}
        self.assertTrue(
            by_title["Old open thing"]["derived"]["stale"])

    def test_config_override_lifts_the_threshold(self):
        self.start_server({"stale_warning_days": 100000})
        plans = self.get("/api/projects/alpha/plans")
        self.assertEqual(plans["stale_warning_days"], 100000)
        by_path = {p["path"]: p for p in plans["plans"]}
        old_plan = by_path[f"{OLD}-old-plan.md"]
        # the age is still served honestly; only the flag lifts
        self.assertGreater(old_plan["derived"]["age_days"], 3)
        self.assertFalse(old_plan["derived"]["stale"])
        bundles = {b["id"]: b for b in plans["bundles"]}
        old_bundle = bundles[f"{OLD}-old-work"]
        self.assertFalse(old_bundle["derived"]["stale"])
        self.assertFalse(
            old_bundle["todos"][0]["derived"]["stale"])
        todos = self.get("/api/projects/alpha/todos")
        by_title = {t["title"]: t for t in todos["todos"]}
        self.assertFalse(
            by_title["Old open thing"]["derived"]["stale"])


if __name__ == "__main__":
    unittest.main()
