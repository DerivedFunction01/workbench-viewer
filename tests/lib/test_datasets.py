"""lib/datasets: classification, schema, paged rows,
and stats over real dataset files, plus the no-DuckDB
degradation (peek-highlight-and-datasets plan, step 2).

Fixtures live in a temp dir standing in for a repo
root: csv/tsv/jsonl as text, a parquet and a native
DuckDB file written by DuckDB itself, a sqlite file
written by the stdlib reader. Path resolution is
lib/files' — pure path logic, no git needed.
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from lib import datasets as datasets_mod
from lib.datasets import DatasetError
from lib.files import FileError_

PEOPLE = [
    ("ada", 36, "paris"),
    ("grace", 85, "nyc"),
    ("alan", 41, "london"),
    ("edsger", 72, "nuenen"),
    ("barbara", 84, "nyc"),
    ("donald", 86, "stanford"),
    ("margaret", 87, "nyc"),
    ("katherine", 101, "west-virginia"),
    ("mary", 88, "nyc"),
    ("radia", 84, "pittsburgh"),
    ("annie", 35, "nyc"),
    ("dennis", None, "murray-hill"),
]


def _duckdb():
    import duckdb
    return duckdb


class DatasetCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-datasets-"))
        root = cls.tmp
        lines = ["name,age,city"] + [
            f"{name},{'' if age is None else age},{city}"
            for name, age, city in PEOPLE]
        (root / "people.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        (root / "people.tsv").write_text(
            "name\tage\nada\t36\ngrace\t85\n",
            encoding="utf-8")
        (root / "rows.jsonl").write_text(
            '{"a": 1, "b": "x"}\n{"a": 2, "b": "y"}\n'
            '{"a": 3, "b": "z"}\n', encoding="utf-8")
        (root / "notes.txt").write_text(
            "plain text\n", encoding="utf-8")
        (root / "credentials.csv").write_text(
            "name,age,city\nada,36,paris\n",
            encoding="utf-8")
        (root / "broken.parquet").write_text(
            "this is not a parquet file\n", encoding="utf-8")
        duckdb = _duckdb()
        conn = duckdb.connect(":memory:")
        conn.execute(
            "CREATE TABLE one (name VARCHAR, age INTEGER,"
            " born DATE, amount DECIMAL(10, 2),"
            " payload BLOB)")
        conn.execute(
            "INSERT INTO one VALUES ('ada', 36,"
            " DATE '1815-12-10', 12.34, CAST('xy' AS BLOB))")
        conn.execute(
            f"COPY one TO '{root / 'one.parquet'}'"
            " (FORMAT PARQUET)")
        conn.close()
        native = duckdb.connect(str(root / "native.duckdb"))
        native.execute(
            "CREATE TABLE events (id INTEGER, label VARCHAR)")
        native.execute(
            "INSERT INTO events VALUES (1, 'boot'),"
            " (2, 'halt')")
        native.execute("CREATE TABLE meta (k VARCHAR)")
        native.execute("INSERT INTO meta VALUES ('v1')")
        native.close()
        sql = sqlite3.connect(str(root / "app.db"))
        sql.execute(
            "CREATE TABLE users (id INTEGER, name TEXT,"
            " age INTEGER)")
        sql.executemany(
            "INSERT INTO users VALUES (?, ?, ?)",
            [(1, "ada", 36), (2, "grace", 85),
             (3, "alan", 41)])
        sql.execute(
            "CREATE TABLE orders (id INTEGER, total REAL)")
        sql.executemany(
            "INSERT INTO orders VALUES (?, ?)",
            [(1, 9.5), (2, 20.0)])
        sql.commit()
        sql.close()

    # -- classification and resolution -------------------

    def test_classify_by_suffix(self):
        cases = {
            "a.parquet": "parquet", "a.csv": "csv",
            "a.tsv": "tsv", "a.jsonl": "jsonl",
            "a.ndjson": "jsonl", "a.db": "sqlite",
            "a.sqlite": "sqlite", "a.duckdb": "duckdb",
            "A.CSV": "csv", "a.txt": None, "noext": None,
        }
        for rel, kind in cases.items():
            self.assertEqual(datasets_mod.classify(rel),
                             kind, rel)

    def test_not_a_dataset(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_schema(self.tmp, "notes.txt")
        self.assertIn("not a dataset file", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_schema(self.tmp, "ghost.csv")
        self.assertIn("no such file", str(ctx.exception))

    def test_escape_refused(self):
        with self.assertRaises(FileError_):
            datasets_mod.dataset_schema(self.tmp, "../x.csv")

    def test_secret_never_tabled(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_schema(
                self.tmp, "credentials.csv")
        self.assertIn("secret", str(ctx.exception))

    def test_corrupt_dataset(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_schema(
                self.tmp, "broken.parquet")
        self.assertIn("could not be read", str(ctx.exception))

    # -- schema ------------------------------------------

    def test_csv_schema(self):
        schema = datasets_mod.dataset_schema(
            self.tmp, "people.csv")
        self.assertEqual(schema["kind"], "csv")
        self.assertEqual(
            [t["name"] for t in schema["tables"]], ["data"])
        columns = schema["tables"][0]["columns"]
        self.assertEqual([c["name"] for c in columns],
                         ["name", "age", "city"])
        self.assertIn("INT", columns[1]["type"])

    def test_tsv_schema_and_rows(self):
        schema = datasets_mod.dataset_schema(
            self.tmp, "people.tsv")
        self.assertEqual(schema["kind"], "tsv")
        page = datasets_mod.dataset_rows(
            self.tmp, "people.tsv")
        self.assertEqual(page["rows"][0], ["ada", 36])

    def test_jsonl_schema_and_rows(self):
        schema = datasets_mod.dataset_schema(
            self.tmp, "rows.jsonl")
        self.assertEqual(schema["kind"], "jsonl")
        page = datasets_mod.dataset_rows(
            self.tmp, "rows.jsonl")
        self.assertEqual(page["rows"],
                         [[1, "x"], [2, "y"], [3, "z"]])
        self.assertFalse(page["has_more"])

    def test_parquet_schema(self):
        schema = datasets_mod.dataset_schema(
            self.tmp, "one.parquet")
        self.assertEqual(schema["kind"], "parquet")
        types = {c["name"]: c["type"]
                 for c in schema["tables"][0]["columns"]}
        self.assertEqual(types["born"], "DATE")
        self.assertIn("DECIMAL", types["amount"])

    def test_sqlite_schema_two_tables(self):
        schema = datasets_mod.dataset_schema(
            self.tmp, "app.db")
        self.assertEqual(schema["kind"], "sqlite")
        self.assertEqual(
            [t["name"] for t in schema["tables"]],
            ["orders", "users"])
        users = schema["tables"][1]
        self.assertEqual([c["name"] for c in
                          users["columns"]],
                         ["id", "name", "age"])

    def test_duckdb_schema_two_tables(self):
        schema = datasets_mod.dataset_schema(
            self.tmp, "native.duckdb")
        self.assertEqual(schema["kind"], "duckdb")
        self.assertEqual(
            {t["name"] for t in schema["tables"]},
            {"events", "meta"})

    # -- rows --------------------------------------------

    def test_rows_paging(self):
        page = datasets_mod.dataset_rows(
            self.tmp, "people.csv", limit=5)
        self.assertEqual(len(page["rows"]), 5)
        self.assertTrue(page["has_more"])
        self.assertEqual(page["columns"],
                         ["name", "age", "city"])
        last = datasets_mod.dataset_rows(
            self.tmp, "people.csv", limit=5, offset=10)
        self.assertEqual(len(last["rows"]), 2)
        self.assertFalse(last["has_more"])

    def test_rows_sort(self):
        page = datasets_mod.dataset_rows(
            self.tmp, "people.csv", sort="age",
            descending=True, limit=1)
        self.assertEqual(page["rows"][0][1], 101)
        page = datasets_mod.dataset_rows(
            self.tmp, "people.csv", sort="age", limit=1)
        self.assertEqual(page["rows"][0][1], 35)

    def test_filter_eq_and_range(self):
        page = datasets_mod.dataset_rows(
            self.tmp, "people.csv",
            filters=[{"column": "city", "op": "eq",
                      "value": "nyc"}], limit=50)
        self.assertEqual(len(page["rows"]), 5)
        page = datasets_mod.dataset_rows(
            self.tmp, "people.csv",
            filters=[{"column": "age", "op": "gt",
                      "value": 84}], limit=50)
        self.assertEqual(len(page["rows"]), 5)

    def test_filter_contains_case_insensitive(self):
        page = datasets_mod.dataset_rows(
            self.tmp, "people.csv",
            filters=[{"column": "name", "op": "contains",
                      "value": "RADI"}])
        self.assertEqual([r[0] for r in page["rows"]],
                         ["radia"])

    def test_unknown_sort_column_refused_by_name(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_rows(
                self.tmp, "people.csv", sort="nope")
        self.assertIn("nope", str(ctx.exception))

    def test_unknown_filter_column_refused_by_name(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_rows(
                self.tmp, "people.csv",
                filters=[{"column": "nope", "op": "eq",
                          "value": 1}])
        self.assertIn("nope", str(ctx.exception))

    def test_unknown_operator_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_rows(
                self.tmp, "people.csv",
                filters=[{"column": "age", "op": "regex",
                          "value": "3"}])
        self.assertIn("regex", str(ctx.exception))

    def test_range_op_on_text_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_rows(
                self.tmp, "people.csv",
                filters=[{"column": "name", "op": "lt",
                          "value": "x"}])
        message = str(ctx.exception)
        self.assertIn("lt", message)
        self.assertIn("name", message)

    def test_contains_on_int_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_rows(
                self.tmp, "people.csv",
                filters=[{"column": "age", "op": "contains",
                          "value": "3"}])
        message = str(ctx.exception)
        self.assertIn("contains", message)
        self.assertIn("age", message)

    def test_sqlite_and_duckdb_rows(self):
        page = datasets_mod.dataset_rows(
            self.tmp, "app.db", table="users", sort="id")
        self.assertEqual(page["rows"][0], [1, "ada", 36])
        page = datasets_mod.dataset_rows(
            self.tmp, "native.duckdb", table="events",
            sort="id")
        self.assertEqual(page["rows"],
                         [[1, "boot"], [2, "halt"]])

    def test_unknown_table_refused_by_name(self):
        with self.assertRaises(DatasetError) as ctx:
            datasets_mod.dataset_rows(
                self.tmp, "app.db", table="nope")
        self.assertIn("nope", str(ctx.exception))

    def test_json_safe_cells(self):
        page = datasets_mod.dataset_rows(
            self.tmp, "one.parquet")
        row = page["rows"][0]
        self.assertEqual(row[0], "ada")
        self.assertEqual(row[2], "1815-12-10")
        self.assertEqual(row[3], "12.34")
        self.assertIsNone(row[4])

    # -- stats -------------------------------------------

    def test_stats_csv(self):
        stats = datasets_mod.dataset_stats(
            self.tmp, "people.csv")
        self.assertEqual(stats["approx_rows"], 12)
        by_name = {c["name"]: c for c in stats["columns"]}
        self.assertEqual(by_name["age"]["null_count"], 1)
        # APPROX_COUNT_DISTINCT is a sketch: on 12 rows
        # it may sit a count either side of the true 8.
        self.assertIn(
            by_name["city"]["approx_distinct"], (7, 8, 9))

    def test_stats_sqlite(self):
        stats = datasets_mod.dataset_stats(
            self.tmp, "app.db", table="users")
        self.assertEqual(stats["approx_rows"], 3)

    # -- fallback engine ---------------------------------

    def test_sqlite_fallback_engine(self):
        """With the scanner-extension probe forced to
        fail, the sqlite kind still derives schema, rows,
        and stats through the stdlib reader."""
        original = datasets_mod._sqlite_engine
        datasets_mod._sqlite_engine = \
            lambda conn, target, tables: "sqlite3"
        try:
            schema = datasets_mod.dataset_schema(
                self.tmp, "app.db")
            self.assertEqual(
                [t["name"] for t in schema["tables"]],
                ["orders", "users"])
            page = datasets_mod.dataset_rows(
                self.tmp, "app.db", table="users",
                sort="id")
            self.assertEqual(page["rows"][0],
                             [1, "ada", 36])
            stats = datasets_mod.dataset_stats(
                self.tmp, "app.db", table="users")
            self.assertEqual(stats["approx_rows"], 3)
        finally:
            datasets_mod._sqlite_engine = original

    # -- degradation -------------------------------------

    def test_unavailable_degradation(self):
        """With the DuckDB import blocked, the module
        reports unavailable and derivations raise the
        typed error — the module itself imported fine."""
        saved = sys.modules.get("duckdb")
        sys.modules["duckdb"] = None
        try:
            self.assertFalse(datasets_mod.available())
            with self.assertRaises(DatasetError) as ctx:
                datasets_mod.dataset_schema(
                    self.tmp, "people.csv")
            self.assertIn("unavailable", str(ctx.exception))
        finally:
            if saved is None:
                sys.modules.pop("duckdb", None)
            else:
                sys.modules["duckdb"] = saved


if __name__ == "__main__":
    unittest.main()
