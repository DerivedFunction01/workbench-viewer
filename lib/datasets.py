"""Dataset derivations over repo files (peek-highlight-
and-datasets plan, step 2): classification, schema,
paged rows, and on-demand column stats for the file
kinds a table view can open.

The contracts mirror the reference dataset viewer in
another-project: reads are bounded twice over (LIMIT + 1
paging with `has_more`, never a COUNT, plus a
serialized-byte cap per page); sort and filter columns
are validated against the described schema before they
reach SQL, and a refusal names the column or operator;
every failure is a DatasetError with a render-safe
message (house label discipline — no raw engine text),
so a broken dataset degrades its own view only.

DuckDB is the repo's one ruled-in dependency (see
requirements.txt). It is imported lazily, inside
functions, so this module — and anything importing it —
loads where DuckDB is absent: available() reports False
and every derivation raises DatasetError. Per-call
connections, read-only in effect: file reads go through
DuckDB's reader functions, native DuckDB files are
ATTACHed READ_ONLY, and nothing here issues a write.

One environment-driven fallback: the sqlite kind is
read through DuckDB's sqlite_scan when its scanner
extension is usable. Where that extension cannot load
(no cached copy and no route to fetch one), the sqlite
kind alone is served by the stdlib sqlite3 reader —
same validation, same paging — with column types taken
from the file's declared schema and COUNT(DISTINCT)
standing in for the approximate distinct count. The
SQL console has no such fallback (its dialect is
DuckDB's) and reports itself unavailable there.

JSON-safe value mapping, applied per cell by
dataset_rows, dataset_stats' callers, and the console:
  None             -> None
  bool / int       -> unchanged
  float            -> unchanged, except NaN and the
                      infinities, which become strings
                      ("nan", "inf", "-inf")
  str              -> unchanged
  date / time /
  datetime         -> ISO 8601 strings
  Decimal          -> str (exact; never float-rounded)
  bytes / bytearray
  / memoryview     -> None (the column stays present)
  list / tuple     -> list of mapped values
  dict             -> {str key: mapped value}
  anything else    -> str(value) (UUIDs, intervals, ...)
"""

import json
import math
import sqlite3
import threading
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from .files import is_secret, resolve_in_repo

# ----------------------------------------------------------------
# Classification and errors

_KIND_BY_SUFFIX = {
    ".parquet": "parquet",
    ".csv": "csv",
    ".tsv": "tsv",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".db": "sqlite",
    ".sqlite": "sqlite",
    ".duckdb": "duckdb",
}

SINGLE_TABLE = "data"

PAGE_BYTES = 1024 * 1024
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
QUERY_TIMEOUT_S = 10.0


class DatasetError(Exception):
    """A dataset derivation failed, with a render-safe
    reason (carried to the client as the error text)."""


def classify(rel) -> str | None:
    """The dataset kind for a repo-relative path, by
    suffix (case-insensitive); None when the file is not
    a dataset kind."""
    return _KIND_BY_SUFFIX.get(Path(str(rel)).suffix.lower())


def available() -> bool:
    """True when the DuckDB package imports."""
    return _duckdb() is not None


def _duckdb():
    try:
        import duckdb
    except ImportError:
        return None
    return duckdb


def _require_duckdb():
    module = _duckdb()
    if module is None:
        raise DatasetError(
            "dataset support is unavailable: the DuckDB "
            "package is not installed")
    return module


def _resolve(root, rel_raw):
    """(target, rel, kind) for a dataset file in a repo.
    Path escapes raise lib/files' FileError_, exactly as
    the peek raises them; a secret-shaped path is
    refused before any read (defense in depth — the
    routes refuse it too)."""
    target, rel = resolve_in_repo(root, rel_raw)
    if is_secret(rel):
        raise DatasetError(
            "secret-shaped paths are never tabled")
    kind = classify(rel)
    if kind is None:
        raise DatasetError(f"not a dataset file: {rel.name}")
    if not target.is_file():
        raise DatasetError("no such file in the repo")
    return target, rel, kind


# ----------------------------------------------------------------
# SQL plumbing

def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _connect():
    return _require_duckdb().connect(":memory:")


def _execute(conn, sql, params=(), timeout_s=QUERY_TIMEOUT_S):
    """Run one statement, interrupting it past its time
    budget (the reference session seam: DuckDB has no
    statement timeout, so the interrupt is scheduled
    from a timer thread and cancelled on every path)."""
    timer = threading.Timer(timeout_s, conn.interrupt)
    timer.start()
    try:
        return conn.execute(sql, list(params))
    except DatasetError:
        raise
    except Exception as exc:
        if "INTERRUPT" in str(exc).upper():
            raise DatasetError(
                "query exceeded its time budget and was "
                "interrupted") from exc
        raise DatasetError("dataset could not be read") from exc
    finally:
        timer.cancel()


def _relation(kind: str, target: Path, table: str | None) -> str:
    """The reader relation for one file (and, for the
    sqlite kind, one chosen table). Paths in the SQL are
    this module's own resolved targets, never client
    input."""
    path = _quote_literal(str(target))
    if kind == "parquet":
        return f"read_parquet({path})"
    if kind == "csv":
        return f"read_csv_auto({path})"
    if kind == "tsv":
        return f"read_csv_auto({path}, delim='\\t')"
    if kind == "jsonl":
        return (f"read_json_auto({path}, "
                "format='newline_delimited')")
    if kind == "sqlite":
        return f"sqlite_scan({path}, {_quote_literal(table or '')})"
    raise DatasetError(f"no reader for dataset kind: {kind}")


def _attach(conn, target: Path) -> None:
    _execute(conn, f"ATTACH {_quote_literal(str(target))} "
                   "AS viewer_database (READ_ONLY)")


def _describe(conn, relation: str) -> list:
    result = _execute(conn, f"DESCRIBE SELECT * FROM {relation}")
    return [{"name": str(row[0]), "type": str(row[1])}
            for row in result.fetchall()]


# ----------------------------------------------------------------
# Table discovery (schema before everything)

def _sqlite_table_names(target: Path) -> list:
    """A sqlite file's real tables, via the stdlib
    reader (read-only URI): the one listing DuckDB's
    scanner cannot give without reading the file."""
    uri = target.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name").fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatasetError("dataset could not be read") from exc
    return [str(row[0]) for row in rows]


def _sqlite_declared_columns(target: Path, table: str) -> list:
    """A sqlite table's declared columns (PRAGMA) — the
    fallback engine's schema, in the file's own types."""
    uri = target.as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute(
                f"PRAGMA table_info({_quote_ident(table)})"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatasetError("dataset could not be read") from exc
    return [{"name": str(row[1]),
             "type": str(row[2]).upper() or "TEXT"}
            for row in rows]


def _tables(conn, target: Path, kind: str) -> list:
    """[{name, relation, schema, table}] for every table
    a dataset file exposes. Single-relation kinds expose
    one table named "data"; database kinds expose one
    per real table (a native file's display name is
    schema-qualified only when a bare name collides)."""
    if kind in ("parquet", "csv", "tsv", "jsonl"):
        return [{"name": SINGLE_TABLE,
                 "relation": _relation(kind, target, None),
                 "schema": None, "table": SINGLE_TABLE}]
    if kind == "sqlite":
        return [{"name": name,
                 "relation": _relation(kind, target, name),
                 "schema": None, "table": name}
                for name in _sqlite_table_names(target)]
    if kind == "duckdb":
        _attach(conn, target)
        result = _execute(
            conn,
            "SELECT table_schema, table_name "
            "FROM information_schema.tables "
            "WHERE table_catalog = 'viewer_database' "
            "ORDER BY table_schema, table_name")
        pairs = [(str(r[0]), str(r[1]))
                 for r in result.fetchall()]
        bare = [name for _schema, name in pairs]
        tables = []
        for schema, name in pairs:
            display = name if bare.count(name) == 1 \
                else f"{schema}.{name}"
            tables.append({
                "name": display,
                "relation": '"viewer_database".'
                            f"{_quote_ident(schema)}."
                            f"{_quote_ident(name)}",
                "schema": schema, "table": name})
        return tables
    raise DatasetError(f"unsupported dataset kind: {kind}")


def _pick_table(tables: list, table: str | None) -> dict:
    if not tables:
        raise DatasetError("dataset has no tables")
    if table is None:
        return tables[0]
    for entry in tables:
        if entry["name"] == table or entry["table"] == table:
            return entry
    raise DatasetError(f"unknown table: {table!r}")


def _sqlite_engine(conn, target: Path, tables: list) -> str:
    """'duckdb' when sqlite_scan can read this file,
    'sqlite3' when its scanner extension cannot load —
    probed once per call on the first table."""
    if not tables:
        return "duckdb"
    try:
        _execute(conn, "SELECT 1 FROM "
                       f"{tables[0]['relation']} LIMIT 0")
        return "duckdb"
    except DatasetError:
        return "sqlite3"


def _open(root, rel_raw, *, table=None):
    """(conn | None, info): resolve a dataset file and
    its chosen table, with the table's columns described
    (schema before everything). info["engine"] is
    'duckdb', or 'sqlite3' for the sqlite fallback;
    conn is None exactly in the fallback case."""
    target, rel, kind = _resolve(root, rel_raw)
    _require_duckdb()
    conn = _connect()
    try:
        tables = _tables(conn, target, kind)
        chosen = _pick_table(tables, table)
        engine = "duckdb"
        if kind == "sqlite":
            engine = _sqlite_engine(conn, target, tables)
        if engine == "sqlite3":
            columns = _sqlite_declared_columns(
                target, chosen["table"])
            conn.close()
            conn = None
        else:
            columns = _describe(conn, chosen["relation"])
    except Exception:
        if conn is not None:
            conn.close()
        raise
    info = {"target": target, "rel": rel, "kind": kind,
            "table": chosen["name"], "relation":
            chosen["relation"], "columns": columns,
            "engine": engine}
    return conn, info


def _schema_tables(root, rel_raw):
    """(kind, [{name, columns}], engine) for every table
    in the file — dataset_schema's whole answer."""
    target, rel, kind = _resolve(root, rel_raw)
    _require_duckdb()
    conn = _connect()
    try:
        tables = _tables(conn, target, kind)
        engine = "duckdb"
        if kind == "sqlite" and tables:
            engine = _sqlite_engine(conn, target, tables)
        out = []
        for entry in tables:
            if engine == "sqlite3":
                columns = _sqlite_declared_columns(
                    target, entry["table"])
            else:
                columns = _describe(conn, entry["relation"])
            out.append({"name": entry["name"],
                        "columns": columns})
        return kind, out, engine
    finally:
        conn.close()


def dataset_schema(root, rel_raw) -> dict:
    """{"kind", "tables": [{"name", "columns":
    [{"name", "type"}]}]} — described, never scanned."""
    kind, tables, _engine = _schema_tables(root, rel_raw)
    return {"kind": kind, "tables": tables}


# ----------------------------------------------------------------
# Rows

_ORDERABLE_PREFIXES = ("DECIMAL", "DOUBLE", "FLOAT",
                       "REAL", "NUMERIC", "DATE", "TIME",
                       "TIMESTAMP", "INTERVAL")
_TEXT_MARKERS = ("VARCHAR", "CHAR", "TEXT", "STRING")
_ORDER_OPS = {"lt": "<", "le": "<=", "gt": ">", "ge": ">="}
_COMPARE_OPS = {"eq": "=", "ne": "<>", **_ORDER_OPS}
_ALL_OPS = {*_COMPARE_OPS, "contains"}


def _is_orderable(type_name: str) -> bool:
    upper = type_name.upper()
    return "INT" in upper or upper.startswith(
        _ORDERABLE_PREFIXES)


def _is_text(type_name: str) -> bool:
    upper = type_name.upper()
    return any(marker in upper for marker in _TEXT_MARKERS)


def _filter_clauses(filters, columns, params) -> list:
    """Validate filters against the schema and build
    the WHERE clauses — every refusal names the column
    or the operator (the reference filter contract)."""
    by_name = {c["name"]: c for c in columns}
    clauses = []
    for item in filters or ():
        if not isinstance(item, dict):
            raise DatasetError("each filter must be an object")
        name = item.get("column")
        op = item.get("op")
        if not isinstance(name, str) or name not in by_name:
            raise DatasetError(
                f"unknown filter column: {name!r}")
        if not isinstance(op, str) or op not in _ALL_OPS:
            raise DatasetError(
                f"unknown filter operator: {op!r}")
        type_name = by_name[name]["type"]
        ident = _quote_ident(name)
        if op == "contains":
            if not _is_text(type_name):
                raise DatasetError(
                    f"operator {op!r} is invalid for "
                    f"column {name!r}")
            clauses.append(f"CAST({ident} AS VARCHAR) ILIKE ?")
            params.append(f"%{item.get('value', '')}%")
            continue
        if op in _ORDER_OPS and not _is_orderable(type_name):
            raise DatasetError(
                f"operator {op!r} is invalid for "
                f"column {name!r}")
        clauses.append(f"{ident} {_COMPARE_OPS[op]} ?")
        params.append(item.get("value"))
    return clauses


def _render_page(raw_rows, limit):
    """Render up to `limit` raw rows JSON-safe under the
    page byte cap. Returns (rows, has_more): has_more is
    honest — an unconsumed fetched row or a row dropped
    by the cap both mean more remain."""
    rows = []
    payload = 0
    overflow = len(raw_rows) > limit
    for raw in raw_rows[:limit]:
        rendered = [_json_safe(value) for value in raw]
        size = len(json.dumps(
            rendered, separators=(",", ":"),
            ensure_ascii=False).encode("utf-8"))
        if payload + size > PAGE_BYTES:
            if not rows:
                raise DatasetError(
                    "a single row exceeds the page size "
                    "limit")
            overflow = True
            break
        rows.append(rendered)
        payload += size
    return rows, overflow


def dataset_rows(root, rel_raw, *, table=None,
                 limit=DEFAULT_LIMIT, offset=0, sort=None,
                 descending=False, filters=()) -> dict:
    """One bounded page: {"columns", "rows",
    "has_more"}. See the module docstring for the
    contracts and the value mapping."""
    if not isinstance(limit, int) or isinstance(limit, bool) \
            or limit < 1:
        raise DatasetError("limit must be a positive integer")
    if limit > MAX_LIMIT:
        raise DatasetError(
            f"limit must be at most {MAX_LIMIT}")
    if not isinstance(offset, int) or offset < 0:
        raise DatasetError("offset must be >= 0")
    conn, info = _open(root, rel_raw, table=table)
    try:
        columns = info["columns"]
        by_name = {c["name"]: c for c in columns}
        if sort is not None and sort not in by_name:
            raise DatasetError(
                f"unknown sort column: {sort!r}")
        params: list = []
        clauses = _filter_clauses(filters, columns, params)
        where = f" WHERE {' AND '.join(clauses)}" \
            if clauses else ""
        order = ""
        if sort is not None:
            direction = "DESC" if descending else "ASC"
            order = f" ORDER BY {_quote_ident(sort)} {direction}"
        names = [c["name"] for c in columns]
        if info["engine"] == "sqlite3":
            raw = _sqlite_rows(info, where, order,
                               params, limit, offset)
        else:
            result = _execute(
                conn,
                f"SELECT * FROM {info['relation']}"
                f"{where}{order} LIMIT ? OFFSET ?",
                [*params, limit + 1, offset])
            raw = result.fetchmany(limit + 1)
        rows, has_more = _render_page(raw, limit)
        return {"columns": names, "rows": rows,
                "has_more": has_more}
    finally:
        if conn is not None:
            conn.close()


def _sqlite_rows(info, where, order, params, limit, offset):
    """The fallback engine's page: the same validated
    clauses over the stdlib reader. ILIKE has no sqlite
    spelling; LIKE is case-insensitive for ASCII, which
    is the fallback's one documented divergence."""
    where = where.replace("ILIKE", "LIKE")
    uri = info["target"].as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            return conn.execute(
                f"SELECT * FROM "
                f"{_quote_ident(info['table'])}"
                f"{where}{order} LIMIT ? OFFSET ?",
                [*params, limit + 1, offset]).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatasetError("dataset could not be read") from exc


# ----------------------------------------------------------------
# Stats

def dataset_stats(root, rel_raw, *, table=None) -> dict:
    """{"approx_rows", "columns": [{"name", "null_count",
    "approx_distinct"}]} — computed on demand, never on
    open. A column whose aggregate the engine refuses
    (an exotic type) reports None rather than failing
    the whole answer."""
    conn, info = _open(root, rel_raw, table=table)
    try:
        if info["engine"] == "sqlite3":
            return _sqlite_stats(info)
        relation = info["relation"]
        names = [c["name"] for c in info["columns"]]
        aggregates = ", ".join(
            f"COUNT({_quote_ident(name)}), "
            f"APPROX_COUNT_DISTINCT({_quote_ident(name)})"
            for name in names)
        try:
            totals = _execute(
                conn,
                f"SELECT COUNT(*), {aggregates} "
                f"FROM {relation}").fetchone()
        except DatasetError:
            totals = None
        if totals is not None:
            total = int(totals[0])
            columns = [{
                "name": name,
                "null_count": total - int(
                    totals[1 + index * 2]),
                "approx_distinct": int(
                    totals[2 + index * 2]),
            } for index, name in enumerate(names)]
            return {"approx_rows": total, "columns": columns}
        total = int(_execute(
            conn, f"SELECT COUNT(*) FROM {relation}"
        ).fetchone()[0])
        columns = []
        for name in names:
            ident = _quote_ident(name)
            try:
                row = _execute(
                    conn,
                    f"SELECT COUNT({ident}), "
                    f"APPROX_COUNT_DISTINCT({ident}) "
                    f"FROM {relation}").fetchone()
                columns.append({
                    "name": name,
                    "null_count": total - int(row[0]),
                    "approx_distinct": int(row[1])})
            except DatasetError:
                columns.append({"name": name,
                                "null_count": None,
                                "approx_distinct": None})
        return {"approx_rows": total, "columns": columns}
    finally:
        if conn is not None:
            conn.close()


def _sqlite_stats(info):
    uri = info["target"].as_uri() + "?mode=ro"
    table = _quote_ident(info["table"])
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            total = int(conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0])
            columns = []
            for column in info["columns"]:
                ident = _quote_ident(column["name"])
                row = conn.execute(
                    f"SELECT COUNT({ident}), "
                    f"COUNT(DISTINCT {ident}) "
                    f"FROM {table}").fetchone()
                columns.append({
                    "name": column["name"],
                    "null_count": total - int(row[0]),
                    "approx_distinct": int(row[1])})
            return {"approx_rows": total,
                    "columns": columns}
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatasetError("dataset could not be read") from exc


# ----------------------------------------------------------------
# Values

def _json_safe(value):
    """One cell, JSON-safe — the mapping in the module
    docstring."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item)
                for key, item in value.items()}
    return str(value)
