"""API route unification conformance (release N): the
frozen legacy-alias inventory, the exact canonicalization
matcher, canonical/alias HTTP equivalence, and the
served-without-alias tripwire.

The alias inventory below INTENTIONALLY duplicates
server/server.py's LEGACY_ROUTE_ALIASES: changing or
deleting one server entry must fail this suite. Aliases
live for exactly one published checkpoint cycle; Step 8
of the unification plan empties this inventory and turns
the equivalence tests into 404 proofs.
"""

import json
import os
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

# The frozen inventory: (method, legacy segments, canonical
# segments). Mirrors server.LEGACY_ROUTE_ALIASES exactly.
EXPECTED_ALIASES = [
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

# The 12 patterns that were already canonical before this
# pass; they never had legacy forms.
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
     for method, _, canonical in EXPECTED_ALIASES]
    + PRE_EXISTING_API)

SAMPLE = {"<slug>": "alpha", "<entry_id>": "tile-a",
          "<message_id>": "1"}


def instantiate(pattern, sample=None):
    values = {**SAMPLE, **(sample or {})}
    return [values.get(segment, segment) for segment in pattern]


def path_of(pattern, sample=None):
    return "/" + "/".join(instantiate(pattern, sample))


class TestAliasInventory(unittest.TestCase):
    def test_server_map_matches_frozen_inventory(self):
        actual = [(method, tuple(legacy), tuple(canonical))
                  for method, legacy, canonical
                  in server_mod.LEGACY_ROUTE_ALIASES]
        self.assertEqual(actual, EXPECTED_ALIASES)

    def test_inventory_is_exactly_fifteen(self):
        self.assertEqual(len(EXPECTED_ALIASES), 15)
        self.assertEqual(
            len(server_mod.LEGACY_ROUTE_ALIASES), 15)


class TestCanonicalize(unittest.TestCase):
    def canon(self, method, parts):
        return server_mod._canonicalize(method, list(parts))

    def test_every_legacy_pattern_rewrites(self):
        for method, legacy, canonical in EXPECTED_ALIASES:
            with self.subTest(method=method, legacy=legacy):
                self.assertEqual(
                    self.canon(method, instantiate(legacy)),
                    instantiate(canonical))

    def test_placeholders_bind_by_position(self):
        parts = self.canon(
            "GET", ["projects", "beta", "entries", "x-9"])
        self.assertEqual(
            parts, ["api", "projects", "beta", "entries",
                    "x-9"])

    def test_every_canonical_pattern_passes_through(self):
        for method, pattern in CANONICAL_PATTERNS:
            with self.subTest(method=method, pattern=pattern):
                parts = instantiate(pattern)
                self.assertEqual(
                    self.canon(method, parts), parts)

    def test_changed_literal_does_not_rewrite(self):
        self.assertEqual(self.canon("GET", ["healthz"]),
                         ["healthz"])
        self.assertEqual(
            self.canon("GET", ["projects", "alpha", "mockup"]),
            ["projects", "alpha", "mockup"])
        self.assertEqual(
            self.canon("POST", ["projects", "rescans"]),
            ["projects", "rescans"])

    def test_missing_segment_does_not_rewrite(self):
        self.assertEqual(self.canon("POST", ["projects"]),
                         ["projects"])  # no bare POST alias
        self.assertEqual(
            self.canon("GET", ["projects", "alpha"]),
            ["projects", "alpha"])
        self.assertEqual(
            self.canon("GET", ["projects", "alpha", "entries"]),
            ["projects", "alpha", "entries"])

    def test_extra_segment_does_not_rewrite(self):
        self.assertEqual(self.canon("GET", ["health", "x"]),
                         ["health", "x"])
        self.assertEqual(
            self.canon(
                "GET", ["projects", "alpha", "mockups", "x"]),
            ["projects", "alpha", "mockups", "x"])

    def test_swapped_method_does_not_rewrite(self):
        self.assertEqual(self.canon("POST", ["health"]),
                         ["health"])
        self.assertEqual(
            self.canon("GET", ["projects", "rescan"]),
            ["projects", "rescan"])
        self.assertEqual(
            self.canon("GET", ["projects", "alpha", "todos"]),
            ["api", "projects", "alpha", "todos"])
        self.assertEqual(
            self.canon("POST", ["board"]), ["board"])


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

# Volatile response fields: equal-route comparisons ignore
# only these (plan: normalize captured_at, health uptime_s).
VOLATILE_KEYS = {"captured_at", "uptime_s"}


def normalize(payload):
    if isinstance(payload, dict):
        return {key: normalize(value)
                for key, value in payload.items()
                if key not in VOLATILE_KEYS}
    if isinstance(payload, list):
        return [normalize(value) for value in payload]
    return payload


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


class TestAliasEquivalence(RouteServerCase):
    """Every legacy pattern answers through its alias with
    the canonical handler's own status and payload."""

    def assert_equivalent(self, method, canonical_path,
                          legacy_path, body=None):
        c_status, c_payload = self.req(method, canonical_path,
                                       body)
        a_status, a_payload = self.req(method, legacy_path,
                                       body)
        self.assertEqual(a_status, c_status)
        self.assertEqual(normalize(a_payload),
                         normalize(c_payload))

    def test_collection_gets(self):
        for canonical, legacy in [
                ("/api/health", "/health"),
                ("/api/config", "/config"),
                ("/api/projects", "/projects"),
                ("/api/board", "/board"),
                ("/api/todos", "/todos")]:
            with self.subTest(path=legacy):
                self.assert_equivalent("GET", canonical, legacy)

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
                self.assert_equivalent("GET", canonical, legacy)

    def test_posts(self):
        self.assert_equivalent("POST", "/api/projects/rescan",
                               "/projects/rescan")
        # Invalid verbs are refused identically without
        # changing state on either path.
        self.assert_equivalent(
            "POST", "/api/projects/alpha/todos",
            "/projects/alpha/todos", {"verb": "bogus"})
        self.assert_equivalent(
            "POST",
            "/api/projects/alpha/entries/tile-a/action",
            "/projects/alpha/entries/tile-a/action",
            {"verb": "bogus"})
        # Editing is disabled in this fixture: the save route
        # refuses identically (403) and writes nothing.
        peek_status, peek = self.req(
            "GET",
            "/api/projects/alpha/entries/tile-a/file"
            "?path=mock.html")
        self.assertEqual(peek_status, 200)
        self.assert_equivalent(
            "POST",
            "/api/projects/alpha/entries/tile-a/file",
            "/projects/alpha/entries/tile-a/file",
            {"path": "mock.html", "content": "changed",
             "base_sha256": peek["sha256"]})


class TestServedWithoutAliasTripwire(RouteServerCase):
    """Legacy-shaped candidates derived by stripping /api
    from every canonical pattern: any candidate outside the
    frozen alias inventory must be a router 404. A candidate
    that reaches a handler answers with a different status
    or a handler error body, never the router's own
    'no route' 404 — so a route ever served without an alias
    entry fails here. Mutation probes use invalid inputs, so
    even a failure of this guard changes no state."""

    def test_no_route_served_without_alias(self):
        alias_keys = {(method, legacy)
                      for method, legacy, _
                      in EXPECTED_ALIASES}
        probed = 0
        for method, canonical in CANONICAL_PATTERNS:
            legacy = tuple(canonical[1:])
            if (method, legacy) in alias_keys:
                continue  # a frozen alias: served on purpose
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
        # The 12 pre-existing /api patterns all strip to a
        # candidate; the 15 unified patterns strip exactly to
        # the alias inventory and are excluded above.
        self.assertEqual(probed, len(PRE_EXISTING_API))


if __name__ == "__main__":
    unittest.main()
