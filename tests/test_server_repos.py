"""Absorption routes gate tests: the server over real
HTTP, launched through run.py exactly as systemd launches
it, against a fixture workspace holding one git repo and
one plain directory.

Proves: the census feed serves the repo with its registry
entry attached (and only the repo); status groups, the
file lists and the full tree classify as the reference
did; peek withholds and reveals secrets; the guarded save
round-trips and a stale sha is a 409 carrying the current
sha; the registry update validates; history records.
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


def make_repo(ws: Path, name: str) -> Path:
    root = ws / name
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main", ".")
    (root / ".gitignore").write_text("ignored.log\n",
                                    encoding="utf-8")
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
    git(root, "add", ".gitignore", "a.txt", ".env")
    git(root, "commit", "-q", "-m", "first")
    # Working state: one modified tracked file, one
    # untracked file, one ignored file.
    (root / "a.txt").write_text("alpha\nbeta\n",
                                encoding="utf-8")
    (root / "b.txt").write_text("new\n", encoding="utf-8")
    (root / "ignored.log").write_text("log\n",
                                      encoding="utf-8")
    return root


class ReposServerCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-repos-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        cls.alpha = make_repo(ws, "alpha-repo")
        (ws / "plain-dir").mkdir()
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
               "file_editing_enabled": True,
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

    def test_repos_feed_census_and_registry(self):
        status, payload = self.req("GET", "/api/repos")
        self.assertEqual(status, 200)
        ids = [r["id"] for r in payload["repos"]]
        self.assertEqual(ids, ["alpha-repo"])
        row = payload["repos"][0]
        self.assertEqual(row["branch"], "main")
        self.assertEqual(row["publication"], "local_only")
        self.assertEqual(row["dirty_counts"]["unstaged"], 1)
        self.assertEqual(row["dirty_counts"]["untracked"], 1)
        self.assertIsNotNone(row["registry"])
        self.assertIn(row["registry"]["expected"],
                      ("untracked", "local_ok", "published"))

    def test_status_groups(self):
        status, payload = self.req(
            "GET", "/api/repos/alpha-repo/status")
        self.assertEqual(status, 200)
        self.assertEqual([e["path"] for e in
                          payload["unstaged"]], ["a.txt"])
        self.assertEqual([e["path"] for e in
                          payload["untracked"]], ["b.txt"])
        self.assertEqual(len(payload["commits"]), 1)
        self.assertIn("main", payload["branches"])

    def test_files_and_full_tree(self):
        status, payload = self.req(
            "GET", "/api/repos/alpha-repo/files")
        self.assertEqual(status, 200)
        self.assertIn("a.txt", payload["tracked"])
        self.assertEqual(payload["untracked"], ["b.txt"])
        status, payload = self.req(
            "GET", "/api/repos/alpha-repo/files?all=1")
        self.assertEqual(status, 200)
        kinds = {e["path"]: e["kind"]
                 for e in payload["entries"]}
        self.assertEqual(kinds["ignored.log"], "ignored")
        self.assertEqual(kinds["b.txt"], "untracked")
        self.assertFalse(payload["all_truncated"])
        # The lazy tree's unit: ?dir= (blank = the root)
        # is a directory listing, not the base payload;
        # a missing directory is a 404.
        status, listing = self.req(
            "GET", "/api/repos/alpha-repo/files?dir=")
        self.assertEqual(status, 200)
        self.assertEqual(listing["dir"], "")
        kinds = {e["path"]: e["kind"]
                 for e in listing["entries"]}
        self.assertEqual(kinds["a.txt"], "tracked")
        self.assertEqual(kinds["b.txt"], "untracked")
        self.assertEqual(kinds["ignored.log"], "ignored")
        status, _payload = self.req(
            "GET", "/api/repos/alpha-repo/files?dir=nope")
        self.assertEqual(status, 404)

    def test_peek_withhold_and_reveal(self):
        status, peek = self.req(
            "GET", "/api/repos/alpha-repo/file?path=a.txt")
        self.assertEqual(status, 200)
        self.assertEqual(peek["content"], "alpha\nbeta\n")
        self.assertTrue(peek["editable"])
        self.assertTrue(peek["sha256"])
        status, peek = self.req(
            "GET", "/api/repos/alpha-repo/file?path=.env")
        self.assertEqual(status, 200)
        self.assertEqual(peek["withheld"], "secret")
        self.assertIsNone(peek["content"])
        status, peek = self.req(
            "GET", "/api/repos/alpha-repo/file"
                   "?path=.env&reveal=1")
        self.assertEqual(status, 200)
        self.assertEqual(peek["content"], "TOKEN=x\n")
        self.assertTrue(peek["revealed"])

    def test_save_round_trip_and_conflict(self):
        _s, peek = self.req(
            "GET", "/api/repos/alpha-repo/file?path=a.txt")
        body = {"path": "a.txt", "content": "alpha\ngamma\n",
                "base_sha256": peek["sha256"]}
        status, saved = self.req(
            "POST", "/api/repos/alpha-repo/file", body)
        self.assertEqual(status, 200)
        self.assertEqual(
            (self.alpha / "a.txt").read_text(
                encoding="utf-8"),
            "alpha\ngamma\n")
        status, conflict = self.req(
            "POST", "/api/repos/alpha-repo/file", body)
        self.assertEqual(status, 409)
        self.assertEqual(conflict["current_sha256"],
                         saved["sha256"])
        status, refused = self.req(
            "POST", "/api/repos/alpha-repo/file",
            {"path": ".env", "content": "TOKEN=y\n",
             "base_sha256": "0" * 64})
        self.assertEqual(status, 403)

    def test_registry_update_validates(self):
        status, payload = self.req(
            "POST", "/api/repos/registry",
            {"id": "alpha-repo",
             "patch": {"expected": "local_ok",
                       "pinned": True}})
        self.assertEqual(status, 200)
        self.assertEqual(payload["registry"]["expected"],
                         "local_ok")
        self.assertTrue(payload["registry"]["pinned"])
        status, payload = self.req(
            "POST", "/api/repos/registry",
            {"id": "alpha-repo", "patch": {"bogus": 1}})
        self.assertEqual(status, 400)
        status, payload = self.req(
            "GET", "/api/repos/registry")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload["repos"]["alpha-repo"]["expected"],
            "local_ok")

    def test_history_records(self):
        self.req("GET", "/api/repos")
        status, payload = self.req(
            "GET", "/api/repos/alpha-repo/history")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(payload["records"]), 1)
        self.assertTrue(payload["timeline"])
        self.assertIsNotNone(payload["dirty_since"])

    def test_unknown_repo_404(self):
        status, _payload = self.req(
            "GET", "/api/repos/nope/status")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
