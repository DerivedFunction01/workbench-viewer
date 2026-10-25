"""Repo-home backend over real HTTP, part 2: GET /api/home
and GET /api/projects/<slug>/worktrees against a fixture
project that is a real git repo with a second worktree.
(Message endpoints: test_server_repo_home.py.)
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

from lib import registry as reg

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def git(cwd, *args):
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if out.returncode != 0:
        raise AssertionError(out.stderr)


class HomeServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-rh2-"))
        ws = cls.tmp / "ws"
        root = ws / "alpha"
        (root / "workbench").mkdir(parents=True)
        (root / ".plans").mkdir()
        (root / "workbench.yaml").write_text(
            "name: Alpha\n"
            "registry: workbench/registry.db\n"
            "plans: .plans\n", encoding="utf-8")
        reg.init_registry(root / "workbench" / "registry.db")
        (root / ".plans" / "2026-10-25-p.md").write_text(
            "# P\n\nStatus: in progress\n\n## Steps\n\n"
            "1. **S.** Do.\n", encoding="utf-8")
        (root / "a.txt").write_text("a\n")
        git(root, "init", "-b", "main")
        git(root, "add", ".")
        git(root, "commit", "-m", "base")
        cls.wt_path = cls.tmp / "wt-x"
        git(root, "worktree", "add", "-b", "build/x",
            str(cls.wt_path))
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
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
                status, _ = cls.req_raw("GET", "/health")
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


class TestHomeEndpoints(HomeServerCase):
    def test_home_feed(self):
        status, out = self.req("GET", "/api/home")
        self.assertEqual(status, 200)
        self.assertEqual(len(out["projects"]), 1)
        row = out["projects"][0]
        self.assertEqual(row["slug"], "alpha")
        self.assertEqual(row["git"]["branch"], "main")
        self.assertEqual(
            row["plans"]["in_progress"]["title"], "P")
        self.assertTrue(row["has_extra_worktrees"])
        branches = {w["branch"] for w in row["worktrees"]}
        self.assertEqual(branches, {"main", "build/x"})

    def test_worktrees_endpoint(self):
        status, out = self.req(
            "GET", "/api/projects/alpha/worktrees")
        self.assertEqual(status, 200)
        self.assertTrue(out["available"])
        by_branch = {w["branch"]: w
                     for w in out["worktrees"]}
        self.assertEqual(by_branch["build/x"]["base"],
                         "main")
        self.assertFalse(by_branch["build/x"]["dirty"])
        status, _ = self.req(
            "GET", "/api/projects/nope/worktrees")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
