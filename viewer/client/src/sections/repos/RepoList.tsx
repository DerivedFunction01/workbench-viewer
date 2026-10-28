// The repo list (absorption plan, step 8): the census
// feed grouped per §19 — a repo's main checkout is the
// row; its linked worktrees nest under it as children; a
// repo with no worktrees gets no group shell. On top, the
// exposure strip: what is not backed up across the whole
// workspace, as sums and counts over the served fields
// (the reference viewer's totals, carried over verbatim
// in shape). Registry rows whose repo discovery did not
// find render at the foot as missing — visible, never
// silently dropped (lib/repo_state.py semantics).

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api, type RepoSummary } from "../../lib/api";
import { formatCount } from "../../lib/format";
import { reposHref } from "../../lib/routing";
import { EmptyWell, ErrorWell, metaStyle, SkeletonWell } from "../shared";
import { AheadBehind, DirtyMark, ExposureMark, PublicationMark } from "./marks";

interface RepoGroup {
  parent: RepoSummary;
  children: RepoSummary[];
}

function groupRepos(repos: RepoSummary[]): { groups: RepoGroup[]; missing: RepoSummary[] } {
  const groups = new Map<string, RepoGroup>();
  const missing: RepoSummary[] = [];
  for (const repo of repos) {
    if (repo.missing) {
      missing.push(repo);
      continue;
    }
    if (!repo.is_worktree) groups.set(repo.id, { parent: repo, children: [] });
  }
  for (const repo of repos) {
    if (repo.missing || !repo.is_worktree) continue;
    const group = repo.parent_id ? groups.get(repo.parent_id) : undefined;
    if (group && group.parent.id !== repo.id) {
      group.children.push(repo);
      continue;
    }
    // A worktree whose parent is not in the census (or is
    // itself) lists as its own row rather than vanishing.
    if (!groups.has(repo.id)) groups.set(repo.id, { parent: repo, children: [] });
  }
  return { groups: [...groups.values()], missing };
}

function RepoRowMeta({ repo }: { repo: RepoSummary }) {
  if (repo.error) {
    return (
      <span style={{ ...metaStyle, color: "var(--wb-danger)", whiteSpace: "normal" }}>
        {repo.error}
      </span>
    );
  }
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--wb-space-8)",
        flexWrap: "wrap",
      }}
    >
      <span className="mono" style={{ color: "var(--wb-content-secondary)" }}>
        {repo.branch ?? "detached"}
      </span>
      {repo.head_short ? (
        <span className="mono" style={metaStyle}>
          {repo.head_short}
        </span>
      ) : null}
      <DirtyMark summary={repo} />
      <AheadBehind summary={repo} />
    </span>
  );
}

function RepoRow({ repo, child = false }: { repo: RepoSummary; child?: boolean }) {
  const name = repo.registry?.display_name || repo.name;
  return (
    <a
      href={reposHref(repo.id)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--wb-space-12)",
        flexWrap: "wrap",
        minHeight: "var(--wb-row-height)",
        padding: "var(--wb-space-8) var(--wb-space-12)",
        color: "var(--wb-content-primary)",
        textDecoration: "none",
        fontSize: "var(--wb-font-size-sm)",
        lineHeight: "var(--wb-line-height-sm)",
      }}
    >
      <span style={{ fontWeight: 600, overflowWrap: "anywhere" }}>
        {name}
        {child ? (
          <span className="mono" style={{ ...metaStyle, marginLeft: "var(--wb-space-8)" }}>
            {repo.id}
          </span>
        ) : null}
      </span>
      {repo.registry?.pinned ? <span style={metaStyle}>pinned</span> : null}
      <RepoRowMeta repo={repo} />
      <span
        style={{
          display: "inline-flex",
          gap: "var(--wb-space-8)",
          marginLeft: "auto",
          flexWrap: "wrap",
        }}
      >
        <PublicationMark summary={repo} />
        <ExposureMark summary={repo} />
      </span>
    </a>
  );
}

function ExposureStrip({ repos }: { repos: RepoSummary[] }) {
  const totals = useMemo(() => {
    const present = repos.filter((repo) => !repo.missing);
    return {
      n: present.length,
      unpushed: present.reduce((sum, repo) => sum + (repo.sync?.unpushed_count ?? 0), 0),
      uncommitted: present.filter((repo) => (repo.exposure?.files ?? 0) > 0).length,
      localOnly: present.filter((repo) => repo.publication === "local_only").length,
    };
  }, [repos]);
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--wb-space-8)",
        alignItems: "center",
        border: "1px solid var(--wb-border-default)",
        borderRadius: "var(--wb-radius-md)",
        background: "var(--wb-surface-1)",
        padding: "var(--wb-space-8) var(--wb-space-12)",
        fontSize: "var(--wb-font-size-sm)",
        lineHeight: "var(--wb-line-height-sm)",
        marginBottom: "var(--wb-space-16)",
      }}
    >
      <span>
        <span className="num">{formatCount(totals.n)}</span> repos tracked
      </span>
      <span aria-hidden="true" style={{ color: "var(--wb-content-muted)" }}>
        ·
      </span>
      <span>
        <span className="num">{formatCount(totals.unpushed)}</span> unpushed commits exposed
      </span>
      <span aria-hidden="true" style={{ color: "var(--wb-content-muted)" }}>
        ·
      </span>
      <span>
        <span className="num">{formatCount(totals.uncommitted)}</span> repos with uncommitted work
      </span>
      <span aria-hidden="true" style={{ color: "var(--wb-content-muted)" }}>
        ·
      </span>
      <span>
        <span className="num">{formatCount(totals.localOnly)}</span> local-only
      </span>
    </div>
  );
}

export function RepoList() {
  const query = useQuery({
    queryKey: ["repos"],
    queryFn: () => api.getRepos({}),
    refetchInterval: 30000,
  });
  const payload = query.data?.payload as unknown as { repos: RepoSummary[] } | null;
  const repos = useMemo(() => payload?.repos ?? [], [payload]);
  const { groups, missing } = useMemo(() => groupRepos(repos), [repos]);

  if (query.isPending) return <SkeletonWell label="the repo census" />;
  if (query.isError || !payload) {
    return (
      <ErrorWell section="Repos" message={query.data?.error ?? "the repo census did not answer."} />
    );
  }
  return (
    <div data-anchor="repos/list">
      <ExposureStrip repos={repos} />
      {groups.length === 0 && missing.length === 0 ? (
        <EmptyWell>No repos found under the workspace root.</EmptyWell>
      ) : (
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            borderTop: "1px solid var(--wb-border-default)",
          }}
        >
          {groups.map(({ parent, children }) => (
            <li key={parent.id} style={{ borderBottom: "1px solid var(--wb-border-default)" }}>
              <RepoRow repo={parent} />
              {children.length > 0 ? (
                <ul
                  style={{
                    listStyle: "none",
                    margin: "0 0 var(--wb-space-8) var(--wb-space-16)",
                    padding: "0 0 0 var(--wb-space-8)",
                    borderLeft: "1px solid var(--wb-border-default)",
                  }}
                >
                  {children.map((childRepo) => (
                    <li key={childRepo.id}>
                      <RepoRow repo={childRepo} child />
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {missing.length > 0 ? (
        <>
          <h2
            style={{
              fontSize: "var(--wb-font-size-xs)",
              lineHeight: "var(--wb-line-height-xs)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--wb-content-secondary)",
              margin: "var(--wb-space-24) 0 var(--wb-space-8)",
            }}
          >
            Missing — in the registry, not found on disk
          </h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {missing.map((repo) => (
              <li
                key={repo.id}
                style={{
                  display: "flex",
                  gap: "var(--wb-space-12)",
                  flexWrap: "wrap",
                  alignItems: "baseline",
                  padding: "var(--wb-space-8) var(--wb-space-12)",
                  border: "1px dashed var(--wb-border-strong)",
                  borderRadius: "var(--wb-radius-md)",
                  marginBottom: "var(--wb-space-8)",
                }}
              >
                <span style={{ fontWeight: 600 }}>{repo.registry?.display_name || repo.id}</span>
                <span className="mono" style={metaStyle}>
                  {repo.root ?? repo.id}
                </span>
                <span style={{ color: "var(--wb-status-stale-text)" }}>
                  ⚠ Missing — the registry knows this repo but the census did not find it.
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p style={{ ...metaStyle, marginTop: "var(--wb-space-12)" }}>
        Publication and exposure are derived on every serve from the repos themselves; the
        registry's tracking expectations live in Settings.
      </p>
    </div>
  );
}
