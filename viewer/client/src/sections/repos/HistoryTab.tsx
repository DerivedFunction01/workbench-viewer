// The History tab (absorption plan, step 8): the HEAD
// timeline and the change records from the history feed,
// with the dirty / ahead streaks the feed derives. The
// streaks also ride the repo view's header (same feed,
// same values — the header mounts its own query so the
// two never disagree by construction of the query key).

import { useQuery } from "@tanstack/react-query";
import { api, type RepoHistoryPayload } from "../../lib/api";
import { formatDateTime, formatRelative, formatShortHash } from "../../lib/format";
import { exposureLabel, publicationLabel } from "../../lib/labels";
import { EmptyWell, ErrorWell, metaStyle, SkeletonWell } from "../shared";

export function HistoryTab({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["repo-history", repoId],
    queryFn: () => api.getRepoHistory({ repoId }),
  });
  const payload = query.data?.payload as unknown as RepoHistoryPayload | null;

  if (query.isPending) return <SkeletonWell label="the repo history" />;
  if (query.isError || !payload) {
    return (
      <ErrorWell
        section="History"
        message={query.data?.error ?? "the history could not be loaded."}
      />
    );
  }
  const records = [...payload.records].reverse();
  return (
    <div data-anchor="repos/history">
      <p style={{ color: "var(--wb-content-secondary)", fontSize: "var(--wb-font-size-sm)" }}>
        {payload.dirty_since ? (
          <>
            Working tree dirty since {formatDateTime(payload.dirty_since)} (
            {formatRelative(payload.dirty_since)}).{" "}
          </>
        ) : (
          <>The working tree is clean in the recorded history. </>
        )}
        {payload.ahead_since ? (
          <>
            Ahead of the upstream since {formatDateTime(payload.ahead_since)} (
            {formatRelative(payload.ahead_since)}).
          </>
        ) : (
          <>Not ahead of the upstream in the recorded history.</>
        )}
      </p>

      <h3
        style={{
          fontSize: "var(--wb-font-size-base)",
          fontWeight: 600,
          margin: "var(--wb-space-24) 0 var(--wb-space-8)",
        }}
      >
        HEAD timeline
      </h3>
      {payload.timeline.length === 0 ? (
        <EmptyWell>No HEAD movements recorded yet.</EmptyWell>
      ) : (
        <ol
          style={{
            listStyle: "none",
            margin: 0,
            padding: "0 0 0 var(--wb-space-16)",
            borderLeft: "1px solid var(--wb-border-default)",
          }}
        >
          {[...payload.timeline].reverse().map((point) => (
            <li
              key={`${point.ts}:${point.head}`}
              style={{ padding: "var(--wb-space-4) 0 var(--wb-space-4) var(--wb-space-8)" }}
            >
              <span className="mono" style={{ fontSize: "var(--wb-font-size-sm)" }}>
                {formatShortHash(point.head)}
              </span>{" "}
              <span style={metaStyle}>
                {point.branch ?? "detached"} · {formatDateTime(point.ts)} (
                {formatRelative(point.ts)})
              </span>
            </li>
          ))}
        </ol>
      )}

      <h3
        style={{
          fontSize: "var(--wb-font-size-base)",
          fontWeight: 600,
          margin: "var(--wb-space-24) 0 var(--wb-space-8)",
        }}
      >
        Change records — <span className="num">{records.length}</span>
      </h3>
      {records.length === 0 ? (
        <EmptyWell>
          No changes recorded yet — a record lands when the repo's headline state changes, plus the
          hourly heartbeat.
        </EmptyWell>
      ) : (
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            borderTop: "1px solid var(--wb-border-default)",
          }}
        >
          {records.map((record) => (
            <li
              key={`${record.at}:${record.head}`}
              style={{
                display: "flex",
                gap: "var(--wb-space-12)",
                flexWrap: "wrap",
                alignItems: "baseline",
                padding: "var(--wb-space-4) var(--wb-space-8)",
                borderBottom: "1px solid var(--wb-border-default)",
                fontSize: "var(--wb-font-size-sm)",
              }}
            >
              <span style={metaStyle}>{formatDateTime(record.at)}</span>
              <span className="mono" style={metaStyle}>
                {formatShortHash(record.head)}
              </span>
              <span style={{ minWidth: 0, overflowWrap: "anywhere", flex: 1 }}>
                {record.head_subject ?? "—"}
              </span>
              <span style={metaStyle}>
                {record.branch ?? "detached"} ·{" "}
                {record.dirty_total > 0 ? `${record.dirty_total} dirty` : "clean"} ·{" "}
                {publicationLabel(record.publication)} · {exposureLabel(record.exposure_level)}
                {record.exposed_commits != null && record.exposed_commits > 0
                  ? ` (${record.exposed_commits} commits)`
                  : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p style={{ ...metaStyle, marginTop: "var(--wb-space-12)" }}>
        Records are appended by the server when a repo is served and its headline state changed —
        the streaks above are the current runs in this record.
      </p>
    </div>
  );
}
