"""Repo-home backend over real HTTP: the /api messages
surface, the guarded cleanup endpoint, and effective
settings — launched through run.py exactly as systemd
launches it, against one fixture project, with the message
store in a temp state dir (config seam, spec D9).

Worktree/home endpoints live in test_server_repo_home2.py.
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


class RepoHomeServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-rh-"))
        ws = cls.tmp / "ws"
        root = ws / "alpha"
        (root / "workbench").mkdir(parents=True)
        (root / ".plans").mkdir()
        (root / "workbench.yaml").write_text(
            "name: Alpha\n"
            "registry: workbench/registry.db\n"
            "plans: .plans\n", encoding="utf-8")
        reg.init_registry(root / "workbench" / "registry.db")
        reg.add_todo(root / "workbench" / "registry.db",
                     "do-thing", "Do the thing")
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


class TestMessagesApi(RepoHomeServerCase):
    def test_message_flow_over_http(self):
        status, out = self.req("POST", "/api/messages", {
            "author": "owner", "body": "please look",
            "project_slug": "alpha", "anchor_type": "plan",
            "anchor_ref": "plan.md", "send": True})
        self.assertEqual(status, 200)
        mid = out["message"]["id"]
        self.assertEqual(out["message"]["state"], "sent")
        # Done before pickup is an illegal transition.
        status, err = self.req(
            "POST", f"/api/messages/{mid}/done", {})
        self.assertEqual(status, 400)
        # Pickup acknowledges (D3).
        status, out = self.req(
            "GET", "/api/messages?project=alpha&pickup=1")
        self.assertEqual(status, 200)
        self.assertEqual(out["picked_up"], 1)
        self.assertEqual(out["messages"][0]["state"],
                         "acknowledged")
        status, out = self.req(
            "GET", "/api/messages?project=alpha&pickup=1")
        self.assertEqual(out["picked_up"], 0)
        # Reply on the thread, then done.
        status, out = self.req("POST", "/api/messages", {
            "author": "Muse", "body": "done it",
            "project_slug": "alpha", "parent_id": mid,
            "send": True})
        self.assertEqual(status, 200)
        status, out = self.req(
            "POST", f"/api/messages/{mid}/done", {})
        self.assertEqual(status, 200)
        self.assertEqual(out["message"]["state"], "done")
        status, out = self.req(
            "GET", "/api/messages?project=alpha")
        states = {m["id"]: m["state"]
                  for m in out["messages"]}
        self.assertEqual(states[mid], "done")

    def test_create_validation(self):
        status, _ = self.req("POST", "/api/messages",
                             {"body": "no author"})
        self.assertEqual(status, 400)
        status, _ = self.req("POST", "/api/messages", {
            "author": "mallory", "body": "x"})
        self.assertEqual(status, 400)
        status, _ = self.req(
            "GET", "/api/messages?state=bogus")
        self.assertEqual(status, 400)
        status, _ = self.req(
            "POST", "/api/messages/abc/done", {})
        self.assertEqual(status, 404)

    def test_cleanup_endpoint_is_guarded(self):
        status, _ = self.req("POST", "/api/messages/cleanup",
                             {})
        self.assertEqual(status, 400)
        status, out = self.req("POST", "/api/messages/cleanup",
                               {"confirm": True})
        self.assertEqual(status, 200)
        self.assertIn("cleanup", out)
        status, out = self.req("POST", "/api/messages/cleanup",
                               {"confirm": True,
                                "purge": "drafts"})
        self.assertEqual(status, 200)
        self.assertIn("purged", out)
        status, _ = self.req("POST", "/api/messages/cleanup",
                             {"confirm": True,
                              "purge": "bogus"})
        self.assertEqual(status, 400)


class TestEffectiveSettings(RepoHomeServerCase):
    def test_effective_settings(self):
        status, out = self.req("GET",
                               "/api/settings/effective")
        self.assertEqual(status, 200)
        self.assertEqual(out["config"]["port"], self.port)
        self.assertEqual(
            out["messages"]["policy"]["draft_ttl_days"], 7)
        self.assertEqual(
            out["messages"]["policy"]["per_project_cap"],
            1000)
        self.assertTrue(
            out["messages"]["db"].endswith("messages.db"))
        # Startup cleanup ran (§5.3) and recorded itself.
        self.assertIsNotNone(
            out["messages"]["last_cleanup_at"])
        self.assertIn("counts", out["messages"])


if __name__ == "__main__":
    unittest.main()
