"""Repos feed cache gate tests: the server over real
HTTP, launched through run.py exactly as systemd launches
it, against a fixture workspace holding one git repo.

Proves: within repos_ttl_s the feed serves the computed
payload unchanged (an external commit does not move the
served head or captured_at); a registry curation POST
invalidates the cache so the next feed read shows the
patch despite a TTL an hour long; with a zero TTL the
feed keeps answering and the background refresh lands
the new head shortly after.
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
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "first")
    return root


def commit_new_file(root: Path, name: str) -> None:
    (root / name).write_text("x\n", encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-q", "-m", f"add {name}")


class CacheServerCase(unittest.TestCase):
    """One real server per class; TTL comes from the
    class's CONFIG_EXTRA."""

    CONFIG_EXTRA: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-repos-cache-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        cls.alpha = make_repo(ws, "alpha-repo")
        cls.port = free_port()
        cfg = {"workspace_root": str(ws),
               "sweep_roots": [str(ws)],
               "host": "127.0.0.1", "port": cls.port,
               "state_dir": str(cls.tmp / "state"),
               "file_editing_enabled": True,
               **cls.CONFIG_EXTRA}
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
        return self.req_raw(method, path, body)

    def feed_row(self):
        status, payload = self.req("GET", "/api/repos")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["repos"]), 1)
        return payload, payload["repos"][0]


class LongTtlCase(CacheServerCase):
    CONFIG_EXTRA = {"repos_ttl_s": 3600}

    def test_feed_served_from_cache_within_ttl(self):
        first, row = self.feed_row()
        head_before = row["head"]
        commit_new_file(self.alpha, "d.txt")
        second, row2 = self.feed_row()
        # No recompute: the served payload is the one
        # computed before the external commit.
        self.assertEqual(second["captured_at"],
                         first["captured_at"])
        self.assertEqual(row2["head"], head_before)

    def test_registry_post_invalidates(self):
        _payload, row = self.feed_row()
        self.assertNotEqual(row["registry"]["expected"],
                            "local_ok")
        status, _saved = self.req(
            "POST", "/api/repos/registry",
            {"id": "alpha-repo",
             "patch": {"expected": "local_ok",
                       "pinned": True}})
        self.assertEqual(status, 200)
        _payload, row2 = self.feed_row()
        self.assertEqual(row2["registry"]["expected"],
                         "local_ok")
        self.assertTrue(row2["registry"]["pinned"])


class ZeroTtlCase(CacheServerCase):
    CONFIG_EXTRA = {"repos_ttl_s": 0}

    def test_background_refresh_lands(self):
        _payload, row = self.feed_row()
        head_before = row["head"]
        commit_new_file(self.alpha, "e.txt")
        # Every read is past the TTL: reads keep answering
        # (stale is fine) and the background refresh lands
        # the new head shortly after.
        deadline = time.time() + 15
        seen = head_before
        while time.time() < deadline:
            _payload, row = self.feed_row()
            seen = row["head"]
            if seen != head_before:
                break
            time.sleep(0.1)
        self.assertNotEqual(seen, head_before)


if __name__ == "__main__":
    unittest.main()
