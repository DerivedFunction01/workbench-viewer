"""API route unification conformance (release N+1): the
legacy aliases are REMOVED. The server carries no alias
map and no canonicalization pass; every former legacy
pattern returns the router's own 404 over HTTP while its
canonical counterpart still succeeds, and the
served-without-alias tripwire now covers every stripped
candidate with no exclusions.

Release N's frozen alias inventory survives below only as
the 404 proof matrix: the 15 patterns that were unified,
each of which must stay dead.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "server"))

from lib import bundles as bundle_mod  # noqa: E402
from lib import registry as reg  # noqa: E402

import server as server_mod  # noqa: E402

# The 15 patterns unified in release N: (method, former
# legacy segments, canonical segments). In release N this
# list mirrored server.LEGACY_ROUTE_ALIASES exactly; Step 8
# removed the server map, and the list is now only the
# record of what must stay dead.
FORMER_LEGACY_PATTERNS = [
    ("GET", ("health",), ("api", "health")),
    ("GET", ("config",), ("api", "config")),
    ("GET", ("projects",), ("api", "projects")),
    ("GET", ("board",), ("api", "board")),
    ("GET", ("todos",), ("api", "todos")),
    ("GET", ("projects", "<slug>", "mockups"),
     ("api", "projects", "<slug>", "mockups")),
    ("GET", ("projects", "<slug>", "plans"),
     ("api", "projects", "<slug>", "plans")),
    ("GET", ("projects", "<slug>", "plan"),
     ("api", "projects", "<slug>", "plan")),
    ("GET", ("projects", "<slug>", "todos"),
     ("api", "projects", "<slug>", "todos")),
    ("GET", ("projects", "<slug>", "entries", "<entry_id>"),
     ("api", "projects", "<slug>", "entries", "<entry_id>")),
    ("GET", ("projects", "<slug>", "entries", "<entry_id>",
             "file"),
     ("api", "projects", "<slug>", "entries", "<entry_id>",
      "file")),
    ("POST", ("projects", "rescan"),
     ("api", "projects", "rescan")),
    ("POST", ("projects", "<slug>", "todos"),
     ("api", "projects", "<slug>", "todos")),
    ("POST", ("projects", "<slug>", "entries", "<entry_id>",
              "action"),
     ("api", "projects", "<slug>", "entries", "<entry_id>",
      "action")),
    ("POST", ("projects", "<slug>", "entries", "<entry_id>",
              "file"),
     ("api", "projects", "<slug>", "entries", "<entry_id>",
      "file")),
]

# The 12 patterns that were already canonical before the
# unification pass; they never had legacy forms.
PRE_EXISTING_API = [
    ("GET", ("api", "home")),
    ("GET", ("api", "projects", "<slug>", "worktrees")),
    ("GET", ("api", "projects", "<slug>", "diff")),
    ("GET", ("api", "messages")),
    ("POST", ("api", "messages")),
    ("POST", ("api", "messages", "cleanup")),
    ("POST", ("api", "messages", "<message_id>", "body")),
    ("POST", ("api", "messages", "<message_id>", "done")),
    ("POST", ("api", "messages", "<message_id>", "send")),
    ("POST", ("api", "messages", "<message_id>", "archive")),
    ("GET", ("api", "outbox")),
    ("GET", ("api", "settings", "effective")),
]

CANONICAL_PATTERNS = (
    [(method, canonical)
     for method, _, canonical in FORMER_LEGACY_PATTERNS]
    + PRE_EXISTING_API)

SAMPLE = {"<slug>": "alpha", "<entry_id>": "tile-a",
          "<message_id>": "1"}


def instantiate(pattern, sample=None):
    values = {**SAMPLE, **(sample or {})}
    return [values.get(segment, segment) for segment in pattern]


def path_of(pattern, sample=None):
    return "/" + "/".join(instantiate(pattern, sample))


class TestAliasMachineryRemoved(unittest.TestCase):
    """The expected alias inventory is empty by
    construction: the server module exposes no alias map
    and no canonicalization pass, under either name."""

    def test_server_has_no_alias_map(self):
        self.assertFalse(
            hasattr(server_mod, "LEGACY_ROUTE_ALIASES"))

    def test_server_has_no_canonicalization_pass(self):
        self.assertFalse(hasattr(server_mod, "_canonicalize"))
        source = (REPO / "server" / "server.py").read_text(
            encoding="utf-8")
        self.assertNotIn("LEGACY_ROUTE_ALIASES", source)
        self.assertNotIn("_canonicalize", source)


PLAN = """# Fixture plan

Status: draft

## Steps

1. **First step.** Do the first thing.
   files: a.py
   verify: run it
   done when: it works
"""

MOCK = ('<style>:root{--ink:#111}</style>'
        '<h1 style="color:var(--ink)">A</h1>\n')


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class RouteServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-routes-"))
        ws = cls.tmp / "ws"
        root = ws / "alpha"
        (root / "workbench").mkdir(parents=True)
        (root / ".plans").mkdir()
        (root / "workbench.yaml").write_text(
            "name: Alpha\n"
            "registry: workbench/registry.db\n"
            "plans: .plans\n"
            "mockups: workbench/entries\n"
            "archive: workbench/archive\n", encoding="utf-8")
        db = root / "workbench" / "registry.db"
        reg.init_registry(db)
        layout = (root / "workbench" / "entries",
                  root / "workbench" / "archive")
        entry = reg.add_entry(db, layout, "tile-a",
                              title="Tile A")
        main = Path(entry["entry_dir"]) / "mock.html"
        main.write_text(MOCK, encoding="utf-8")
        reg.verify_entry(db, "tile-a", accept_drift=True)
        bundle_mod.create_bundle(root / ".plans",
                                 "fixture-work",
                                 today="2026-10-25")
        bundle_mod.create_todo(root / ".plans", "fixture-work",
                               "Do the thing")
        (root / ".plans" / "2026-10-25-fixture-plan.md"
         ).write_text(PLAN, encoding="utf-8")
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


class TestFormerLegacyPaths404(RouteServerCase):
    """Every former legacy pattern is dead: the router's
    own 404, never a handler response — while its canonical
    counterpart still reaches its handler."""

    def assert_router_404(self, method, path, body=None):
        status, payload = self.req(method, path, body)
        self.assertEqual(status, 404)
        self.assertTrue(
            payload.get("error", "").startswith("no route"),
            f"{method} {path} reached a handler: {payload!r}")

    def assert_canonical_ok(self, method, path, body=None):
        status, _ = self.req(method, path, body)
        self.assertEqual(status, 200)

    def assert_canonical_reached(self, method, path,
                                 body=None):
        # The handler answered — possibly with a refusal —
        # rather than the router's "no route" 404.
        status, payload = self.req(method, path, body)
        self.assertFalse(
            status == 404
            and payload.get("error", "").startswith("no route"),
            f"{method} {path} did not reach its handler: "
            f"{status} {payload!r}")

    def test_collection_gets(self):
        for canonical, legacy in [
                ("/api/health", "/health"),
                ("/api/config", "/config"),
                ("/api/projects", "/projects"),
                ("/api/board", "/board"),
                ("/api/todos", "/todos")]:
            with self.subTest(path=legacy):
                self.assert_canonical_ok("GET", canonical)
                self.assert_router_404("GET", legacy)

    def test_parameterized_gets(self):
        plan_q = "?path=2026-10-25-fixture-plan.md"
        for canonical, legacy in [
                ("/api/projects/alpha/mockups",
                 "/projects/alpha/mockups"),
                ("/api/projects/alpha/plans",
                 "/projects/alpha/plans"),
                ("/api/projects/alpha/plan" + plan_q,
                 "/projects/alpha/plan" + plan_q),
                ("/api/projects/alpha/todos",
                 "/projects/alpha/todos"),
                ("/api/projects/alpha/entries/tile-a",
                 "/projects/alpha/entries/tile-a"),
                ("/api/projects/alpha/entries/tile-a/file"
                 "?path=mock.html",
                 "/projects/alpha/entries/tile-a/file"
                 "?path=mock.html")]:
            with self.subTest(path=legacy):
                self.assert_canonical_ok("GET", canonical)
                self.assert_router_404("GET", legacy)

    def test_posts(self):
        self.assert_canonical_ok("POST", "/api/projects/rescan")
        self.assert_router_404("POST", "/projects/rescan")
        # Invalid verbs are refused by the canonical handler
        # without changing state; the legacy path reaches
        # nothing at all.
        self.assert_canonical_reached(
            "POST", "/api/projects/alpha/todos",
            {"verb": "bogus"})
        self.assert_router_404(
            "POST", "/projects/alpha/todos", {"verb": "bogus"})
        self.assert_canonical_reached(
            "POST",
            "/api/projects/alpha/entries/tile-a/action",
            {"verb": "bogus"})
        self.assert_router_404(
            "POST",
            "/projects/alpha/entries/tile-a/action",
            {"verb": "bogus"})
        # Editing is disabled in this fixture: the canonical
        # save route refuses (403) and writes nothing; the
        # legacy path is a router 404.
        peek_status, peek = self.req(
            "GET",
            "/api/projects/alpha/entries/tile-a/file"
            "?path=mock.html")
        self.assertEqual(peek_status, 200)
        save = {"path": "mock.html", "content": "changed",
                "base_sha256": peek["sha256"]}
        status, _ = self.req(
            "POST",
            "/api/projects/alpha/entries/tile-a/file", save)
        self.assertEqual(status, 403)
        self.assert_router_404(
            "POST",
            "/projects/alpha/entries/tile-a/file", save)

    def test_near_misses_stay_404(self):
        # The release N matcher's old negative space —
        # changed literals, missing or extra segments,
        # swapped methods — was never routed and stays
        # unrouted now that the matcher itself is gone.
        for method, path in [
                ("GET", "/healthz"),
                ("GET", "/projects/alpha/mockup"),
                ("POST", "/projects/rescans"),
                ("GET", "/projects/alpha"),
                ("POST", "/projects"),
                ("GET", "/health/x"),
                ("GET", "/projects/alpha/mockups/x"),
                ("POST", "/health"),
                ("GET", "/projects/rescan"),
                ("POST", "/board")]:
            with self.subTest(method=method, path=path):
                self.assert_router_404(method, path)


class TestServedWithoutAliasTripwire(RouteServerCase):
    """Legacy-shaped candidates derived by stripping /api
    from every canonical pattern: with the aliases removed
    there are no exclusions — every candidate must be the
    router's own 'no route' 404. A candidate that reaches a
    handler answers with a different status or a handler
    error body, so a route ever served outside the canonical
    namespace fails here. Mutation probes use invalid
    inputs, so even a failure of this guard changes no
    state."""

    def test_no_route_served_without_alias(self):
        probed = 0
        for method, canonical in CANONICAL_PATTERNS:
            legacy = tuple(canonical[1:])
            probed += 1
            path = path_of(legacy)
            body = None
            if canonical == ("api", "messages"):
                body = {"author": "Muse",
                        "body": "tripwire probe — must 404"}
                path = "/messages"
            if canonical == ("api", "outbox"):
                path = "/outbox?after=0"
            with self.subTest(method=method, path=path):
                status, payload = self.req(method, path, body)
                self.assertEqual(status, 404)
                self.assertTrue(
                    payload.get("error", "").startswith(
                        "no route"),
                    f"{method} {path} reached a handler: "
                    f"{payload!r}")
        # All 27 canonical patterns strip to a candidate —
        # the 15 unified patterns included, now that their
        # aliases are gone.
        self.assertEqual(probed, len(CANONICAL_PATTERNS))


# A legacy route literal in caller source: a quote directly
# before a legacy first segment, bounded by a quote, slash,
# query, or template marker. Canonical paths put the quote
# before /api and never match.
LEGACY_LITERAL_RE = re.compile(
    r"[\"'`]/(?:health|config|projects|todos|board)"
    r"(?=[\"'`/?$])")


class TestControlledCallerScan(unittest.TestCase):
    """Controlled callers speak canonical paths only: the
    bridge actions carry no legacy route literal, and the
    healthcheck has no legacy literal at all since Step 8
    removed its bounded release N fallback."""

    def test_bridge_actions_have_no_legacy_literal(self):
        source = (REPO / "viewer" / "server" / "src"
                  / "actions.ts").read_text(encoding="utf-8")
        self.assertEqual(LEGACY_LITERAL_RE.findall(source),
                         [])

    def test_healthcheck_has_no_legacy_literal(self):
        source = (REPO / "server" / "healthcheck.py").read_text(
            encoding="utf-8")
        self.assertEqual(LEGACY_LITERAL_RE.findall(source),
                         [])
        self.assertIn('"/api/health"', source)


if __name__ == "__main__":
    unittest.main()
