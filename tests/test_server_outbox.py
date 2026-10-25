"""Repo-home spec §15.1 over real HTTP: the outbox poll
endpoint, the draft -> sent route, and the maintenance
loop firing a configured notify command for a message
sent after startup — launched through run.py exactly as
systemd launches it, with the message store in a temp
state dir and the notify target a file-writing command.
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


class OutboxServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-outbox-srv-"))
        ws = cls.tmp / "ws"
        root = ws / "alpha"
        (root / "workbench").mkdir(parents=True)
        (root / ".plans").mkdir()
        (root / "workbench.yaml").write_text(
            "name: Alpha\n"
            "registry: workbench/registry.db\n"
            "plans: .plans\n", encoding="utf-8")
        reg.init_registry(root / "workbench" / "registry.db")
        cls.notify_file = cls.tmp / "notify" / "event.json"
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
               "sweep_ttl_s": 1,
               "messages_notify_poll_s": 5,
               "messages_notify_command":
                   f"mkdir -p {cls.notify_file.parent} && "
                   f"cat > {cls.notify_file}"}
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

    def test_outbox_endpoint_and_notify_firing(self):
        # A draft writes no outbox row; the send route does.
        status, out = self.req("POST", "/api/messages", {
            "author": "owner", "body": "please review\n"
            "the plan", "project_slug": "alpha"})
        self.assertEqual(status, 200)
        mid = out["message"]["id"]
        self.assertEqual(out["message"]["state"], "draft")
        status, out = self.req("GET", "/api/outbox")
        self.assertEqual(status, 200)
        self.assertEqual(out["events"], [])

        status, out = self.req(
            "POST", f"/api/messages/{mid}/send", {})
        self.assertEqual(status, 200)
        self.assertEqual(out["message"]["state"], "sent")

        status, out = self.req("GET", "/api/outbox")
        self.assertEqual(status, 200)
        self.assertEqual(len(out["events"]), 1)
        event = out["events"][0]
        self.assertEqual(event["message_id"], mid)
        self.assertEqual(event["anchor_summary"],
                         "please review")
        self.assertEqual(out["last_id"], event["id"])
        # Poll semantics: after=<id> is the consumer's own
        # checkpoint; reading never consumes.
        status, out = self.req(
            "GET", f"/api/outbox?after={event['id']}")
        self.assertEqual(out["events"], [])
        status, out = self.req("GET", "/api/outbox?after=x")
        self.assertEqual(status, 400)

        # The maintenance loop fires the configured command
        # target for the new row and advances its checkpoint:
        # the event JSON lands on the command's stdin -> file.
        deadline = time.time() + 20
        payload = None
        while time.time() < deadline:
            if self.notify_file.is_file():
                payload = json.loads(
                    self.notify_file.read_text())
                break
            time.sleep(0.25)
        self.assertIsNotNone(
            payload, "notify command never fired")
        self.assertEqual(payload["message_id"], mid)
        self.assertEqual(payload["event"], "sent")
        status, out = self.req(
            "GET", "/api/settings/effective")
        self.assertEqual(
            out["messages"]["notify_checkpoint"], event["id"])
        self.assertEqual(out["messages"]["outbox_rows"], 1)

    def test_send_route_refuses_non_draft(self):
        status, out = self.req("POST", "/api/messages", {
            "author": "Muse", "body": "born sent",
            "send": True})
        mid = out["message"]["id"]
        status, _ = self.req(
            "POST", f"/api/messages/{mid}/send", {})
        self.assertEqual(status, 400)
        # Archive is legal from sent; then send is refused.
        status, out = self.req(
            "POST", f"/api/messages/{mid}/archive", {})
        self.assertEqual(status, 200)
        self.assertEqual(out["message"]["state"], "archived")
        status, _ = self.req(
            "POST", f"/api/messages/{mid}/send", {})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
