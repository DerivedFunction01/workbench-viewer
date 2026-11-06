"""Fingerprint-keyed feed cache gate tests
(cache-refresh plan Step 2): the server over real HTTP,
launched through run.py exactly as systemd launches it,
against a fixture workspace holding two manifest
projects whose .plans corpora are built through the lib
writer (production §3.2 shape).

Proves: with an unchanged fingerprint the todos, plans,
and board feeds serve the cached payload (captured_at
unmoved — no recompute); an external write in one
project's corpus recomputes exactly that project's
feeds (the other's captured_at never moves); and
POST /api/refresh busts every cache, so the next reads
re-derive despite unchanged fingerprints. The fixture
runs sweep_ttl_s 0, so fingerprints re-derive on every
sweep read and the only thing standing between a write
and a recompute is the keyed cache itself.
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

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"

import sys  # noqa: E402

sys.path.insert(0, str(REPO))

from lib import bundles as bundle_mod  # noqa: E402


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        check=True, capture_output=True, text=True)


def make_project(ws: Path, name: str) -> Path:
    root = ws / name
    (root / ".plans").mkdir(parents=True)
    (root / "workbench.yaml").write_text(
        f"name: {name}\nslug: {name}\n"
        "registry: workbench/registry.db\nplans: .plans\n"
        "mockups: workbench/entries\n"
        "archive: workbench/archive\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main", ".")
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    plans = root / ".plans"
    bundle_mod.create_bundle(plans, "work", plan=True,
                             today="2026-11-05")
    bundle_mod.create_todo(plans, "work", "First thing")
    return root


class FeedCacheServerCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(
            prefix="wb-feed-cache-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        cls.alpha = make_project(ws, "alpha-proj")
        cls.beta = make_project(ws, "beta-proj")
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
               "sweep_ttl_s": 0, "repos_ttl_s": 3600}
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
                                        timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def get_feed(self, path):
        status, payload = self.req_raw("GET", path)
        self.assertEqual(status, 200)
        return payload

    def wait_for_new_capture(self, path, old_capture):
        """Poll until the feed's captured_at moves (the
        background recompute lands), or fail."""
        deadline = time.time() + 20
        payload = self.get_feed(path)
        while payload["captured_at"] == old_capture:
            if time.time() > deadline:
                self.fail(f"{path} never recomputed")
            time.sleep(0.1)
            payload = self.get_feed(path)
        return payload


class KeyedCacheCase(FeedCacheServerCase):

    def test_todos_cached_then_recompute_on_write(self):
        first = self.get_feed(
            "/api/projects/alpha-proj/todos")
        count_before = len(first["todos"])
        again = self.get_feed(
            "/api/projects/alpha-proj/todos")
        # Unchanged fingerprint: the cached payload
        # serves, captured_at unmoved.
        self.assertEqual(again["captured_at"],
                         first["captured_at"])
        beta_first = self.get_feed(
            "/api/projects/beta-proj/todos")
        # An external write in alpha's corpus only.
        bundle_mod.create_todo(
            self.alpha / ".plans", "work", "Second thing")
        landed = self.wait_for_new_capture(
            "/api/projects/alpha-proj/todos",
            first["captured_at"])
        self.assertEqual(len(landed["todos"]),
                         count_before + 1)
        # Beta's corpus never moved: still the cache.
        beta_again = self.get_feed(
            "/api/projects/beta-proj/todos")
        self.assertEqual(beta_again["captured_at"],
                         beta_first["captured_at"])

    def test_plans_and_board_cached(self):
        plans_first = self.get_feed(
            "/api/projects/alpha-proj/plans")
        plans_again = self.get_feed(
            "/api/projects/alpha-proj/plans")
        self.assertEqual(plans_again["captured_at"],
                         plans_first["captured_at"])
        board_first = self.get_feed(
            "/api/projects/alpha-proj/board")
        board_again = self.get_feed(
            "/api/projects/alpha-proj/board")
        self.assertEqual(board_again["captured_at"],
                         board_first["captured_at"])
        bundle_mod.create_todo(
            self.alpha / ".plans", "work", "Third thing")
        landed = self.wait_for_new_capture(
            "/api/projects/alpha-proj/board",
            board_first["captured_at"])
        self.assertEqual(
            landed["counts"]["todos"]["todo"],
            board_first["counts"]["todos"]["todo"] + 1)


class RefreshCase(FeedCacheServerCase):

    def test_refresh_busts_every_cache(self):
        todos_first = self.get_feed(
            "/api/projects/alpha-proj/todos")
        home_first = self.get_feed("/api/home")
        status, payload = self.req_raw(
            "POST", "/api/refresh")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {
            "ok": True, "projects": 2,
            "invalidated": ["sweep", "home", "repos",
                            "feeds"]})
        # No file changed — the bust alone forces the
        # next reads to re-derive (cold, on the request
        # path: no polling needed).
        todos_after = self.get_feed(
            "/api/projects/alpha-proj/todos")
        self.assertNotEqual(todos_after["captured_at"],
                            todos_first["captured_at"])
        home_after = self.get_feed("/api/home")
        self.assertNotEqual(home_after["captured_at"],
                            home_first["captured_at"])


if __name__ == "__main__":
    unittest.main()
