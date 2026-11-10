// The entry's append-only history, split as the spec splits
// it: the review log (dispositions + comments — the triage
// trail) and the full history (every mutation, actor + ts).
// Nothing here writes; the log is the record.

import { Card } from "../../components/Card";
import { formatDateTime, formatShortHash } from "../../lib/format";
import type { HistoryRow, ReviewPayload } from "./types";

function parseReview(row: HistoryRow): ReviewPayload | null {
  if (row.verb !== "review" || !row.new) return null;
  try {
    return JSON.parse(row.new) as ReviewPayload;
  } catch {
    return null;
  }
}

const DISPOSITION_WORDS: Record<string, string> = {
  approve: "Approved",
  "needs-changes": "Needs changes",
  stale: "Marked stale",
};

export function ReviewLog({ history }: { history: HistoryRow[] }) {
  const reviews = history.filter((row) => row.verb === "review");
  return (
    <Card title="Review log">
      {reviews.length === 0 ? (
        <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
          No reviews yet — dispositions and comments will appear here.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {[...reviews].reverse().map((row) => {
            const payload = parseReview(row);
            const disposition = payload?.disposition ?? "review";
            return (
              <li
                key={row.id}
                style={{
                  borderBottom: "1px solid var(--wb-border-default)",
                  padding: "var(--wb-space-8) 0",
                }}
              >
                <span style={{ fontWeight: 600 }}>
                  {DISPOSITION_WORDS[disposition] ?? disposition}
                </span>{" "}
                <span style={{ color: "var(--wb-content-muted)" }}>
                  {row.actor} · {formatDateTime(row.ts)}
                </span>
                {payload?.comment ? (
                  <p style={{ margin: "var(--wb-space-4) 0 0" }}>{payload.comment}</p>
                ) : row.note && row.note !== payload?.comment ? (
                  <p style={{ margin: "var(--wb-space-4) 0 0" }}>{row.note}</p>
                ) : null}
                {payload?.state_sha256 ? (
                  <p
                    className="mono"
                    style={{
                      margin: "var(--wb-space-4) 0 0",
                      color: "var(--wb-content-muted)",
                      fontSize: "var(--wb-font-size-xs)",
                    }}
                  >
                    state {formatShortHash(payload.state_sha256)}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

export function HistoryList({ history }: { history: HistoryRow[] }) {
  return (
    <Card title="History">
      {history.length === 0 ? (
        <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>No history recorded.</p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {[...history].reverse().map((row) => (
            <li
              key={row.id}
              style={{
                borderBottom: "1px solid var(--wb-border-default)",
                padding: "var(--wb-space-8) 0",
                fontSize: "var(--wb-font-size-sm)",
              }}
            >
              <span style={{ fontWeight: 600 }}>{row.verb}</span>
              {row.field ? (
                <span className="mono" style={{ color: "var(--wb-content-secondary)" }}>
                  {" "}
                  {row.field}
                </span>
              ) : null}{" "}
              <span style={{ color: "var(--wb-content-muted)" }}>
                {row.actor} · {formatDateTime(row.ts)}
              </span>
              {row.old != null || row.new != null ? (
                <span
                  className="mono"
                  style={{
                    display: "block",
                    color: "var(--wb-content-muted)",
                    fontSize: "var(--wb-font-size-xs)",
                    overflowWrap: "anywhere",
                  }}
                >
                  {row.old ?? "—"} → {row.verb === "review" ? "(review payload)" : (row.new ?? "—")}
                </span>
              ) : null}
              {row.note ? (
                <span style={{ display: "block", color: "var(--wb-content-secondary)" }}>
                  {row.note}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
