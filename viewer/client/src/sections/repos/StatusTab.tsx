// The Status tab (absorption plan, step 8): the owner's
// ruled shape — STACKED groups on one page: Staged,
// Unstaged, Untracked (each file with its +/−), then
// Commits, then Branches (per-branch publication), then
// Worktrees. Every value is the status payload's own;
// the tab only arranges it.

import type { RepoFileStat, RepoStatusPayload } from "../../lib/api";
import { formatCount, formatDate, formatRelative } from "../../lib/format";
import { reposHref } from "../../lib/routing";
import { EmptyWell, metaStyle } from "../shared";

const groupTitleStyle: React.CSSProperties = {
  fontSize: "var(--wb-font-size-base)",
  lineHeight: "var(--wb-line-height-base)",
  fontWeight: 600,
  margin: "var(--wb-space-24) 0 var(--wb-space-8)",
};

function StatCounts({ entry }: { entry: RepoFileStat }) {
  if (entry.is_binary) return <span style={metaStyle}>binary</span>;
  if (entry.insertions == null && entry.deletions == null) return null;
  return (
    <span className="num" style={{ ...metaStyle, marginLeft: "auto" }}>
      <span style={{ color: "var(--wb-status-implemented-text)" }}>
        +{formatCount(entry.insertions ?? 0)}
      </span>{" "}
      <span style={{ color: "var(--wb-status-hard-gate-text)" }}>
        −{formatCount(entry.deletions ?? 0)}
      </span>
    </span>
  );
}

function FileGroup({
  title,
  entries,
}: {
  title: string;
  entries: (RepoFileStat | { path: string })[];
}) {
  return (
    <section>
      <h3 style={groupTitleStyle}>
        {title} — <span className="num">{entries.length}</span>
      </h3>
      {entries.length === 0 ? (
        <p style={{ color: "var(--wb-content-muted)", margin: 0 }}>None.</p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            borderTop: "1px solid var(--wb-border-default)",
          }}
        >
          {entries.map((entry) => (
            <li
              key={entry.path}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: "var(--wb-space-12)",
                padding: "var(--wb-space-4) var(--wb-space-8)",
                borderBottom: "1px solid var(--wb-border-default)",
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: "var(--wb-font-size-sm)",
                  overflowWrap: "anywhere",
                  minWidth: 0,
                }}
              >
                {entry.path}
              </span>
              {"insertions" in entry ? <StatCounts entry={entry} /> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function StatusTab({ status }: { status: RepoStatusPayload }) {
  return (
    <div data-anchor="repos/status">
      <FileGroup title="Staged" entries={status.staged} />
      <FileGroup title="Unstaged" entries={status.unstaged} />
      <FileGroup title="Untracked" entries={status.untracked} />

      <section>
        <h3 style={groupTitleStyle}>
          Commits — <span className="num">{status.commits.length}</span> most recent
        </h3>
        {status.commits.length === 0 ? (
          <EmptyWell>No commits yet.</EmptyWell>
        ) : (
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              borderTop: "1px solid var(--wb-border-default)",
            }}
          >
            {status.commits.map((commit) => (
              <li
                key={commit.hash}
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: "var(--wb-space-12)",
                  padding: "var(--wb-space-4) var(--wb-space-8)",
                  borderBottom: "1px solid var(--wb-border-default)",
                  flexWrap: "wrap",
                }}
              >
                <span className="mono" style={metaStyle}>
                  {commit.short}
                </span>
                <span
                  style={{
                    fontSize: "var(--wb-font-size-sm)",
                    minWidth: 0,
                    overflowWrap: "anywhere",
                    flex: 1,
                  }}
                >
                  {commit.subject}
                </span>
                <span style={metaStyle}>
                  {formatDate(commit.date)} {formatRelative(commit.date)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 style={groupTitleStyle}>
          Branches — <span className="num">{status.branch_details.length}</span>
          {status.default_branch ? (
            <span style={metaStyle}> · default {status.default_branch}</span>
          ) : null}
        </h3>
        {status.branch_details.length === 0 ? (
          <EmptyWell>No branches.</EmptyWell>
        ) : (
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              borderTop: "1px solid var(--wb-border-default)",
            }}
          >
            {status.branch_details.map((branch) => (
              <li
                key={branch.name}
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: "var(--wb-space-12)",
                  padding: "var(--wb-space-4) var(--wb-space-8)",
                  borderBottom: "1px solid var(--wb-border-default)",
                  flexWrap: "wrap",
                }}
              >
                <span
                  className="mono"
                  style={{
                    fontSize: "var(--wb-font-size-sm)",
                    fontWeight: branch.name === status.branch ? 600 : 400,
                  }}
                >
                  {branch.name}
                  {branch.name === status.branch ? " ·" : ""}
                </span>
                {branch.name === status.branch ? <span style={metaStyle}>current</span> : null}
                <span style={metaStyle}>{branch.upstream ?? "no upstream"}</span>
                {branch.ahead != null && branch.behind != null ? (
                  <span style={metaStyle}>
                    ↑<span className="num">{formatCount(branch.ahead)}</span> ↓
                    <span className="num">{formatCount(branch.behind)}</span>
                  </span>
                ) : null}
                {branch.unpushed_commits > 0 ? (
                  <span style={{ ...metaStyle, color: "var(--wb-status-stale-text)" }}>
                    <span className="num">{formatCount(branch.unpushed_commits)}</span> unpushed
                  </span>
                ) : null}
                {branch.contained_in_default ? (
                  <span style={metaStyle}>contained in {status.default_branch}</span>
                ) : null}
                {branch.oldest_unpushed_at ? (
                  <span style={metaStyle}>
                    oldest unpushed {formatDate(branch.oldest_unpushed_at)}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 style={groupTitleStyle}>
          Worktrees — <span className="num">{status.worktrees.length}</span>
        </h3>
        {status.worktrees.length === 0 ? (
          <EmptyWell>No worktrees.</EmptyWell>
        ) : (
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              borderTop: "1px solid var(--wb-border-default)",
            }}
          >
            {status.worktrees.map((worktree) => (
              <li
                key={worktree.path}
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: "var(--wb-space-12)",
                  padding: "var(--wb-space-4) var(--wb-space-8)",
                  borderBottom: "1px solid var(--wb-border-default)",
                  flexWrap: "wrap",
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: "var(--wb-font-size-sm)", overflowWrap: "anywhere" }}
                >
                  {worktree.path}
                </span>
                <span className="mono" style={metaStyle}>
                  {worktree.branch ?? "detached"} · {worktree.head}
                </span>
                {worktree.path === status.root ? (
                  <span style={metaStyle}>this checkout</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p style={{ ...metaStyle, marginTop: "var(--wb-space-24)" }}>
        Cross-links:{" "}
        <a href={reposHref()} style={{ color: "var(--wb-accent)" }}>
          all repos
        </a>{" "}
        · status captured {formatDate(status.captured_at)} {formatRelative(status.captured_at)}
      </p>
    </div>
  );
}
