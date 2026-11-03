"""Board portion gate tests: the server over real HTTP,
launched through run.py exactly as systemd launches it,
against two fixture projects (heavy-feed batching,
2026-11-01).

Proves the board's per-project portion contract: one
call per project instead of the /api/board monolith;
card projections carry only the fields the board cards
render (no bodies, raw markdown, or step lists — those
stay in the section feeds); the done lanes are
paginated with their totals riding along while the open
lanes serve whole; one project's portion never carries
another project's cards.
"""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from lib import bundles as bundle_mod
from lib import registry as reg

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"

MOCK = ('<style>:root{--ink:#111}</style>'
        '<h1 style="color:var(--ink)">A</h1>\n')

DONE_COUNT = 60


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_project(ws: Path, slug: str, name: str,
                 done_history: bool) -> Path:
    root = ws / slug
    (root / "workbench").mkdir(parents=True)
    (root / ".plans").mkdir()
    (root / "workbench.yaml").write_text(
        f"name: {name}\n"
        "registry: workbench/registry.db\n"
        "plans: .plans\n"
        "mockups: workbench/entries\n"
        "archive: workbench/archive\n", encoding="utf-8")
    db = root / "workbench" / "registry.db"
    reg.init_registry(db)
    layout = (root / "workbench" / "entries",
              root / "workbench" / "archive")
    entry = reg.add_entry(db, layout, "tile-a", title="Tile A")
    main = Path(entry["entry_dir"]) / "mock.html"
    main.write_text(MOCK, encoding="utf-8")
    reg.verify_entry(db, "tile-a", accept_drift=True)
    plans = root / ".plans"
    bundle_mod.create_bundle(plans, "fixture-work",
                             today="2026-10-25")
    bundle_mod.create_todo(plans, "fixture-work",
                           "Do the thing")
    bundle_mod.create_todo(plans, "fixture-work",
                           "Blocked thing", status="blocked")
    bundle_mod.create_bundle(plans, "fixture-planned",
                             plan=True, today="2026-10-25")
    if done_history:
        bundle_mod.create_bundle(plans, "done-history",
                                 today="2026-10-25")
        for i in range(DONE_COUNT):
            bundle_mod.create_todo(
                plans, "done-history", f"Done thing {i:02d}",
                status="done", body="history " * 40)
    return root


class BoardPortionCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-board-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        cls.alpha = make_project(ws, "alpha", "Alpha", True)
        cls.beta = make_project(ws, "beta", "Beta", False)
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
               "file_editing_enabled": False,
               "sweep_ttl_s": 1}
        cls.cfg_path = cls.tmp / "config.json"
        cls.cfg_path.write_text(json.dumps(cfg),
                                encoding="utf-8")
        env = {**os.environ,
               "WB_VIEWER_CONFIG": str(cls.cfg_path)}
        cls.proc = subprocess.Popen(
            [str(PY), str(REPO / "run.py")], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 20
        while time.time() < deadline:
            if cls.proc.poll() is not None:
                raise RuntimeError(
                    "server exited early: "
                    + cls.proc.stderr.read().decode()[-2000:])
            try:
                status, _ = cls.req("GET", "/api/health")
                if status == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError("server did not come up")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def req(cls, method, path):
        url = f"http://127.0.0.1:{cls.port}{path}"
        request = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(request,
                                    timeout=30) as resp:
            return resp.status, json.loads(
                resp.read().decode("utf-8"))

    def test_portion_shape_counts_and_review(self):
        status, p = self.req("GET", "/api/projects/alpha/board")
        self.assertEqual(status, 200)
        self.assertEqual(p["slug"], "alpha")
        self.assertEqual(p["counts"]["todos"]["todo"], 1)
        self.assertEqual(p["counts"]["todos"]["blocked"], 1)
        self.assertEqual(p["counts"]["todos"]["done"],
                         DONE_COUNT)
        self.assertEqual(p["counts"]["plans"]["todo"], 1)
        self.assertEqual(p["counts"]["review_queue"], 1)
        self.assertEqual(p["review_queue"][0]["id"], "tile-a")
        self.assertEqual(p["review_queue"][0]["kind"],
                         "mockup")
        todo_titles = [t["title"] for t in p["todos"]["todo"]]
        self.assertEqual(todo_titles, ["Do the thing"])
        blocked = [t["title"] for t in p["todos"]["blocked"]]
        self.assertEqual(blocked, ["Blocked thing"])

    def test_cards_are_projections(self):
        status, p = self.req("GET", "/api/projects/alpha/board")
        self.assertEqual(status, 200)
        cards = (p["todos"]["todo"] + p["todos"]["blocked"]
                 + p["todos"]["done"])
        self.assertTrue(cards)
        for card in cards:
            for heavy in ("body", "markdown",
                          "content_sha256", "fields",
                          "derived"):
                self.assertNotIn(heavy, card)
            self.assertEqual(card["project"], "alpha")
            self.assertEqual(card["project_name"], "Alpha")
            self.assertTrue(card["id"])
            self.assertTrue(card["path"])
        for plan in p["plans"]["todo"]:
            self.assertNotIn("steps", plan)
            self.assertIn("step_count", plan)
            self.assertEqual(plan["bundle"],
                             "2026-10-25-fixture-planned")
        # the section feed still serves the full rows —
        # projection is a board-portion property only
        status, feed = self.req(
            "GET", "/api/projects/alpha/todos")
        self.assertEqual(status, 200)
        done_rows = [t for t in feed["todos"]
                     if t["status"] == "done"]
        self.assertTrue(done_rows)
        self.assertIn("body", done_rows[0])

    def test_done_lanes_paginate_with_totals(self):
        status, p = self.req("GET", "/api/projects/alpha/board")
        self.assertEqual(status, 200)
        # default page = board_done_page (50)
        self.assertEqual(len(p["todos"]["done"]), 50)
        self.assertEqual(p["done_page"],
                         {"offset": 0, "limit": 50})
        first_ids = {t["id"] for t in p["todos"]["done"]}
        status, p2 = self.req(
            "GET", "/api/projects/alpha/board?done_offset=50")
        self.assertEqual(status, 200)
        self.assertEqual(len(p2["todos"]["done"]),
                         DONE_COUNT - 50)
        second_ids = {t["id"] for t in p2["todos"]["done"]}
        self.assertFalse(first_ids & second_ids)
        # totals do not move with the page
        self.assertEqual(p2["counts"]["todos"]["done"],
                         DONE_COUNT)
        status, p3 = self.req(
            "GET",
            "/api/projects/alpha/board?done_limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(len(p3["todos"]["done"]), 5)
        self.assertEqual(p3["done_page"]["limit"], 5)
        # junk paging args degrade to the defaults, never 500
        status, p4 = self.req(
            "GET",
            "/api/projects/alpha/board?done_offset=-3"
            "&done_limit=abc")
        self.assertEqual(status, 200)
        self.assertEqual(p4["done_page"]["offset"], 0)
        self.assertEqual(p4["done_page"]["limit"], 50)

    def test_portions_are_per_project(self):
        status, p = self.req("GET", "/api/projects/beta/board")
        self.assertEqual(status, 200)
        self.assertEqual(p["slug"], "beta")
        self.assertEqual(p["counts"]["todos"]["done"], 0)
        self.assertEqual(p["todos"]["done"], [])
        for lane in p["todos"].values():
            for card in lane:
                self.assertEqual(card["project"], "beta")

    def test_board_monolith_route_is_gone(self):
        # The legacy /api/board monolith was dropped
        # (threadpool plan, step 6): portions are the only
        # board surface.
        url = f"http://127.0.0.1:{self.port}/api/board"
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(url, timeout=30)
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
