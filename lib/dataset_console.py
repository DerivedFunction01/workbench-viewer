"""The guarded, read-only SQL console over one dataset
file (peek-highlight-and-datasets plan, step 4).

The guard's semantics are ported from the reference
dataset viewer's console in another-project: a filter,
not a sandbox, stacked so a query scoped to one dataset
cannot become a query over the filesystem —

- native DuckDB files are refused outright: reading
  one means ATTACHing its catalog, which would make
  every table in it addressable by name and break the
  one-relation scope (its tables still browse through
  lib/datasets);
- a single statement only, its first keyword SELECT,
  WITH, or DESCRIBE, and no write or DDL verb anywhere
  among its unquoted tokens (so WITH cannot smuggle a
  DELETE past the first-keyword check);
- table functions are refused by lowercase substring
  over the whole input — read_parquet, read_csv,
  read_json, sqlite_scan, st_read, httpfs — and so is
  any "://" or absolute-path string literal: a console
  query may name only the dataset's relation;
- the relation is bound as a view named `data` on a
  fresh connection where nothing else exists, and the
  statement runs wrapped in a LIMIT the wrapper sets,
  so the row cap holds even over an unbounded subquery;
- results are capped by rows (MAX_SQL_ROWS) and by
  serialized payload (MAX_PAYLOAD_BYTES), and execution
  is interrupted past its time budget.

Statement checks run on a masked form of the input —
comments and string literals blanked, quoted
identifiers blanked — so a semicolon or a verb inside
a literal is data, not syntax. (Dollar-quoted strings
are not masked; the reference scanner has the same
limit.) Engine errors from the operator's own query
are returned as the engine states them, capped in
length: that message is the console's feedback about
the query, unlike the dataset derivations, which
label their failures.
"""

import json
import re
import threading

from . import datasets as datasets_mod
from .datasets import DatasetError, _json_safe

MAX_SQL_ROWS = 10_000
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
CONSOLE_TIMEOUT_S = 10.0

_ALLOWED_FIRST = ("SELECT", "WITH", "DESCRIBE")
_FORBIDDEN_VERBS = frozenset({
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP",
    "ALTER", "ATTACH", "COPY", "INSTALL", "LOAD",
    "PRAGMA", "SET", "VACUUM", "EXPORT", "IMPORT",
})
# The single relation a console query may name is bound
# by the server; these functions would let a query reach
# any other file on disk. Matching is on the lowercase
# substring, catching every spelling of the call.
_FORBIDDEN_FUNCTIONS = ("read_parquet", "read_csv",
                        "read_json", "sqlite_scan",
                        "st_read", "httpfs")


def _mask(sql: str):
    """(masked, literals): the input with comments,
    string-literal contents, and quoted-identifier
    contents blanked (positions preserved), plus the
    string literals' values for the path check. An
    unterminated literal runs to end-of-string."""
    out = []
    literals = []
    index, end_of = 0, len(sql)
    while index < end_of:
        pair = sql[index:index + 2]
        char = sql[index]
        if pair == "--":
            end = sql.find("\n", index)
            end = end_of if end == -1 else end
            out.append(" " * (end - index))
            index = end
        elif pair == "/*":
            end = sql.find("*/", index + 2)
            end = end_of if end == -1 else end + 2
            out.append(" " * (end - index))
            index = end
        elif char == "'":
            cursor = index + 1
            value = []
            while cursor < end_of:
                if sql[cursor] == "'":
                    if sql[cursor:cursor + 2] == "''":
                        value.append("'")
                        cursor += 2
                        continue
                    cursor += 1
                    break
                value.append(sql[cursor])
                cursor += 1
            literals.append("".join(value))
            out.append("''")
            index = cursor
        elif char in ('"', "`"):
            cursor = index + 1
            while cursor < end_of:
                if sql[cursor] == char:
                    if sql[cursor:cursor + 2] == char * 2:
                        cursor += 2
                        continue
                    cursor += 1
                    break
                cursor += 1
            out.append('""')
            index = cursor
        else:
            out.append(char)
            index += 1
    return "".join(out), literals


def _validate(sql):
    """(executed_sql, first_keyword) for an accepted
    query, else a DatasetError naming the refusal. The
    separator check runs first, so a write followed by a
    read is reported as a multiple-statement problem,
    as the reference reports it."""
    if not isinstance(sql, str) or not sql.strip():
        raise DatasetError("query is empty")
    masked, literals = _mask(sql)
    body = masked.rstrip()
    if body.endswith(";"):
        body = body[:-1]
    if ";" in body:
        raise DatasetError(
            "multiple statements are not allowed")
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body)
    if not tokens:
        raise DatasetError("query is empty")
    first = tokens[0].upper()
    if first in _FORBIDDEN_VERBS:
        raise DatasetError(
            f"{first} is not allowed in console queries")
    if first not in _ALLOWED_FIRST:
        raise DatasetError(
            "only SELECT, WITH, or DESCRIBE queries may "
            "run in the console")
    for token in tokens[1:]:
        verb = token.upper()
        if verb in _FORBIDDEN_VERBS:
            raise DatasetError(
                f"{verb} is not allowed in console queries")
    lowered = sql.lower()
    for name in _FORBIDDEN_FUNCTIONS:
        if name in lowered:
            raise DatasetError(
                f"table function {name!r} is not allowed "
                "in console queries")
    if "://" in sql:
        raise DatasetError(
            "a console query may name only the dataset's "
            "relation")
    for literal in literals:
        if literal.startswith(("/", "\\")) or \
                re.match(r"^[A-Za-z]:[\\/]", literal):
            raise DatasetError(
                "a console query may name only the "
                "dataset's relation")
    executed = sql.strip()
    if executed.endswith(";"):
        executed = executed[:-1].rstrip()
    return executed, first


def run_dataset_sql(root, rel_raw, sql, *, table=None,
                    timeout_s=None) -> dict:
    """Run one guarded read against one dataset file:
    {"columns", "rows", "truncated"} — rows JSON-safe
    per lib/datasets' mapping, capped by rows and by
    payload, interrupted past the time budget."""
    if timeout_s is None:
        timeout_s = CONSOLE_TIMEOUT_S
    conn, info = datasets_mod._open(root, rel_raw,
                                    table=table)
    try:
        if info["kind"] == "duckdb":
            raise DatasetError(
                "SQL console is unavailable for native "
                "DuckDB files")
        if info["engine"] == "sqlite3":
            raise DatasetError(
                "SQL console is unavailable: the SQLite "
                "reader extension is not installed")
        query, first = _validate(sql)
        datasets_mod._execute(
            conn,
            "CREATE VIEW data AS SELECT * FROM "
            f"{info['relation']}")
        if first == "DESCRIBE":
            executed = query
        else:
            executed = (
                f"SELECT * FROM (\n{query}\n) "
                f"__console LIMIT {MAX_SQL_ROWS + 1}")
        timer = threading.Timer(timeout_s, conn.interrupt)
        timer.start()
        try:
            result = conn.execute(executed)
            columns = [str(d[0])
                       for d in result.description]
            rows = []
            payload = 0
            truncated = False
            while not truncated:
                batch = result.fetchmany(500)
                if not batch:
                    break
                for raw in batch:
                    if len(rows) >= MAX_SQL_ROWS:
                        truncated = True
                        break
                    rendered = [_json_safe(value)
                                for value in raw]
                    size = len(json.dumps(
                        rendered, separators=(",", ":"),
                        ensure_ascii=False).encode("utf-8"))
                    if payload + size > MAX_PAYLOAD_BYTES:
                        truncated = True
                        break
                    rows.append(rendered)
                    payload += size
        except DatasetError:
            raise
        except Exception as exc:
            if "INTERRUPT" in str(exc).upper():
                raise DatasetError(
                    f"query exceeded {timeout_s:g}s and "
                    "was interrupted") from exc
            raise DatasetError(str(exc)[:300]) from exc
        finally:
            timer.cancel()
        return {"columns": columns, "rows": rows,
                "truncated": truncated}
    finally:
        if conn is not None:
            conn.close()
