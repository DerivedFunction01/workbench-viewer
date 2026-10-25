// DataTable — columns in field order, caller-supplied friendly
// headers (raw snake_case never reaches this component). Row
// hover / selected per contract; rows are keyboard-operable
// when selectable: Tab reaches a row, Enter/Space selects,
// Enter on the selected row activates.
// Contract: docs/component-contracts.md#datatable.
import { type CSSProperties, type KeyboardEvent, type ReactNode, useState } from "react";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  mono?: boolean;
  numeric?: boolean;
  render?: (row: T) => ReactNode;
};

export type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  selectedKey?: string;
  onRowSelect?: (key: string) => void;
  onRowActivate?: (key: string) => void;
  /** Rendered in place of rows (an EmptyState). */
  empty?: ReactNode;
  ariaLabel: string;
  className?: string;
};

function cellText<T>(row: T, col: DataTableColumn<T>): ReactNode {
  if (col.render) return col.render(row);
  const value = (row as Record<string, unknown>)[col.key];
  return value === null || value === undefined ? "" : String(value);
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  selectedKey,
  onRowSelect,
  onRowActivate,
  empty,
  ariaLabel,
  className,
}: DataTableProps<T>) {
  const selectable = Boolean(onRowSelect);
  const [hoverKey, setHoverKey] = useState<string | null>(null);

  const onRowKeyDown = (e: KeyboardEvent<HTMLTableRowElement>, key: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (key === selectedKey && onRowActivate) {
        onRowActivate(key);
      } else {
        onRowSelect?.(key);
      }
    }
  };

  const rowStyle = (key: string, selected: boolean): CSSProperties => ({
    backgroundColor: selected || hoverKey === key ? "var(--wb-surface-1)" : "var(--wb-surface-2)",
    boxShadow: selected ? "inset 2px 0 0 0 var(--wb-accent)" : undefined,
    height: "var(--wb-row-height)",
  });

  return (
    <div className={className}>
      <table aria-label={ariaLabel} className="w-full border-collapse text-sm">
        <thead>
          <tr style={{ backgroundColor: "var(--wb-surface-1)", height: "var(--wb-row-height)" }}>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={[
                  "px-3 text-xs font-semibold tracking-[0.06em] uppercase",
                  col.numeric ? "text-right" : "text-left",
                ].join(" ")}
                style={{
                  color: "var(--wb-content-secondary)",
                  borderBottomColor: "var(--wb-border-strong)",
                  borderBottomStyle: "solid",
                  borderBottomWidth: 1,
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row);
            const selected = key === selectedKey;
            return (
              <tr
                key={key}
                data-selected={selected || undefined}
                aria-selected={selectable ? selected : undefined}
                tabIndex={selectable ? 0 : undefined}
                onClick={selectable ? () => onRowSelect?.(key) : undefined}
                onDoubleClick={onRowActivate ? () => onRowActivate(key) : undefined}
                onKeyDown={selectable ? (e) => onRowKeyDown(e, key) : undefined}
                onMouseEnter={() => setHoverKey(key)}
                onMouseLeave={() => setHoverKey(null)}
                className={[
                  selectable ? "cursor-pointer" : "",
                  "focus-visible:outline-2 focus-visible:outline-solid focus-visible:-outline-offset-2 focus-visible:outline-(--wb-focus-ring)",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={rowStyle(key, selected)}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={[
                      "max-w-[240px] truncate px-3",
                      col.mono ? "mono" : "",
                      col.numeric ? "num text-right" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={{
                      color: "var(--wb-content-primary)",
                      borderBottomColor: "var(--wb-border-default)",
                      borderBottomStyle: "solid",
                      borderBottomWidth: 1,
                    }}
                  >
                    {cellText(row, col)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && empty ? <div className="mt-3">{empty}</div> : null}
    </div>
  );
}
