"""Datasets routes gate tests (datasets plan, step 3):
the server over real HTTP against a fixture repo holding
a csv, a parquet, a native DuckDB file, and a
secret-shaped csv.

Proves: the peek carries the dataset descriptor (and
never for the secret file); schema, paged rows with
has_more, sort, a filter, and an unknown-column refusal
serve; stats answer; the console runs a scoped SELECT,
refuses a write, and refuses a native DuckDB file.
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
import urllib.parse
import urllib.request
from pathlib import Path

from lib import datasets as datasets_mod

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"

CSV = "name,score\nann,3\nbob,5\ncy,4\ndan,1\neve,2\n"


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


@unittest.skipUnless(datasets_mod.available(),
                     "duckdb not installed in this venv")
class DatasetsServerCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-datasets-"))
        ws = cls.tmp / "ws"
        ws.mkdir()
        root = ws / "data-repo"
        root.mkdir()
        git(root, "init", "-q", "-b", "main", ".")
        (root / "data.csv").write_text(CSV, encoding="utf-8")
        (root / "credentials.csv").write_text(
            "user,pass\nx,y\n", encoding="utf-8")
        import duckdb
        con = duckdb.connect()
        con.execute(
            "CREATE TABLE t AS SELECT * FROM (VALUES "
            "('ann', 3), ('bob', 5), ('cy', 4), ('dan', 1), "
            "('eve', 2)) AS v(name, score)")
        con.execute(
            f"COPY t TO '{root / 'data.parquet'}' "
            "(FORMAT PARQUET)")
        con.close()
        con = duckdb.connect(str(root / "native.duckdb"))
        con.execute("CREATE TABLE t1 (a INTEGER)")
        con.execute("INSERT INTO t1 VALUES (1), (2)")
        con.close()
        git(root, "add", ".")
        git(root, "commit", "-q", "-m", "data")
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
                                        timeout=15) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def req(self, method, path, body=None):
        return type(self).req_raw(method, path, body)

    def test_peek_descriptors(self):
        _s, peek = self.req(
            "GET", "/api/repos/data-repo/file?path=data.csv")
        self.assertEqual(peek["dataset"], {"kind": "csv"})
        _s, peek = self.req(
            "GET", "/api/repos/data-repo/file"
                   "?path=data.parquet")
        self.assertTrue(peek["is_binary"])
        self.assertEqual(peek["dataset"], {"kind": "parquet"})
        _s, peek = self.req(
            "GET", "/api/repos/data-repo/file"
                   "?path=native.duckdb")
        self.assertEqual(peek["dataset"]["kind"], "duckdb")
        self.assertIn("t1", peek["dataset"]["tables"])
        _s, peek = self.req(
            "GET", "/api/repos/data-repo/file"
                   "?path=credentials.csv")
        self.assertEqual(peek["withheld"], "secret")
        self.assertIsNone(peek.get("dataset"))

    def test_schema_route(self):
        status, payload = self.req(
            "GET", "/api/repos/data-repo/dataset"
                   "?path=data.csv")
        self.assertEqual(status, 200)
        table = payload["tables"][0]
        self.assertEqual(table["name"], "data")
        self.assertEqual([c["name"] for c in table["columns"]],
                         ["name", "score"])

    def test_rows_paging_sort_filter(self):
        q = urllib.parse.urlencode(
            {"path": "data.parquet", "limit": 2})
        status, page = self.req(
            "GET", f"/api/repos/data-repo/dataset/rows?{q}")
        self.assertEqual(status, 200)
        self.assertEqual(len(page["rows"]), 2)
        self.assertTrue(page["has_more"])
        q = urllib.parse.urlencode(
            {"path": "data.parquet", "limit": 2, "offset": 4})
        _s, page = self.req(
            "GET", f"/api/repos/data-repo/dataset/rows?{q}")
        self.assertEqual(len(page["rows"]), 1)
        self.assertFalse(page["has_more"])
        q = urllib.parse.urlencode(
            {"path": "data.parquet", "sort": "score",
             "dir": "desc"})
        _s, page = self.req(
            "GET", f"/api/repos/data-repo/dataset/rows?{q}")
        self.assertEqual(page["rows"][0], ["bob", 5])
        q = urllib.parse.urlencode(
            {"path": "data.parquet",
             "filters": json.dumps(
                 [{"column": "name", "op": "eq",
                   "value": "cy"}])})
        _s, page = self.req(
            "GET", f"/api/repos/data-repo/dataset/rows?{q}")
        self.assertEqual(page["rows"], [["cy", 4]])
        q = urllib.parse.urlencode(
            {"path": "data.parquet", "sort": "nope"})
        status, payload = self.req(
            "GET", f"/api/repos/data-repo/dataset/rows?{q}")
        self.assertEqual(status, 400)
        self.assertIn("nope", payload["error"])

    def test_stats_route(self):
        status, payload = self.req(
            "GET", "/api/repos/data-repo/dataset/stats"
                   "?path=data.csv")
        self.assertEqual(status, 200)
        self.assertEqual(payload["approx_rows"], 5)
        self.assertEqual(len(payload["columns"]), 2)

    def test_sql_console(self):
        status, payload = self.req(
            "POST", "/api/repos/data-repo/dataset/sql",
            {"path": "data.csv",
             "sql": "SELECT name FROM data WHERE score > 3 "
                    "ORDER BY name"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["rows"], [["bob"], ["cy"]])
        status, payload = self.req(
            "POST", "/api/repos/data-repo/dataset/sql",
            {"path": "data.csv",
             "sql": "DELETE FROM data"})
        self.assertEqual(status, 400)
        status, payload = self.req(
            "POST", "/api/repos/data-repo/dataset/sql",
            {"path": "native.duckdb",
             "sql": "SELECT * FROM data"})
        self.assertEqual(status, 400)

    def test_secret_dataset_refused(self):
        status, _payload = self.req(
            "GET", "/api/repos/data-repo/dataset"
                   "?path=credentials.csv")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
