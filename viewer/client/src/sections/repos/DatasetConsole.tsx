// The dataset SQL console (datasets plan, step 6): one
// guarded read against the opened file, run through
// lib/dataset_console — a single read-only statement,
// scoped to the file's one relation, which the query
// names `data` (for the database kinds, the table the
// Table view has chosen). Refusals and engine answers
// arrive as the bridge envelope's error and render in
// place; a capped result says so. Native DuckDB files
// get no console at all — the engine cannot scope ATTACH
// to one relation, so they are browse-only.

import { useState } from "react";
import { Button } from "../../components/Button";
import { api, type DatasetCell, type DatasetSqlResult } from "../../lib/api";
import { metaStyle } from "../shared";

const CELL_MAX = 80;

const fieldStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  color: "var(--wb-content-primary)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-8)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  width: "100%",
  resize: "vertical",
  fontFamily: "var(--wb-font-mono)",
  boxSizing: "border-box",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  fontWeight: 600,
  padding: "var(--wb-space-4) var(--wb-space-12) var(--wb-space-4) 0",
  borderBottom: "1px solid var(--wb-border-strong)",
  whiteSpace: "nowrap",
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

export function DatasetConsole({
  repoId,
  path,
  table,
  kind,
}: {
  repoId: string;
  path: string;
  /** The Table view's chosen table (database kinds);
   * undefined for the single-relation kinds. */
  table?: string;
  kind: string;
}) {
  const [sql, setSql] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DatasetSqlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  // State resets are keyed by the caller (the render-once
  // rule): the parent mounts this component fresh per
  // file + table via `key`, so an answer scoped to an old
  // relation never survives into a new one.

  if (kind === "duckdb") {
    return (
      <p style={{ color: "var(--wb-content-secondary)", margin: "var(--wb-space-16) 0 0" }}>
        Console unavailable for native DuckDB files — browse only.
      </p>
    );
  }

  const run = async () => {
    const statement = sql.trim();
    if (!statement || running) return;
    setRunning(true);
    setError(null);
    try {
      const reply = await api.postRepoDatasetSql({ repoId, path, table, sql: statement });
      if (reply.status === 200 && reply.payload) {
        setResult(reply.payload as unknown as DatasetSqlResult);
      } else {
        setResult(null);
        setError(reply.error ?? `The query was refused (status ${reply.status}).`);
      }
    } catch {
      setResult(null);
      setError("The console call failed.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <section style={{ marginTop: "var(--wb-space-24)" }}>
      <h4
        style={{
          fontSize: "var(--wb-font-size-base)",
          lineHeight: "var(--wb-line-height-base)",
          fontWeight: 600,
          margin: "0 0 var(--wb-space-8)",
        }}
      >
        Console
      </h4>
      <textarea
        aria-label="SQL query"
        placeholder="SELECT … FROM data"
        rows={4}
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            void run();
          }
        }}
        style={fieldStyle}
      />
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
          variant="secondary"
          disabled={running || sql.trim() === ""}
          onClick={() => void run()}
        >
          {running ? "Running…" : "Run"}
        </Button>
        <span style={metaStyle}>Read-only · one statement · query the relation named data</span>
      </div>
      {error ? (
        <p role="alert" style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) 0 0" }}>
          {error}
        </p>
      ) : null}
      {result ? (
        <div style={{ marginTop: "var(--wb-space-12)" }}>
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
                  {result.columns.map((name) => (
                    <th key={name} style={thStyle}>
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: result rows are positional and the page is immutable per run
                  <tr key={i}>
                    {row.map((value, j) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: cells are positional, parallel to the result columns
                      <td key={j} style={tdStyle}>
                        <CellValue value={value} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ ...metaStyle, whiteSpace: "normal", margin: "var(--wb-space-8) 0 0" }}>
            <span className="num">{result.rows.length}</span> row
            {result.rows.length === 1 ? "" : "s"}
            {result.truncated ? " · Results truncated at the console cap" : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
