"""lib/dataset_console: the guarded read-only SQL
console (peek-highlight-and-datasets plan, step 4).

The happy path and every refusal are proven against
real dataset files in a temp dir: a scoped SELECT, a
write, a second statement, a table function, an
absolute path, a native DuckDB file, and both caps
(rows and payload), plus the interrupt on a heavy
cross join.
"""

import tempfile
import unittest
from pathlib import Path

from lib import dataset_console as console_mod
from lib.datasets import DatasetError


class ConsoleCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wb-console-"))
        root = cls.tmp
        (root / "people.csv").write_text(
            "name,age\nada,36\ngrace,85\nalan,41\n"
            "edsger,72\n", encoding="utf-8")
        (root / "credentials.csv").write_text(
            "name,age\nada,36\n", encoding="utf-8")
        import duckdb
        conn = duckdb.connect(":memory:")
        conn.execute(
            "CREATE TABLE one (name VARCHAR, age INTEGER)")
        conn.execute(
            "INSERT INTO one VALUES ('ada', 36),"
            " ('grace', 85)")
        conn.execute(
            f"COPY one TO '{root / 'one.parquet'}'"
            " (FORMAT PARQUET)")
        conn.close()
        native = duckdb.connect(str(root / "native.duckdb"))
        native.execute("CREATE TABLE t1 (a INTEGER)")
        native.execute("INSERT INTO t1 VALUES (7)")
        native.close()
        import sqlite3
        sql = sqlite3.connect(str(root / "app.db"))
        sql.execute(
            "CREATE TABLE users (id INTEGER, name TEXT)")
        sql.executemany(
            "INSERT INTO users VALUES (?, ?)",
            [(1, "ada"), (2, "grace"), (3, "alan")])
        sql.commit()
        sql.close()

    def run_sql(self, rel, sql, **kwargs):
        return console_mod.run_dataset_sql(
            self.tmp, rel, sql, **kwargs)

    # -- happy paths -------------------------------------

    def test_scoped_select(self):
        out = self.run_sql(
            "people.csv",
            "SELECT name, age FROM data WHERE age > 40"
            " ORDER BY name")
        self.assertEqual(out["columns"], ["name", "age"])
        self.assertEqual(out["rows"], [["alan", 41],
                                       ["edsger", 72],
                                       ["grace", 85]])
        self.assertFalse(out["truncated"])

    def test_select_with_own_limit(self):
        out = self.run_sql(
            "people.csv", "SELECT * FROM data LIMIT 2")
        self.assertEqual(len(out["rows"]), 2)

    def test_trailing_semicolon_and_semicolon_literal(self):
        self.assertEqual(
            self.run_sql("people.csv", "SELECT 1;")["rows"],
            [[1]])
        self.assertEqual(
            self.run_sql("people.csv", "SELECT ';'")["rows"],
            [[";"]])

    def test_comment_prefix(self):
        out = self.run_sql(
            "people.csv", "-- a note\nSELECT 2")
        self.assertEqual(out["rows"], [[2]])

    def test_with_query(self):
        out = self.run_sql(
            "people.csv",
            "WITH t AS (SELECT 42 AS x) SELECT * FROM t")
        self.assertEqual(out["rows"], [[42]])

    def test_describe(self):
        out = self.run_sql("people.csv", "DESCRIBE data")
        self.assertIn("column_name", out["columns"])
        self.assertEqual(out["rows"][0][0], "name")

    def test_parquet_console(self):
        out = self.run_sql(
            "one.parquet",
            "SELECT name FROM data WHERE age > 40")
        self.assertEqual(out["rows"], [["grace"]])

    def test_sqlite_console_over_chosen_table(self):
        out = self.run_sql(
            "app.db", "SELECT COUNT(*) FROM data",
            table="users")
        self.assertEqual(out["rows"], [[3]])

    # -- refusals ----------------------------------------

    def test_write_verbs_refused_by_name(self):
        for sql, verb in [
                ("DELETE FROM data WHERE 1 = 1", "DELETE"),
                ("INSERT INTO data VALUES (1, 2)", "INSERT"),
                ("DROP TABLE data", "DROP"),
                ("UPDATE data SET age = 0", "UPDATE")]:
            with self.assertRaises(DatasetError) as ctx:
                self.run_sql("people.csv", sql)
            self.assertIn(verb, str(ctx.exception), sql)

    def test_write_smuggled_behind_with_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            self.run_sql(
                "people.csv",
                "WITH t AS (SELECT 1) DELETE FROM data")
        self.assertIn("DELETE", str(ctx.exception))

    def test_second_statement_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            self.run_sql("people.csv", "SELECT 1; SELECT 2")
        self.assertIn("multiple statements",
                      str(ctx.exception))

    def test_table_function_refused_by_name(self):
        with self.assertRaises(DatasetError) as ctx:
            self.run_sql(
                "people.csv",
                "SELECT * FROM read_parquet('x.parquet')")
        self.assertIn("read_parquet", str(ctx.exception))

    def test_absolute_path_literal_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            self.run_sql(
                "people.csv",
                "SELECT * FROM data"
                " WHERE name = '/elsewhere/other.csv'")
        self.assertIn("may name only", str(ctx.exception))

    def test_url_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            self.run_sql(
                "people.csv",
                "SELECT 'https://example.invalid/x'")
        self.assertIn("may name only", str(ctx.exception))

    def test_duckdb_file_console_refused(self):
        with self.assertRaises(DatasetError) as ctx:
            self.run_sql("native.duckdb", "SELECT 1")
        self.assertIn("native DuckDB", str(ctx.exception))

    def test_secret_refused(self):
        with self.assertRaises(DatasetError):
            self.run_sql("credentials.csv", "SELECT 1")

    def test_unknown_relation_refused(self):
        with self.assertRaises(DatasetError):
            self.run_sql(
                "people.csv", "SELECT * FROM other_table")

    # -- caps --------------------------------------------

    def test_row_cap_truncates(self):
        out = self.run_sql(
            "people.csv", "SELECT range FROM range(20000)")
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["rows"]),
                         console_mod.MAX_SQL_ROWS)

    def test_payload_cap_truncates(self):
        out = self.run_sql(
            "people.csv",
            "SELECT repeat('x', 100000) FROM range(200)")
        self.assertTrue(out["truncated"])
        self.assertGreaterEqual(len(out["rows"]), 1)
        self.assertLess(len(out["rows"]), 200)

    def test_timeout_interrupts(self):
        original = console_mod.CONSOLE_TIMEOUT_S
        console_mod.CONSOLE_TIMEOUT_S = 0.5
        try:
            with self.assertRaises(DatasetError) as ctx:
                self.run_sql(
                    "people.csv",
                    "SELECT SUM(a.range * b.range)"
                    " FROM range(100000) a, range(100000) b")
            self.assertIn("interrupted", str(ctx.exception))
        finally:
            console_mod.CONSOLE_TIMEOUT_S = original


if __name__ == "__main__":
    unittest.main()
