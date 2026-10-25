"""Annotations over real HTTP (spec §12): create with a
selection payload, list by anchor, the draft body update
+ send round trip, and the pickup anchor_context — the
server launched through run.py exactly as systemd
launches it, against one fixture project with a real
house-format plan (the re-location target) and a real
registry entry (the component target). The message store
sits in a temp state dir (config seam, spec D9).
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

PLAN = """# Fixture Plan

Status: in progress
Created: 2026-10-25

## Steps

1. **Compare against the checkpoint.** First compare the
   result against the checkpoint recorded at the previous
   seal. Anything that moved since the checkpoint is
   listed, not silently carried into the seal. Only when
   the list is empty does the step close.
   files: lib/seal.py
   verify: the comparison report prints
   done when: the step closes on an empty list

2. **Publish the report.** The report is published to the
   library.
   files: lib/report.py
   verify: the library lists the report
   done when: the report is live
"""

QUOTE = ("Anything that moved since the checkpoint is "
         "listed, not silently carried into the seal.")

TEXT_SELECTION = {
    "kind": "text",
    "component_id": "plans/step-1",
    "component_label": "Step 1",
    "section_heading": "Steps",
    "quote": QUOTE,
    "prefix": "seal. ",
    "suffix": " Only when",
}

COMPONENT_SELECTION = {
    "kind": "component",
    "component_id": "summary/bars-by-year",
    "component_label": "chart · bars-by-year",
    "entry_id": "bars-entry",
}


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class AnnotationServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-ann-"))
        ws = cls.tmp / "ws"
        cls.root = ws / "alpha"
        (cls.root / "workbench" / "entries").mkdir(
            parents=True)
        (cls.root / "workbench" / "archive").mkdir()
        (cls.root / ".plans").mkdir()
        (cls.root / "workbench.yaml").write_text(
            "name: Alpha\n"
            "registry: workbench/registry.db\n"
            "plans: .plans\n"
            "mockups: workbench/entries\n"
            "archive: workbench/archive\n",
            encoding="utf-8")
        cls.plan_path = cls.root / ".plans" / "plan.md"
        cls.write_plan(PLAN)
        db = cls.root / "workbench" / "registry.db"
        reg.init_registry(db)
        layout = (cls.root / "workbench" / "entries",
                  cls.root / "workbench" / "archive")
        reg.add_entry(db, layout, "bars-entry",
                      title="Bars")
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
    def write_plan(cls, text):
        cls.plan_path.write_text(text, encoding="utf-8")

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

    def create_annotation(self, **over):
        body = {"author": "owner", "body": "a comment",
                "project_slug": "alpha",
                "anchor_type": "text",
                "anchor_ref": "plan.md",
                "selection": dict(TEXT_SELECTION)}
        body.update(over)
        status, out = self.req("POST", "/api/messages",
                               body)
        self.assertEqual(status, 200, out)
        return out["message"]


class TestAnnotationApi(AnnotationServerCase):
    def test_create_and_anchor_filters(self):
        m = self.create_annotation()
        self.assertEqual(m["state"], "draft")
        self.assertEqual(m["selection"], TEXT_SELECTION)
        plain = self.req("POST", "/api/messages", {
            "author": "owner", "body": "plain note",
            "project_slug": "alpha",
            "anchor_type": "plan",
            "anchor_ref": "plan.md"})[1]["message"]
        self.assertIsNone(plain["selection"])
        # anchor_ref filter: only this plan's messages.
        status, out = self.req(
            "GET", "/api/messages?anchor_ref=plan.md")
        ids = {row["id"] for row in out["messages"]}
        self.assertIn(m["id"], ids)
        self.assertIn(plain["id"], ids)
        status, out = self.req(
            "GET", "/api/messages?anchor_ref=other.md")
        self.assertEqual(out["messages"], [])
        # anchor_type filter separates annotations from
        # plain anchored messages on the same ref.
        status, out = self.req(
            "GET", "/api/messages?anchor_ref=plan.md"
                   "&anchor_type=text")
        ids = {row["id"] for row in out["messages"]}
        self.assertEqual(ids, {m["id"]})
        status, out = self.req(
            "GET", "/api/messages?anchor_type=bogus")
        self.assertEqual(status, 400)

    def test_offset_key_refused_over_http(self):
        bad = dict(TEXT_SELECTION, offset=4)
        status, out = self.req("POST", "/api/messages", {
            "author": "owner", "body": "x",
            "project_slug": "alpha", "anchor_type": "text",
            "anchor_ref": "plan.md", "selection": bad})
        self.assertEqual(status, 400)
        self.assertIn("offset", out["error"])

    def test_draft_body_update_and_send_round_trip(self):
        m = self.create_annotation(body="first thought")
        mid = m["id"]
        status, out = self.req(
            "POST", f"/api/messages/{mid}/body",
            {"body": "refined thought"})
        self.assertEqual(status, 200)
        self.assertEqual(out["message"]["body"],
                         "refined thought")
        self.assertEqual(out["message"]["state"], "draft")
        self.assertGreaterEqual(out["message"]["updated_at"],
                                m["updated_at"])
        # A non-string body is refused.
        status, _ = self.req(
            "POST", f"/api/messages/{mid}/body",
            {"body": 42})
        self.assertEqual(status, 400)
        # Send walks draft -> sent; body is then frozen and
        # a second send is refused.
        status, out = self.req(
            "POST", f"/api/messages/{mid}/send", {})
        self.assertEqual(status, 200)
        self.assertEqual(out["message"]["state"], "sent")
        status, _ = self.req(
            "POST", f"/api/messages/{mid}/body",
            {"body": "too late"})
        self.assertEqual(status, 400)
        status, _ = self.req(
            "POST", f"/api/messages/{mid}/send", {})
        self.assertEqual(status, 400)

    def test_component_annotation_round_trip(self):
        status, out = self.req("POST", "/api/messages", {
            "author": "owner", "body": "wrong chart",
            "project_slug": "alpha",
            "anchor_type": "component",
            "anchor_ref": "bars-entry",
            "selection": dict(COMPONENT_SELECTION),
            "send": True})
        self.assertEqual(status, 200)
        self.assertEqual(out["message"]["selection"],
                         COMPONENT_SELECTION)
        status, out = self.req(
            "GET", "/api/messages?anchor_ref=bars-entry"
                   "&anchor_type=component")
        self.assertEqual(len(out["messages"]), 1)


class TestPickupAnchorContext(AnnotationServerCase):
    """Step 7: reads carry the derived anchor_context —
    the pickup payload is the agent's work order (§13)."""

    def list_context(self, message_id, **params):
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        status, out = self.req("GET", f"/api/messages?{qs}")
        self.assertEqual(status, 200, out)
        for row in out["messages"]:
            if row["id"] == message_id:
                return row.get("anchor_context")
        self.fail(f"message {message_id} not listed")

    def test_pickup_carries_located_context(self):
        m = self.create_annotation(send=True)
        status, out = self.req(
            "GET", "/api/messages?pickup=1&project=alpha")
        self.assertEqual(status, 200, out)
        mine = [r for r in out["messages"]
                if r["id"] == m["id"]]
        self.assertEqual(len(mine), 1)
        # The fetch acknowledged it (pickup is the act).
        self.assertEqual(mine[0]["state"], "acknowledged")
        ctx = mine[0]["anchor_context"]
        self.assertEqual(ctx["kind"], "text")
        self.assertEqual(ctx["status"], "located")
        self.assertTrue(ctx["relocated"])
        self.assertEqual(ctx["step"], 1)
        self.assertEqual(ctx["section_heading"], "Steps")
        self.assertFalse(ctx["component_missing"])
        self.assertIn(
            "Anything that moved since the checkpoint is",
            ctx["excerpt"])

    def test_context_orphan_after_quote_edited_away(self):
        m = self.create_annotation()
        edited = PLAN.replace(
            "Anything that moved since the checkpoint is\n"
            "   listed, not silently carried into the seal.",
            "The moved items are printed.")
        self.assertNotEqual(edited, PLAN)
        type(self).write_plan(edited)
        try:
            ctx = self.list_context(m["id"],
                                    anchor_ref="plan.md")
        finally:
            type(self).write_plan(PLAN)
        self.assertEqual(ctx["status"], "orphan")
        self.assertFalse(ctx["relocated"])
        # The stored quote survives — anchor-moved is
        # shown, never dropped.
        self.assertEqual(ctx["quote"], QUOTE)
        self.assertIsNone(ctx["excerpt"])

    def test_component_context_present_and_moved(self):
        status, out = self.req("POST", "/api/messages", {
            "author": "owner", "body": "wrong chart",
            "project_slug": "alpha",
            "anchor_type": "component",
            "anchor_ref": "bars-entry",
            "selection": dict(COMPONENT_SELECTION),
            "send": True})
        self.assertEqual(status, 200, out)
        mid = out["message"]["id"]
        mock = (type(self).root / "workbench" / "entries"
                / "bars-entry" / "mock.html")
        # The component was renamed in the exhibit: its
        # data-anchor no longer exists in the main file.
        mock.write_text(
            '<figure data-anchor="summary/other-chart">'
            "</figure>", encoding="utf-8")
        ctx = self.list_context(
            mid, anchor_ref="bars-entry",
            anchor_type="component")
        self.assertEqual(ctx["kind"], "component")
        self.assertFalse(ctx["present"])
        self.assertEqual(ctx["status"], "anchor moved")
        # The stored label snapshot still says what it was.
        self.assertEqual(ctx["component_label"],
                         "chart · bars-by-year")
        self.assertEqual(ctx["entry_title"], "Bars")
        # Restored under its id: present again.
        mock.write_text(
            '<figure data-anchor="summary/bars-by-year">'
            "</figure>", encoding="utf-8")
        ctx = self.list_context(
            mid, anchor_ref="bars-entry",
            anchor_type="component")
        self.assertTrue(ctx["present"])
        self.assertEqual(ctx["status"], "present")


if __name__ == "__main__":
    unittest.main()
