"""Step 4 gate tests: the server over real HTTP, launched
through run.py exactly as systemd launches it, against two
fixture projects.

Proves: every feed answers for two projects; a locked DB in
one project degrades ONLY that project's payload; a wrong-sha
save is a 409 and leaves the file byte-identical; editing
disabled is a 403; a canonical transition without a ruling
via the action endpoint is refused; reconciliation problems
surface in the mockups payload.
"""

import json
import os
import shutil
import socket
import sqlite3
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

PLAN = """# Fixture plan

Status: draft
Created: 2026-10-25

## Steps

1. **First step.** Do the first thing.
   files: a.py
   verify: run it
   done when: it works
2. **Second step.** Do the second thing.
   files: b.py
   verify: run that
   done when: that works
"""

MOCK = ('<style>:root{--ink:#111}</style>'
        '<h1 style="color:var(--ink)">A</h1>\n')


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_project(ws: Path, slug: str, name: str) -> Path:
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
    # a DB todo exists too — the file todos below supersede
    # it (§3.7), so "DB only thing" must never reach a feed
    reg.add_todo(db, "db-only", "DB only thing")
    bundle_mod.create_bundle(root / ".plans", "fixture-work",
                             today="2026-10-25")
    bundle_mod.create_todo(root / ".plans", "fixture-work",
                           "Do the thing")
    bundle_mod.create_todo(root / ".plans", "fixture-work",
                           "Blocked thing", status="blocked")
    bundle_mod.create_bundle(root / ".plans", "fixture-planned",
                             plan=True, today="2026-10-25")
    (root / ".plans" / "2026-10-25-fixture-plan.md").write_text(
        PLAN, encoding="utf-8")
    return root


class ServerCase(unittest.TestCase):
    editing = False

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-server-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        cls.alpha = make_project(ws, "alpha", "Alpha")
        cls.beta = make_project(ws, "beta", "Beta")
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
               "file_editing_enabled": cls.editing,
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
                status, _ = cls.req_raw("GET", "/api/health")
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
    def req_raw(cls, method, path, body=None):
        url = f"http://127.0.0.1:{cls.port}{path}"
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request,
                                        timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def req(self, method, path, body=None):
        return type(self).req_raw(method, path, body)


class TestFeeds(ServerCase):
    def test_health_and_config(self):
        status, health = self.req("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(health["ok"])
        self.assertEqual(health["projects_count"], 2)
        self.assertEqual(health["port"], self.port)
        self.assertTrue(health["config_hash"])
        status, cfg = self.req("GET", "/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(cfg["config"]["port"], self.port)
        self.assertFalse(cfg["config"]["file_editing_enabled"])

    def test_projects_and_rescan(self):
        status, summary = self.req("GET", "/api/projects")
        self.assertEqual(status, 200)
        slugs = {p["slug"] for p in summary["projects"]}
        self.assertEqual(slugs, {"alpha", "beta"})
        alpha = [p for p in summary["projects"]
                 if p["slug"] == "alpha"][0]
        self.assertTrue(alpha["sections"]["mockups"])
        self.assertTrue(alpha["sections"]["plans"])
        status, _ = self.req("POST", "/api/projects/rescan")
        self.assertEqual(status, 200)

    def test_mockups_feed_two_projects(self):
        for slug in ("alpha", "beta"):
            status, feed = self.req(
                "GET", f"/api/projects/{slug}/mockups")
            self.assertEqual(status, 200)
            self.assertTrue(feed["available"])
            self.assertFalse(feed["degraded"])
            self.assertEqual([e["id"] for e in feed["entries"]],
                             ["tile-a"])
            self.assertEqual(feed["reconcile"]["status"], "ok")
            triage_ids = [t["id"] for t in feed["triage"]]
            self.assertIn("tile-a", triage_ids)  # unexplored

    def test_entry_detail(self):
        status, detail = self.req(
            "GET", "/api/projects/alpha/entries/tile-a")
        self.assertEqual(status, 200)
        self.assertEqual(detail["entry"]["id"], "tile-a")
        self.assertIn("derived", detail)
        self.assertIn("approval", detail)
        self.assertTrue(detail["history"])
        self.assertEqual([f["path"] for f in detail["files"]],
                         ["mock.html"])
        status, _ = self.req(
            "GET", "/api/projects/alpha/entries/nope")
        self.assertEqual(status, 404)
        status, _ = self.req("GET", "/api/projects/nope/mockups")
        self.assertEqual(status, 404)

    def test_plans_feed_and_doc(self):
        status, feed = self.req("GET", "/api/projects/alpha/plans")
        self.assertEqual(status, 200)
        self.assertEqual(len(feed["plans"]), 1)
        self.assertEqual(feed["plans"][0]["step_count"], 2)
        # bundles ride the same feed: the fixture bundle with
        # its checklist strip, and the planned bundle's plan
        bundles = {b["id"]: b for b in feed["bundles"]}
        work = bundles["2026-10-25-fixture-work"]
        self.assertEqual(work["todo_count"], 2)
        self.assertEqual(work["open_count"], 2)
        planned = bundles["2026-10-25-fixture-planned"]
        self.assertIsNotNone(planned["plan"])
        status, doc = self.req(
            "GET", "/api/projects/alpha/plan"
                   "?path=2026-10-25-fixture-planned/plan.md")
        self.assertEqual(status, 200)
        self.assertEqual(doc["title"], "Fixture Planned")
        status, doc = self.req(
            "GET", "/api/projects/alpha/plan"
                   "?path=2026-10-25-fixture-plan.md")
        self.assertEqual(status, 200)
        self.assertEqual(doc["step_count"], 2)
        self.assertEqual(doc["status_bucket"], "todo")
        status, _ = self.req(
            "GET", "/api/projects/alpha/plan?path=../workbench.yaml")
        self.assertEqual(status, 404)

    def test_todos_and_board(self):
        status, feed = self.req("GET", "/api/todos")
        self.assertEqual(status, 200)
        projects = {t["project"] for t in feed["todos"]}
        self.assertEqual(projects, {"alpha", "beta"})
        # file todos are the source; the DB todo is superseded
        titles = [t["title"] for t in feed["todos"]]
        self.assertNotIn("DB only thing", titles)
        self.assertEqual(titles.count("Do the thing"), 2)
        self.assertTrue(all(t["bundle"] == "2026-10-25-fixture-work"
                            for t in feed["todos"]))
        status, board = self.req("GET", "/api/board")
        self.assertEqual(status, 200)
        todo_titles = [t["title"]
                       for t in board["todos"]["todo"]]
        self.assertEqual(todo_titles.count("Do the thing"), 2)
        blocked = [t["title"]
                   for t in board["todos"]["blocked"]]
        self.assertEqual(blocked.count("Blocked thing"), 2)
        plan_projects = {p["project"]
                         for p in board["plans"]["todo"]}
        self.assertEqual(plan_projects, {"alpha", "beta"})
        queue_projects = {q["project"]
                          for q in board["review_queue"]}
        self.assertEqual(queue_projects, {"alpha", "beta"})


class TestArtifactsFeed(ServerCase):
    """The Artifacts collection (kind artifact): each
    collection's feed serves only its own kinds — entries
    and triage — and the board's review queue unions both,
    each item carrying its kind, exactly once."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        db = cls.alpha / "workbench" / "registry.db"
        layout = (cls.alpha / "workbench" / "entries",
                  cls.alpha / "workbench" / "archive")
        entry = reg.add_entry(db, layout, "sheet-q",
                              title="Sheet Q", kind="artifact",
                              main_file="index.html")
        main = Path(entry["entry_dir"]) / "index.html"
        main.write_text("<h1>Open questions</h1>\n",
                        encoding="utf-8")
        reg.verify_entry(db, "sheet-q", accept_drift=True)

    def test_artifacts_feed_carries_only_the_artifact(self):
        status, feed = self.req(
            "GET", "/api/projects/alpha/artifacts")
        self.assertEqual(status, 200)
        self.assertTrue(feed["available"])
        self.assertEqual([e["id"] for e in feed["entries"]],
                         ["sheet-q"])
        self.assertEqual(feed["entries"][0]["kind"],
                         "artifact")
        self.assertEqual([t["id"] for t in feed["triage"]],
                         ["sheet-q"])
        self.assertEqual(feed["triage"][0]["kind"],
                         "artifact")

    def test_mockups_feed_excludes_the_artifact(self):
        status, feed = self.req(
            "GET", "/api/projects/alpha/mockups")
        self.assertEqual(status, 200)
        self.assertEqual([e["id"] for e in feed["entries"]],
                         ["tile-a"])
        self.assertEqual([t["id"] for t in feed["triage"]],
                         ["tile-a"])
        self.assertEqual(feed["triage"][0]["kind"], "mockup")

    def test_board_review_queue_unions_both_collections(self):
        status, board = self.req("GET", "/api/board")
        self.assertEqual(status, 200)
        mine = [i for i in board["review_queue"]
                if i["project"] == "alpha"]
        by_id = {i["id"]: i for i in mine}
        self.assertEqual(sorted(by_id), ["sheet-q", "tile-a"])
        self.assertEqual(by_id["sheet-q"]["kind"], "artifact")
        self.assertEqual(by_id["tile-a"]["kind"], "mockup")
        self.assertEqual(
            len([i for i in mine if i["id"] == "sheet-q"]), 1)
        # answered out of triage: a ruling moves it to
        # canonical, and the queue no longer carries it
        db = self.alpha / "workbench" / "registry.db"
        layout = (self.alpha / "workbench" / "entries",
                  self.alpha / "workbench" / "archive")
        reg.set_status(db, "sheet-q", "canonical",
                       ruling="answered", layout=layout)
        status, board = self.req("GET", "/api/board")
        self.assertEqual(status, 200)
        self.assertNotIn("sheet-q", [i["id"] for i in
                                     board["review_queue"]])
        status, feed = self.req(
            "GET", "/api/projects/alpha/artifacts")
        self.assertEqual(feed["triage"], [])


class TestContainment(ServerCase):
    def test_locked_db_degrades_only_that_project(self):
        beta_db = self.beta / "workbench" / "registry.db"
        conn = sqlite3.connect(beta_db)
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute(
                "UPDATE todos SET title = title WHERE 0")
            status, feed = self.req(
                "GET", "/api/projects/beta/mockups")
            self.assertEqual(status, 200)
            self.assertTrue(feed["degraded"])
            self.assertTrue(feed["reason"])
            # the other project is untouched by beta's lock
            status, feed = self.req(
                "GET", "/api/projects/alpha/mockups")
            self.assertEqual(status, 200)
            self.assertFalse(feed["degraded"])
            self.assertEqual(len(feed["entries"]), 1)
        finally:
            conn.rollback()
            conn.close()

    def test_reconcile_banner_for_orphan_folder(self):
        orphan = (self.alpha / "workbench" / "entries"
                  / "orphan-x")
        orphan.mkdir(parents=True)
        try:
            status, feed = self.req(
                "GET", "/api/projects/alpha/mockups")
            self.assertEqual(status, 200)
            self.assertEqual(feed["reconcile"]["status"],
                             "problems")
            self.assertTrue(any(
                "orphan-x" in p["message"]
                for p in feed["reconcile"]["problems"]))
        finally:
            orphan.rmdir()


class TestActions(ServerCase):
    def test_canonical_requires_ruling_via_action(self):
        status, payload = self.req(
            "POST", "/api/projects/alpha/entries/tile-a/action",
            {"verb": "set-status", "status": "canonical"})
        self.assertEqual(status, 400)
        self.assertIn("ruling", payload["error"])
        status, detail = self.req(
            "GET", "/api/projects/alpha/entries/tile-a")
        self.assertEqual(detail["entry"]["status"],
                         "unexplored")

    def test_canonical_with_ruling_and_export_regenerated(self):
        status, detail = self.req(
            "POST", "/api/projects/alpha/entries/tile-a/action",
            {"verb": "set-status", "status": "canonical",
             "ruling": "the owner, 2026-10-25: fixture ruling"})
        self.assertEqual(status, 200)
        self.assertEqual(detail["entry"]["status"], "canonical")
        export_file = (self.alpha / "workbench"
                       / "registry.json")
        self.assertTrue(export_file.is_file())
        self.assertIn('"canonical"',
                      export_file.read_text(encoding="utf-8"))

    def test_review_and_todo_actions(self):
        status, detail = self.req(
            "POST", "/api/projects/beta/entries/tile-a/action",
            {"verb": "review", "disposition": "approve",
             "comment": "looks right"})
        self.assertEqual(status, 200)
        self.assertEqual(
            detail["latest_review"]["payload"]["disposition"],
            "approve")
        self.assertTrue(detail["approval"]["approved"])
        # the board drag path: one set-status mutation on a
        # bundle todo file, through the lib writer
        status, feed = self.req("GET", "/api/projects/beta/todos")
        self.assertEqual(status, 200)
        todo = [t for t in feed["todos"]
                if t["title"] == "Do the thing"][0]
        status, payload = self.req(
            "POST", "/api/projects/beta/todos",
            {"verb": "set-status", "id": todo["id"],
             "status": "doing"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["todo"]["status"], "doing")
        on_disk = (self.beta / ".plans" / todo["path"])
        self.assertIn("status: doing",
                      on_disk.read_text(encoding="utf-8"))
        status, feed = self.req("GET", "/api/projects/beta/todos")
        moved = [t for t in feed["todos"]
                 if t["id"] == todo["id"]][0]
        self.assertEqual(moved["status"], "doing")
        # the retired DB verb and unknown ids are refused
        status, payload = self.req(
            "POST", "/api/projects/beta/todos",
            {"verb": "add", "id": "second-thing",
             "title": "Second thing"})
        self.assertEqual(status, 400)
        status, payload = self.req(
            "POST", "/api/projects/beta/todos",
            {"verb": "set-status", "id": "t-nope",
             "status": "done"})
        self.assertEqual(status, 400)
        status, payload = self.req(
            "POST", "/api/projects/beta/todos",
            {"verb": "bogus"})
        self.assertEqual(status, 400)

    def test_save_refused_when_editing_disabled(self):
        main = (self.alpha / "workbench" / "entries" / "tile-a"
                / "mock.html")
        before = main.read_bytes()
        status, peek = self.req(
            "GET", "/api/projects/alpha/entries/tile-a/file"
                   "?path=mock.html")
        self.assertEqual(status, 200)
        self.assertFalse(peek["editable"])
        status, payload = self.req(
            "POST", "/api/projects/alpha/entries/tile-a/file",
            {"path": "mock.html", "content": "changed",
             "base_sha256": peek["sha256"]})
        self.assertEqual(status, 403)
        self.assertEqual(main.read_bytes(), before)


class TestEditingEnabled(ServerCase):
    editing = True

    def test_wrong_sha_409_and_file_untouched(self):
        main = (self.alpha / "workbench" / "entries" / "tile-a"
                / "mock.html")
        before = main.read_bytes()
        status, payload = self.req(
            "POST", "/api/projects/alpha/entries/tile-a/file",
            {"path": "mock.html", "content": "changed",
             "base_sha256": "0" * 64})
        self.assertEqual(status, 409)
        self.assertTrue(payload["current_sha256"])
        self.assertEqual(main.read_bytes(), before)

    def test_save_round_trip(self):
        status, peek = self.req(
            "GET", "/api/projects/alpha/entries/tile-a/file"
                   "?path=mock.html")
        self.assertEqual(status, 200)
        self.assertTrue(peek["editable"])
        status, payload = self.req(
            "POST", "/api/projects/alpha/entries/tile-a/file",
            {"path": "mock.html",
             "content": peek["content"] + "<!-- v2 -->\n",
             "base_sha256": peek["sha256"]})
        self.assertEqual(status, 200)
        main = (self.alpha / "workbench" / "entries" / "tile-a"
                / "mock.html")
        self.assertIn("<!-- v2 -->",
                      main.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
