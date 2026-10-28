// The peek's Table view (datasets plan, step 5): a
// browsable grid over a dataset-kind repo file, served
// by lib/datasets — the schema is described once, rows
// arrive in bounded pages (LIMIT + 1, has_more drives
// Next, never a count), sorting and the one filter are
// validated server-side against the schema, and stats
// are computed only when asked for. Column types ride
// the schema; the rows page carries names and values
// only. The database kinds (sqlite, duckdb) open on a
// table picker and load no rows until one is chosen.
// The SQL console mounts under the grid, scoped to the
// same file (and table).

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "../../components/Button";
import {
  api,
  type DatasetCell,
  type DatasetColumn,
  type DatasetDescriptor,
  type DatasetFilter,
  type DatasetRowsPage,
  type DatasetSchema,
  type DatasetStats,
  type DatasetTable as DatasetTableShape,
} from "../../lib/api";
import { formatCount } from "../../lib/format";
import { metaStyle } from "../shared";
import { DatasetConsole } from "./DatasetConsole";

const PAGE_SIZE = 50;
const CELL_MAX = 80;

const OPS: DatasetFilter["op"][] = ["eq", "ne", "lt", "le", "gt", "ge", "contains"];

const OP_LABELS: Record<DatasetFilter["op"], string> = {
  eq: "=",
  ne: "≠",
  lt: "<",
  le: "≤",
  gt: ">",
  ge: "≥",
  contains: "contains",
};

const fieldStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  color: "var(--wb-content-primary)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-8)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  fontWeight: 600,
  padding: "var(--wb-space-4) var(--wb-space-12) var(--wb-space-4) 0",
  borderBottom: "1px solid var(--wb-border-strong)",
  whiteSpace: "nowrap",
  verticalAlign: "bottom",
};

const tdStyle: React.CSSProperties = {
  padding: "var(--wb-space-4) var(--wb-space-12) var(--wb-space-4) 0",
  borderBottom: "1px solid var(--wb-border-default)",
  whiteSpace: "nowrap",
  verticalAlign: "top",
};

function CellValue({ value }: { value: DatasetCell }) {
  if (value == null) return <span style={{ color: "var(--wb-content-muted)" }}>—</span>;
  const text =
    typeof value === "string"
      ? value
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
  if (text.length > CELL_MAX) {
    return <span title={text}>{`${text.slice(0, CELL_MAX)}…`}</span>;
  }
  return <>{text}</>;
}

export function DatasetTable({
  repoId,
  path,
  descriptor,
}: {
  repoId: string;
  path: string;
  descriptor: DatasetDescriptor;
}) {
  const isDb = descriptor.tables != null;
  const [chosenTable, setChosenTable] = useState<string | null>(null);
  const [sort, setSort] = useState<{ column: string; dir: "asc" | "desc" } | null>(null);
  const [offset, setOffset] = useState(0);
  const [filterColumn, setFilterColumn] = useState("");
  const [filterOp, setFilterOp] = useState<DatasetFilter["op"]>("eq");
  const [filterValue, setFilterValue] = useState("");
  const [appliedFilter, setAppliedFilter] = useState<DatasetFilter | null>(null);
  const [showStats, setShowStats] = useState(false);

  const schemaQuery = useQuery({
    queryKey: ["repo-dataset-schema", repoId, path],
    queryFn: () => api.getRepoDataset({ repoId, path }),
  });
  const schemaEnvelope = schemaQuery.data;
  const schema =
    schemaEnvelope && schemaEnvelope.status === 200
      ? (schemaEnvelope.payload as unknown as DatasetSchema)
      : null;
  const schemaError =
    schemaEnvelope && schemaEnvelope.status !== 200
      ? (schemaEnvelope.error ?? "The dataset schema could not be read.")
      : null;

  // Before the schema lands, the database kinds still
  // know their table names (the descriptor carried them);
  // the fetched schema replaces the list when it arrives
  // and is the only source of column names and types.
  const tables: DatasetTableShape[] =
    schema?.tables ?? (descriptor.tables ?? []).map((name) => ({ name, columns: [] }));
  const activeTable = isDb ? chosenTable : (tables[0]?.name ?? null);
  const activeDef = tables.find((t) => t.name === activeTable) ?? null;
  const columns: DatasetColumn[] = activeDef?.columns ?? [];
  const typeByName = new Map(columns.map((c) => [c.name, c.type]));

  // The filter draft follows the columns of the table in
  // view: a column the table does not have resets to its
  // first column.
  useEffect(() => {
    if (columns.length > 0 && !columns.some((c) => c.name === filterColumn)) {
      setFilterColumn((columns[0] as DatasetColumn).name);
    }
  }, [columns, filterColumn]);

  const rowsQuery = useQuery({
    queryKey: [
      "repo-dataset-rows",
      repoId,
      path,
      activeTable,
      offset,
      sort?.column ?? "",
      sort?.dir ?? "",
      appliedFilter ? JSON.stringify(appliedFilter) : "",
    ],
    queryFn: () =>
      api.getRepoDatasetRows({
        repoId,
        path,
        table: isDb ? (activeTable ?? undefined) : undefined,
        limit: PAGE_SIZE,
        offset,
        sort: sort?.column,
        dir: sort?.dir,
        filtersJson: appliedFilter ? JSON.stringify([appliedFilter]) : undefined,
      }),
    enabled: schema != null && activeTable != null,
  });
  const rowsEnvelope = rowsQuery.data;
  const page =
    rowsEnvelope && rowsEnvelope.status === 200
      ? (rowsEnvelope.payload as unknown as DatasetRowsPage)
      : null;
  const rowsError =
    rowsEnvelope && rowsEnvelope.status !== 200
      ? (rowsEnvelope.error ?? "The dataset rows could not be read.")
      : null;

  const statsQuery = useQuery({
    queryKey: ["repo-dataset-stats", repoId, path, activeTable],
    queryFn: () =>
      api.getRepoDatasetStats({
        repoId,
        path,
        table: isDb ? (activeTable ?? undefined) : undefined,
      }),
    enabled: showStats && activeTable != null,
  });
  const statsEnvelope = statsQuery.data;
  const stats =
    statsEnvelope && statsEnvelope.status === 200
      ? (statsEnvelope.payload as unknown as DatasetStats)
      : null;
  const statsError =
    statsEnvelope && statsEnvelope.status !== 200
      ? (statsEnvelope.error ?? "The dataset stats could not be read.")
      : null;

  const chooseTable = (name: string) => {
    setChosenTable(name === "" ? null : name);
    setSort(null);
    setOffset(0);
    setAppliedFilter(null);
    setFilterValue("");
    setShowStats(false);
  };

  const toggleSort = (column: string) => {
    setOffset(0);
    setSort((prev) => {
      if (!prev || prev.column !== column) return { column, dir: "asc" };
      if (prev.dir === "asc") return { column, dir: "desc" };
      return null;
    });
  };

  const applyFilter = () => {
    if (filterColumn === "" || filterValue === "") return;
    setAppliedFilter({ column: filterColumn, op: filterOp, value: filterValue });
    setOffset(0);
  };

  const clearFilter = () => {
    setAppliedFilter(null);
    setFilterValue("");
    setOffset(0);
  };

  const headerNames = page?.columns ?? columns.map((c) => c.name);

  return (
    <div>
      {isDb ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-8)",
            flexWrap: "wrap",
            marginBottom: "var(--wb-space-12)",
          }}
        >
          <label style={metaStyle} htmlFor={`dataset-table-${path}`}>
            Table
          </label>
          <select
            id={`dataset-table-${path}`}
            aria-label="Dataset table"
            value={chosenTable ?? ""}
            onChange={(e) => chooseTable(e.target.value)}
            style={fieldStyle}
          >
            <option value="">Choose a table…</option>
            {tables.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
          {schemaQuery.isPending ? <span style={metaStyle}>Loading schema…</span> : null}
        </div>
      ) : schemaQuery.isPending ? (
        <p style={{ color: "var(--wb-content-muted)" }}>Loading schema…</p>
      ) : null}

      {schemaError ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          {schemaError}
        </p>
      ) : null}

      {isDb && activeTable == null && !schemaError ? (
        <p style={{ color: "var(--wb-content-secondary)" }}>Choose a table to browse its rows.</p>
      ) : null}

      {activeTable != null && schema != null ? (
        <>
          {columns.length > 0 ? (
            <div
              style={{
                display: "flex",
                gap: "var(--wb-space-8)",
                flexWrap: "wrap",
                alignItems: "center",
                marginBottom: "var(--wb-space-12)",
              }}
            >
              <select
                aria-label="Filter column"
                value={filterColumn}
                onChange={(e) => setFilterColumn(e.target.value)}
                style={fieldStyle}
              >
                {columns.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
              <select
                aria-label="Filter operator"
                value={filterOp}
                onChange={(e) => setFilterOp(e.target.value as DatasetFilter["op"])}
                style={fieldStyle}
              >
                {OPS.map((op) => (
                  <option key={op} value={op}>
                    {OP_LABELS[op]}
                  </option>
                ))}
              </select>
              <input
                aria-label="Filter value"
                value={filterValue}
                placeholder="Value"
                onChange={(e) => setFilterValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") applyFilter();
                }}
                style={{ ...fieldStyle, flex: "1 1 140px", minWidth: 0 }}
              />
              <Button
                variant="secondary"
                disabled={filterColumn === "" || filterValue === ""}
                onClick={applyFilter}
              >
                Filter
              </Button>
              {appliedFilter ? (
                <>
                  <Button variant="ghost" onClick={clearFilter}>
                    Clear
                  </Button>
                  <span style={{ ...metaStyle, whiteSpace: "normal" }}>
                    {appliedFilter.column} {OP_LABELS[appliedFilter.op]} {appliedFilter.value}
                  </span>
                </>
              ) : null}
            </div>
          ) : null}

          <div style={{ marginBottom: "var(--wb-space-12)" }}>
            <Button variant="ghost" onClick={() => setShowStats((v) => !v)}>
              {showStats ? "Hide stats" : "Stats"}
            </Button>
            {showStats ? (
              statsQuery.isPending ? (
                <p style={{ color: "var(--wb-content-muted)", margin: "var(--wb-space-8) 0 0" }}>
                  Loading stats…
                </p>
              ) : statsError ? (
                <p
                  role="alert"
                  style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) 0 0" }}
                >
                  {statsError}
                </p>
              ) : stats ? (
                <div style={{ marginTop: "var(--wb-space-8)" }}>
                  <p
                    style={{ ...metaStyle, whiteSpace: "normal", margin: "0 0 var(--wb-space-8)" }}
                  >
                    ≈ <span className="num">{formatCount(stats.approx_rows)}</span> rows
                  </p>
                  <div style={{ overflowX: "auto" }}>
                    <table
                      className="mono"
                      style={{
                        borderCollapse: "collapse",
                        fontSize: "var(--wb-font-size-sm)",
                        lineHeight: "var(--wb-line-height-sm)",
                      }}
                    >
                      <thead>
                        <tr>
                          <th style={thStyle}>Column</th>
                          <th style={thStyle}>Distinct ≈</th>
                          <th style={thStyle}>Nulls</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stats.columns.map((c) => (
                          <tr key={c.name}>
                            <td style={tdStyle}>{c.name}</td>
                            <td style={tdStyle}>
                              <span className="num">
                                {c.approx_distinct != null ? formatCount(c.approx_distinct) : "—"}
                              </span>
                            </td>
                            <td style={tdStyle}>
                              <span className="num">
                                {c.null_count != null ? formatCount(c.null_count) : "—"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null
            ) : null}
          </div>

          {rowsError ? (
            <p role="alert" style={{ color: "var(--wb-danger)" }}>
              {rowsError}
            </p>
          ) : rowsQuery.isPending || !page ? (
            <p style={{ color: "var(--wb-content-muted)" }}>Loading rows…</p>
          ) : (
            <>
              <div style={{ overflowX: "auto" }}>
                <table
                  className="mono"
                  style={{
                    borderCollapse: "collapse",
                    fontSize: "var(--wb-font-size-sm)",
                    lineHeight: "var(--wb-line-height-sm)",
                  }}
                >
                  <thead>
                    <tr>
                      {headerNames.map((name) => (
                        <th key={name} style={thStyle}>
                          <button
                            type="button"
                            aria-label={`Sort by ${name}`}
                            onClick={() => toggleSort(name)}
                            style={{
                              background: "none",
                              border: "none",
                              padding: 0,
                              font: "inherit",
                              color: "inherit",
                              cursor: "pointer",
                            }}
                          >
                            {name}
                            {sort?.column === name ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
                          </button>
                          {typeByName.get(name) ? (
                            <div
                              style={{
                                fontWeight: 400,
                                color: "var(--wb-content-muted)",
                                fontSize: "var(--wb-font-size-xs)",
                              }}
                            >
                              {typeByName.get(name)}
                            </div>
                          ) : null}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {page.rows.length === 0 ? (
                      <tr>
                        <td style={tdStyle} colSpan={Math.max(1, headerNames.length)}>
                          <span style={{ color: "var(--wb-content-muted)" }}>
                            No rows{appliedFilter ? " match the filter" : ""}.
                          </span>
                        </td>
                      </tr>
                    ) : (
                      page.rows.map((row, i) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: dataset rows are positional and the page is immutable per query
                        <tr key={offset + i}>
                          {row.map((value, j) => (
                            // biome-ignore lint/suspicious/noArrayIndexKey: cells are positional, parallel to the page columns
                            <td key={j} style={tdStyle}>
                              <CellValue value={value} />
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--wb-space-12)",
                  flexWrap: "wrap",
                  marginTop: "var(--wb-space-8)",
                }}
              >
                <Button
                  variant="ghost"
                  disabled={offset === 0 || rowsQuery.isFetching}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  ← Prev
                </Button>
                <span style={metaStyle}>
                  {page.rows.length === 0 ? (
                    "0 rows"
                  ) : (
                    <>
                      Rows <span className="num">{offset + 1}</span>–
                      <span className="num">{offset + page.rows.length}</span>
                    </>
                  )}
                </span>
                <Button
                  variant="ghost"
                  disabled={!page.has_more || rowsQuery.isFetching}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next →
                </Button>
                {rowsQuery.isFetching ? <span style={metaStyle}>Loading…</span> : null}
              </div>
            </>
          )}
        </>
      ) : null}

      {descriptor.kind === "duckdb" || !isDb || activeTable != null ? (
        <DatasetConsole
          key={`${path}::${activeTable ?? ""}`}
          repoId={repoId}
          path={path}
          table={isDb && activeTable != null ? activeTable : undefined}
          kind={descriptor.kind}
        />
      ) : null}
    </div>
  );
}
