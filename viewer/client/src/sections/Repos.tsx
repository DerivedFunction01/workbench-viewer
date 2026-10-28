// Repos — the top-level section (absorption plan, steps
// 8-9, the owner's picks): the workspace repo census in
// the list, and one repo's view behind tabs
// [Status | Files | History]. The status view is stacked
// groups; Files is the tree/peek split; History is the
// HEAD timeline + records. The header carries the repo's
// headline derivations and the dirty/ahead streak chips
// from the history feed. Everything renders served
// values — the backend does the work.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { SegmentedControl } from "../components/SegmentedControl";
import { api, type RepoHistoryPayload, type RepoStatusPayload, type RepoSummary } from "../lib/api";
import { formatDate, formatRelative, formatShortHash } from "../lib/format";
import { reposHref } from "../lib/routing";
import { FilesTab } from "./repos/FilesTab";
import { HistoryTab } from "./repos/HistoryTab";
import { AheadBehind, DirtyMark, ExposureMark, PublicationMark, SyncMark } from "./repos/marks";
import { RepoList } from "./repos/RepoList";
import { StatusTab } from "./repos/StatusTab";
import { EmptyWell, ErrorWell, metaStyle, SkeletonWell, sectionTitleStyle } from "./shared";

type RepoTab = "status" | "files" | "history";

const TAB_OPTIONS: { value: RepoTab; label: string }[] = [
  { value: "status", label: "Status" },
  { value: "files", label: "Files" },
  { value: "history", label: "History" },
];

function StreakChip({ label, since }: { label: string; since: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: "24px",
        padding: "0 var(--wb-space-8)",
        borderRadius: "var(--wb-radius-pill)",
        border: "1px solid var(--wb-status-stale)",
        color: "var(--wb-status-stale-text)",
        fontSize: "var(--wb-font-size-xs)",
        lineHeight: "var(--wb-line-height-xs)",
        fontWeight: 500,
        whiteSpace: "nowrap",
      }}
    >
      ◷ {label} since {formatDate(since)} ({formatRelative(since)})
    </span>
  );
}

function RepoHeader({
  status,
  history,
}: {
  status: RepoStatusPayload;
  history: RepoHistoryPayload | null;
}) {
  const name = status.registry?.display_name || status.name;
  return (
    <header style={{ marginBottom: "var(--wb-space-16)" }}>
      <p style={{ margin: "0 0 var(--wb-space-4)" }}>
        <a
          href={reposHref()}
          style={{
            color: "var(--wb-accent)",
            textDecoration: "none",
            fontSize: "var(--wb-font-size-sm)",
          }}
        >
          ← All repos
        </a>
      </p>
      <h1 style={{ ...sectionTitleStyle, margin: 0 }}>{name}</h1>
      <p
        className="mono"
        style={{
          color: "var(--wb-content-muted)",
          fontSize: "var(--wb-font-size-xs)",
          overflowWrap: "anywhere",
          margin: "var(--wb-space-4) 0 var(--wb-space-12)",
        }}
      >
        {status.id} · {status.root}
        {status.is_worktree ? " · linked worktree" : ""}
      </p>
      {status.error ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          This repo's state could not be derived — {status.error}
        </p>
      ) : (
        <>
          <p
            style={{
              display: "flex",
              gap: "var(--wb-space-8)",
              alignItems: "baseline",
              flexWrap: "wrap",
              margin: "0 0 var(--wb-space-8)",
              fontSize: "var(--wb-font-size-sm)",
            }}
          >
            <span className="mono" style={{ fontWeight: 600 }}>
              {status.branch ?? "detached"}
            </span>
            <span className="mono" style={metaStyle}>
              {formatShortHash(status.head_short ?? status.head)}
            </span>
            <span style={{ minWidth: 0, overflowWrap: "anywhere" }}>
              {status.head_subject ?? ""}
            </span>
          </p>
          <p
            style={{
              display: "flex",
              gap: "var(--wb-space-8)",
              alignItems: "center",
              flexWrap: "wrap",
              margin: 0,
            }}
          >
            <PublicationMark summary={status} />
            <SyncMark summary={status} />
            <ExposureMark summary={status} />
            <AheadBehind summary={status} />
            <DirtyMark summary={status} />
            {history?.dirty_since ? <StreakChip label="Dirty" since={history.dirty_since} /> : null}
            {history?.ahead_since ? <StreakChip label="Ahead" since={history.ahead_since} /> : null}
            {status.registry?.notes ? (
              <span style={metaStyle}>Registry note: {status.registry.notes}</span>
            ) : null}
          </p>
        </>
      )}
    </header>
  );
}

function RepoView({ repoId }: { repoId: string }) {
  const [tab, setTab] = useState<RepoTab>("status");

  const listQuery = useQuery({
    queryKey: ["repos"],
    queryFn: () => api.getRepos({}),
  });
  const row =
    (listQuery.data?.payload as unknown as { repos: RepoSummary[] } | null)?.repos.find(
      (repo) => repo.id === repoId,
    ) ?? null;

  const statusQuery = useQuery({
    queryKey: ["repo-status", repoId],
    queryFn: () => api.getRepoStatus({ repoId }),
    // The boolean form is load-bearing: the value must be
    // a real false until the census row is known — React
    // Query treats enabled: undefined as enabled (the
    // query would fire for missing repos and 404 noisily).
    enabled: row != null && !row.missing,
  });
  const status = statusQuery.data?.payload as unknown as RepoStatusPayload | null;

  const historyQuery = useQuery({
    queryKey: ["repo-history", repoId],
    queryFn: () => api.getRepoHistory({ repoId }),
    // Same load-bearing boolean form as the status query.
    enabled: row != null && !row.missing,
  });
  const history = historyQuery.data?.payload as unknown as RepoHistoryPayload | null;

  if (row?.missing) {
    return (
      <div data-anchor="repos/missing">
        <p style={{ margin: "0 0 var(--wb-space-4)" }}>
          <a href={reposHref()} style={{ color: "var(--wb-accent)", textDecoration: "none" }}>
            ← All repos
          </a>
        </p>
        <h1 style={sectionTitleStyle}>{row.registry?.display_name || repoId}</h1>
        <EmptyWell>
          ⚠ Missing — the registry knows this repo (root{" "}
          <span className="mono">{row.root ?? repoId}</span>) but the census did not find it on
          disk. If the directory comes back, the repo reappears here with its registry entry intact;
          the entry can be retired from Settings once it is truly gone.
        </EmptyWell>
      </div>
    );
  }

  if (!listQuery.isPending && row == null) {
    return (
      <div data-anchor="repos/view">
        <ErrorWell section="Repos" message={`repo ${repoId} is not in the census.`} />
      </div>
    );
  }

  return (
    <div data-anchor="repos/view">
      {statusQuery.isPending ? (
        <SkeletonWell label="the repo" />
      ) : statusQuery.isError || !status ? (
        <ErrorWell
          section="Repos"
          message={statusQuery.data?.error ?? "the repo status did not answer."}
        />
      ) : (
        <>
          <RepoHeader status={status} history={history} />
          <div style={{ marginBottom: "var(--wb-space-16)" }}>
            <SegmentedControl
              ariaLabel="Repo view"
              options={TAB_OPTIONS}
              value={tab}
              onChange={(next) => setTab(next as RepoTab)}
            />
          </div>
          {tab === "status" ? (
            <StatusTab status={status} />
          ) : tab === "files" ? (
            <FilesTab repoId={repoId} />
          ) : (
            <HistoryTab repoId={repoId} />
          )}
        </>
      )}
    </div>
  );
}

export function ReposSection({ repoId }: { repoId: string | null }) {
  if (repoId == null) {
    return (
      <section data-anchor="repos/section">
        <h1 style={sectionTitleStyle}>Repos</h1>
        <RepoList />
      </section>
    );
  }
  return (
    <section data-anchor="repos/section">
      <RepoView repoId={repoId} />
    </section>
  );
}
