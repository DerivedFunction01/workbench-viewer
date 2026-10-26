"""Resolvable plan questions over HTTP (plan Step 3):
the plans feed carries the questions list, the single-plan
payload carries questions + file_sha256, and POST
/api/projects/<slug>/plan/resolve writes the answers into
the plan file through the guarded save.

Proves: the happy path writes exactly the composed bytes
(lib apply_answers is the oracle); a stale base is a 409
and leaves the file byte-identical; editing disabled is
a 403; a plan without sentinels rejects resolve; bad
answers and unknown ids are 400s; an unknown plan is a
404."""

import hashlib
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

from lib.plans import parser as plan_parser

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"

PLAN = """# Questions fixture

Status: draft

## Open questions

- [ ] Which store holds the index?
  - Recommendation: the messages store.
  <!-- wb-question
  id=q-store
  type=choice
  options=messages store | registry
  recommended=messages store
  answer=
  -->
- [ ] What name should the new entry kind carry?
  <!-- wb-question
  id=q-kind-name
  type=text
  answer=
  -->
"""

PLAIN_PLAN = """# Plain fixture

Status: draft

## Open questions

- [ ] An ordinary question?
"""


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ResolveServerCase(unittest.TestCase):
    editing = True

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-resolve-"))
        ws = cls.tmp / "ws"
        root = ws / "alpha"
        (root / ".plans").mkdir(parents=True)
        (root / "workbench.yaml").write_text(
            "name: Alpha\nplans: .plans\n", encoding="utf-8")
        (root / ".plans" / "2026-10-25-q.md").write_text(
            PLAN, encoding="utf-8")
        (root / ".plans" / "2026-10-25-plain.md").write_text(
            PLAIN_PLAN, encoding="utf-8")
        cls.plan_path = root / ".plans" / "2026-10-25-q.md"
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

    def setUp(self):
        # Every test starts from the pristine fixture file.
        type(self).plan_path.write_text(PLAN, encoding="utf-8")

    def plan_sha(self) -> str:
        return hashlib.sha256(
            type(self).plan_path.read_bytes()).hexdigest()


class TestPayloads(ResolveServerCase):
    def test_plan_payload_carries_questions_and_sha(self):
        status, doc = self.req(
            "GET", "/api/projects/alpha/plan"
                   "?path=2026-10-25-q.md")
        self.assertEqual(status, 200)
        self.assertEqual(
            [q["id"] for q in doc["questions"]],
            ["q-store", "q-kind-name"])
        self.assertEqual(doc["file_sha256"], self.plan_sha())

    def test_plans_feed_summary_carries_questions(self):
        status, feed = self.req(
            "GET", "/api/projects/alpha/plans")
        self.assertEqual(status, 200)
        by_path = {p["path"]: p for p in feed["plans"]}
        self.assertEqual(
            [q["id"] for q in
             by_path["2026-10-25-q.md"]["questions"]],
            ["q-store", "q-kind-name"])
        self.assertEqual(
            by_path["2026-10-25-plain.md"]["questions"], [])


class TestResolve(ResolveServerCase):
    def resolve(self, answers, base=None, path="2026-10-25-q.md"):
        return self.req(
            "POST", "/api/projects/alpha/plan/resolve",
            {"path": path,
             "base_sha256": self.plan_sha() if base is None
             else base,
             "answers": answers})

    def test_happy_path_writes_exactly_the_composition(self):
        answers = {"q-store": "registry",
                   "q-kind-name": "explainer"}
        status, payload = self.resolve(answers)
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["resolved"],
                         ["q-kind-name", "q-store"])
        expected = plan_parser.apply_answers(PLAN, answers)
        on_disk = type(self).plan_path.read_text(
            encoding="utf-8")
        self.assertEqual(on_disk, expected)
        self.assertEqual(payload["sha256"], self.plan_sha())
        # the fresh payload shows the recorded answers
        status, doc = self.req(
            "GET", "/api/projects/alpha/plan"
                   "?path=2026-10-25-q.md")
        got = {q["id"]: q["answer"] for q in doc["questions"]}
        self.assertEqual(got, answers)
        # one-generation backup holds the pristine source
        backup = Path(payload["backup"])
        self.assertEqual(backup.read_text(encoding="utf-8"),
                         PLAN)

    def test_stale_base_is_409_and_writes_nothing(self):
        before = type(self).plan_path.read_bytes()
        status, payload = self.resolve(
            {"q-store": "registry"}, base="0" * 64)
        self.assertEqual(status, 409)
        self.assertEqual(payload["current_sha256"],
                         self.plan_sha())
        self.assertEqual(type(self).plan_path.read_bytes(),
                         before)

    def test_plan_without_sentinels_rejects_resolve(self):
        status, payload = self.resolve(
            {"q-store": "registry"},
            path="2026-10-25-plain.md")
        self.assertEqual(status, 400)
        self.assertIn("no resolvable", payload["error"])

    def test_unknown_question_and_bad_answer_are_400(self):
        status, _ = self.resolve({"q-nope": "x"})
        self.assertEqual(status, 400)
        status, _ = self.resolve({"q-store": "a third store"})
        self.assertEqual(status, 400)
        self.assertEqual(type(self).plan_path.read_text(
            encoding="utf-8"), PLAN)

    def test_missing_fields_are_400(self):
        status, _ = self.req(
            "POST", "/api/projects/alpha/plan/resolve",
            {"path": "2026-10-25-q.md"})
        self.assertEqual(status, 400)

    def test_unknown_plan_is_404(self):
        status, _ = self.resolve({"q-store": "registry"},
                                 path="2026-10-25-nope.md")
        self.assertEqual(status, 404)


class TestResolveEditingDisabled(ResolveServerCase):
    editing = False

    def test_resolve_is_403_and_writes_nothing(self):
        status, payload = self.req(
            "POST", "/api/projects/alpha/plan/resolve",
            {"path": "2026-10-25-q.md",
             "base_sha256": self.plan_sha(),
             "answers": {"q-store": "registry"}})
        self.assertEqual(status, 403, payload)
        self.assertEqual(type(self).plan_path.read_text(
            encoding="utf-8"), PLAN)


if __name__ == "__main__":
    unittest.main()
