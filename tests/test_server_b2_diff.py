"""Repo-home B2 over real HTTP: GET /api/projects/<slug>/
diff against a fixture project that is a real git repo
with a feature worktree (spec §18.5). Proves: the default
working view, mode presets over the wire, bundle
narrowing, the ?peek= form for §18.4 files, honest 4xx
for unknown worktree/mode/project/revision, and
per-project containment (a non-git project's diff 404s
without disturbing the git project).
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
PAST = "2026-10-20T12:00:00+00:00"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def git(cwd, *args, date=None):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return out.stdout.strip()


class DiffServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-b2-"))
        ws = cls.tmp / "ws"
        root = ws / "alpha"
        (root / ".plans").mkdir(parents=True)
        (root / "workbench.yaml").write_text(
            "name: Alpha\nplans: .plans\n", encoding="utf-8")
        (root / ".gitignore").write_text("ignored.log\n")
        (root / "a.txt").write_text("one\ntwo\n")
        (root / "b.txt").write_text("b0\n")
        git(root, "init", "-b", "main")
        git(root, "add", ".")
        git(root, "commit", "-m", "base", date=PAST)
        cls.base_sha = git(root, "rev-parse", "HEAD")
        (root / ".plans" / "2026-10-25-thing.md").write_text(
            "# Thing\n\nStatus: in progress\n"
            "Worktree: build/x\n\n## Steps\n\n"
            "1. **Change a.** Do it.\n"
            "   files: `a.txt`\n"
            "   verify: tests\n"
            "   done when: done\n", encoding="utf-8")
        wt = cls.tmp / "wt-x"
        git(root, "worktree", "add", "-b", "build/x", str(wt))
        (wt / "a.txt").write_text("one\nTWO\n")
        git(wt, "add", "a.txt")
        git(wt, "commit", "-m", "work")
        cls.work_sha = git(wt, "rev-parse", "HEAD")
        (wt / "b.txt").write_text("b1\n")          # unstaged
        (wt / "fresh.txt").write_text("new\n")     # untracked
        (wt / "ignored.log").write_text("log\n")   # ignored
        bump = time.time() + 5
        os.utime(wt / "ignored.log", (bump, bump))
        # A second project that is NOT a git repo.
        beta = ws / "beta"
        beta.mkdir()
        (beta / "workbench.yaml").write_text(
            "name: Beta\n", encoding="utf-8")
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


class TestDiffEndpoint(DiffServerCase):
    def test_default_working_view(self):
        status, out = self.req(
            "GET", "/api/projects/alpha/diff?worktree=build/x")
        self.assertEqual(status, 200)
        self.assertEqual(out["mode"], "working")
        paths = {f["path"] for f in out["files"]}
        self.assertEqual(paths, {"a.txt", "b.txt"})
        untracked = {u["path"] for u in out["untracked"]}
        self.assertEqual(untracked, {"fresh.txt"})
        ignored = {i["path"] for i in out["ignored_changed"]}
        self.assertEqual(ignored, {"ignored.log"})

    def test_modes_over_the_wire(self):
        status, out = self.req(
            "GET", "/api/projects/alpha/diff"
                   "?worktree=build/x&mode=committed")
        self.assertEqual(status, 200)
        self.assertEqual({f["path"] for f in out["files"]},
                         {"a.txt"})
        status, out = self.req(
            "GET", "/api/projects/alpha/diff"
                   f"?mode=range&base={self.base_sha}"
                   f"&target={self.work_sha}")
        self.assertEqual(status, 200)
        self.assertEqual({f["path"] for f in out["files"]},
                         {"a.txt"})
        status, out = self.req(
            "GET", "/api/projects/alpha/diff"
                   f"?mode=commit&base={self.work_sha}")
        self.assertEqual(status, 200)
        self.assertEqual({f["path"] for f in out["files"]},
                         {"a.txt"})

    def test_bundle_narrowing(self):
        status, out = self.req(
            "GET", "/api/projects/alpha/diff"
                   "?bundle=2026-10-25-thing")
        self.assertEqual(status, 200)
        self.assertTrue(out["narrowed"])
        self.assertEqual(out["anchor"]["branch"], "build/x")
        self.assertEqual({f["path"] for f in out["files"]},
                         {"a.txt"})

    def test_peek(self):
        status, out = self.req(
            "GET", "/api/projects/alpha/diff"
                   "?worktree=build/x&peek=ignored.log")
        self.assertEqual(status, 200)
        self.assertIsNone(out["peek"]["withheld"])
        self.assertEqual(
            out["peek"]["hunks"][0]["lines"][0]["text"],
            "log")

    def test_refusals_are_4xx_with_error_shape(self):
        for path, want in (
            ("/api/projects/alpha/diff?worktree=nope", 404),
            ("/api/projects/alpha/diff?mode=sideways", 400),
            ("/api/projects/alpha/diff?mode=range"
             f"&base={self.base_sha}", 400),
            ("/api/projects/alpha/diff?mode=commit"
             "&base=zzzz", 400),
            ("/api/projects/alpha/diff?bundle=nope", 404),
            ("/api/projects/nope/diff", 404),
        ):
            status, out = self.req("GET", path)
            self.assertEqual(status, want, path)
            self.assertIn("error", out)

    def test_non_git_project_contained(self):
        status, out = self.req("GET", "/api/projects/beta/diff")
        self.assertEqual(status, 404)
        self.assertIn("error", out)
        # The git project still serves afterwards.
        status, _ = self.req(
            "GET", "/api/projects/alpha/diff?worktree=build/x")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
