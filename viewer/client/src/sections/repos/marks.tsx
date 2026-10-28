// Presentation marks for repo derivations (absorption
// plan, steps 8-9), shared by the repo list and the repo
// view. Presentation only: every value is a lib/repos.py
// derivation carried on the feed; nothing is computed
// here beyond formatting. Publication, sync, and exposure
// are DERIVED states (computed at read, never ruled), so
// they render in the outline-badge shape of the
// fundamentals — glyph + word, never color alone.

import type { RepoSummary } from "../../lib/api";
import { formatCount } from "../../lib/format";
import { exposureLabel, publicationLabel, syncStateLabel } from "../../lib/labels";
import { metaStyle } from "../shared";

export const pillBase: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "var(--wb-space-4)",
  height: "24px",
  padding: "0 var(--wb-space-8)",
  borderRadius: "var(--wb-radius-pill)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  fontWeight: 500,
  whiteSpace: "nowrap",
};

function outlinePill(tone: string, textTone: string): React.CSSProperties {
  return {
    ...pillBase,
    border: `1px solid var(${tone})`,
    color: `var(${textTone})`,
  };
}

/** The publication posture: does a remote exist, and does
 * the branch track one. Neutral outline — a fact about
 * the repo's wiring, not a verdict. */
export function PublicationMark({ summary }: { summary: RepoSummary }) {
  if (summary.publication == null) return null;
  return (
    <span style={outlinePill("--wb-border-strong", "--wb-content-secondary")}>
      <span aria-hidden="true">⬡</span> {publicationLabel(summary.publication)}
      {summary.remote_stale ? " · remote view stale" : ""}
    </span>
  );
}

/** The sync state against the upstream, when the branch
 * tracks one (or the local-only / no-upstream states). */
export function SyncMark({ summary }: { summary: RepoSummary }) {
  if (summary.sync == null) return null;
  return (
    <span style={outlinePill("--wb-border-strong", "--wb-content-secondary")}>
      {syncStateLabel(summary.sync.state)}
      {summary.sync.unpushed_count > 0 ? (
        <>
          {" · "}
          <span className="num">{formatCount(summary.sync.unpushed_count)}</span> unpushed
        </>
      ) : null}
    </span>
  );
}

const EXPOSURE_TONES: Record<string, { tone: string; text: string }> = {
  local_only: { tone: "--wb-status-hard-gate", text: "--wb-status-hard-gate-text" },
  uncommitted_work: { tone: "--wb-status-stale", text: "--wb-status-stale-text" },
  unbacked_commits: { tone: "--wb-status-stale", text: "--wb-status-stale-text" },
  backed_up: { tone: "--wb-status-implemented", text: "--wb-status-implemented-text" },
};

/** What is not backed up, in one badge: the level word +
 * the counts it was derived from (commits for the commit
 * levels, files for uncommitted work). */
export function ExposureMark({ summary }: { summary: RepoSummary }) {
  const exposure = summary.exposure;
  if (exposure == null) return null;
  const tones = EXPOSURE_TONES[exposure.level] ?? {
    tone: "--wb-border-strong",
    text: "--wb-content-secondary",
  };
  return (
    <span style={outlinePill(tones.tone, tones.text)}>
      <span aria-hidden="true">{exposure.level === "backed_up" ? "✓" : "⚠"}</span>{" "}
      {exposureLabel(exposure.level)}
      {exposure.level === "uncommitted_work" && exposure.files > 0 ? (
        <>
          {" · "}
          <span className="num">{formatCount(exposure.files)}</span> files
        </>
      ) : null}
      {(exposure.level === "unbacked_commits" || exposure.level === "local_only") &&
      exposure.commits > 0 ? (
        <>
          {" · "}
          <span className="num">{formatCount(exposure.commits)}</span> commits
        </>
      ) : null}
    </span>
  );
}

/** ↑ahead ↓behind against the upstream, when both are
 * known (a repo with no upstream carries nulls and shows
 * nothing — the publication mark says why). */
export function AheadBehind({ summary }: { summary: RepoSummary }) {
  if (summary.ahead == null || summary.behind == null) return null;
  if (summary.ahead === 0 && summary.behind === 0) {
    return <span style={metaStyle}>in sync</span>;
  }
  return (
    <span style={metaStyle}>
      ↑<span className="num">{formatCount(summary.ahead)}</span> ↓
      <span className="num">{formatCount(summary.behind)}</span>
    </span>
  );
}

/** The dirty counts as words: "3 changed (1 staged,
 * 2 unstaged, 4 untracked)" parts, or "clean". */
export function DirtyMark({ summary }: { summary: RepoSummary }) {
  const counts = summary.dirty_counts;
  if (counts == null) return null;
  const total = counts.staged + counts.unstaged + counts.untracked;
  if (total === 0) return <span style={metaStyle}>clean</span>;
  const parts: string[] = [];
  if (counts.staged > 0) parts.push(`${counts.staged} staged`);
  if (counts.unstaged > 0) parts.push(`${counts.unstaged} unstaged`);
  if (counts.untracked > 0) parts.push(`${counts.untracked} untracked`);
  return (
    <span style={metaStyle}>
      <span className="num">{formatCount(total)}</span> changed ({parts.join(", ")})
    </span>
  );
}
