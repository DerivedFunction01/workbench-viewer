// Grouped worktree presentation (repo-home spec §19),
// shared by the workspace Home and the per-project
// Overview: the repo item is the main checkout; linked
// worktrees nest under it as children; no linked
// worktrees -> no group shell at all. Also the §17
// provenance mark + active-plan line both surfaces use.
//
// Presentation only — every value here is a lib
// derivation (lib/worktrees.py, lib/active.py) carried on
// the feed; nothing is computed in the client beyond the
// grouping itself (lib/grouping.ts). One opt-in exception:
// the Overview drill-in passes `showChanges`, and the
// expanded child then mounts the B2 Changes panel for its
// own worktree (the panel owns its queries, like every
// section-level component; Home does not opt in).

import { useState } from "react";
import { Button } from "../components/Button";
import type { ActiveResolution, WorktreeItem } from "../lib/api";
import { formatDate, formatRelative } from "../lib/format";
import { activeSourceLabel, planBucketLabel } from "../lib/labels";
import { sectionHref } from "../lib/routing";
import { ChangesPanel } from "./plans/ChangesPanel";
import { metaStyle } from "./shared";

const pillBase: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  height: "24px",
  padding: "0 var(--wb-space-8)",
  borderRadius: "var(--wb-radius-pill)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  fontWeight: 500,
  whiteSpace: "nowrap",
};

/** §17.2 provenance: `declared` is a ruling — filled.
 * The derived signals (branch / unique / recency) are
 * outline. `none` renders nothing (the surfaces say "no
 * active plan" in words instead). */
export function ProvenanceMark({ source }: { source: string }) {
  if (source === "none") return null;
  if (source === "declared") {
    return (
      <span
        style={{
          ...pillBase,
          background: "color-mix(in srgb, var(--wb-accent) 16%, transparent)",
          color: "var(--wb-content-primary)",
        }}
      >
        ◆ {activeSourceLabel(source)}
      </span>
    );
  }
  return (
    <span
      style={{
        ...pillBase,
        border: "1px solid var(--wb-border-strong)",
        color: "var(--wb-content-secondary)",
      }}
    >
      {activeSourceLabel(source)}
    </span>
  );
}

export function LikelyDoneMark() {
  return (
    <span
      style={{
        ...pillBase,
        border: "1px solid var(--wb-border-strong)",
        color: "var(--wb-content-secondary)",
      }}
    >
      ◷ Likely done
    </span>
  );
}

/** The active plan of one worktree, one line: title
 * (linked into the Plans reader), bucket, provenance. */
export function ActivePlanLine({
  slug,
  active,
}: {
  slug: string;
  active: ActiveResolution | null | undefined;
}) {
  if (!active || active.source === "none" || !active.bundle) {
    return <span style={metaStyle}>No active plan</span>;
  }
  const { plan, bundle } = active;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--wb-space-8)",
        flexWrap: "wrap",
      }}
    >
      {plan ? (
        <a
          href={sectionHref(slug, "plans", plan.path)}
          style={{ color: "var(--wb-accent)", textDecoration: "none" }}
        >
          {plan.title}
        </a>
      ) : (
        <span>{bundle.id}</span>
      )}
      {plan ? <span style={metaStyle}>{planBucketLabel(plan.status_bucket)}</span> : null}
      <span style={metaStyle}>
        <span className="num">{bundle.open_count}</span> open todos
      </span>
      <ProvenanceMark source={active.source} />
    </span>
  );
}

/** Git meta spans for one worktree (branch, head, dirty,
 * ahead/behind, last commit) — words, never raw enums. */
export function WorktreeMeta({ worktree }: { worktree: WorktreeItem }) {
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
        {worktree.branch ?? "detached"}
      </span>
      {worktree.head_short ? (
        <span className="mono" style={metaStyle}>
          {worktree.head_short}
        </span>
      ) : null}
      {worktree.dirty == null ? null : worktree.dirty ? (
        <span style={metaStyle}>
          <span className="num">{worktree.changed_count ?? 0}</span> changed
        </span>
      ) : (
        <span style={metaStyle}>clean</span>
      )}
      {worktree.ahead != null && worktree.behind != null ? (
        <span style={metaStyle}>
          ↑<span className="num">{worktree.ahead}</span> ↓
          <span className="num">{worktree.behind}</span>
        </span>
      ) : null}
      {worktree.last_commit_at ? (
        <span style={metaStyle}>
          {formatDate(worktree.last_commit_at)} {formatRelative(worktree.last_commit_at)}
        </span>
      ) : null}
      {worktree.likely_done ? <LikelyDoneMark /> : null}
      {worktree.degraded ? (
        <span style={{ ...metaStyle, color: "var(--wb-danger)" }}>
          {worktree.reason ?? "degraded"}
        </span>
      ) : null}
    </span>
  );
}

/** One linked-worktree child row (grouped under its repo,
 * §19). Expandable to the full derivation: path, base,
 * attribution, and its own active plan (§17). With
 * `showChanges` (the Overview drill-in) the expansion also
 * mounts the worktree's Changes panel (§18) — the panel
 * takes the worktree from this row, branch falling back to
 * path exactly as the B2 picker derives it. */
export function WorktreeChild({
  slug,
  worktree,
  showChanges = false,
}: {
  slug: string;
  worktree: WorktreeItem;
  showChanges?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li
      style={{
        borderBottom: "1px solid var(--wb-border-default)",
        padding: "var(--wb-space-8) 0",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-12)",
          flexWrap: "wrap",
        }}
      >
        <Button
          variant="ghost"
          iconOnly
          ariaLabel={open ? "Collapse worktree details" : "Expand worktree details"}
          onClick={() => setOpen(!open)}
        >
          <span aria-hidden="true">{open ? "▾" : "▸"}</span>
        </Button>
        <WorktreeMeta worktree={worktree} />
        <ActivePlanLine slug={slug} active={worktree.active} />
      </div>
      {open ? (
        <>
          <dl
            style={{
              display: "grid",
              gridTemplateColumns: "120px 1fr",
              gap: "var(--wb-space-4) var(--wb-space-16)",
              margin: "var(--wb-space-8) 0 0 var(--wb-space-24)",
              fontSize: "var(--wb-font-size-sm)",
            }}
          >
            <dt style={metaStyle}>Path</dt>
            <dd className="mono" style={{ margin: 0 }}>
              {worktree.path}
            </dd>
            <dt style={metaStyle}>Base</dt>
            <dd style={{ margin: 0 }}>{worktree.base ?? "—"}</dd>
            <dt style={metaStyle}>Attribution</dt>
            <dd style={{ margin: 0 }}>
              {worktree.attribution.label ?? "—"}
              {worktree.attribution.plan
                ? ` · plan ${worktree.attribution.plan}`
                : ` · ${worktree.attribution.source}`}
            </dd>
            {worktree.active && worktree.active.also_in_progress.length > 0 ? (
              <>
                <dt style={metaStyle}>Also in progress</dt>
                <dd style={{ margin: 0 }}>
                  {worktree.active.also_in_progress
                    .map((a) => a.plan?.title ?? a.bundle.id)
                    .join(" · ")}
                </dd>
              </>
            ) : null}
            {worktree.active?.note ? (
              <>
                <dt style={metaStyle}>Note</dt>
                <dd style={{ margin: 0, color: "var(--wb-danger)" }}>{worktree.active.note}</dd>
              </>
            ) : null}
          </dl>
          {showChanges ? (
            <div style={{ margin: "var(--wb-space-16) 0 var(--wb-space-8) var(--wb-space-24)" }}>
              <ChangesPanel slug={slug} worktree={worktree.branch ?? worktree.path} />
            </div>
          ) : null}
        </>
      ) : null}
    </li>
  );
}

/** The nested children of a repo node (§19): the linked
 * worktrees, indented under the main checkout. Renders
 * nothing when there are none — no empty group shell. */
export function WorktreeChildren({
  slug,
  worktrees,
  showChanges = false,
}: {
  slug: string;
  worktrees: WorktreeItem[];
  showChanges?: boolean;
}) {
  const children = worktrees.filter((w) => !w.is_main);
  if (children.length === 0) return null;
  return (
    <ul
      style={{
        listStyle: "none",
        margin: "0 0 0 var(--wb-space-16)",
        padding: "0 0 0 var(--wb-space-16)",
        borderLeft: "1px solid var(--wb-border-default)",
      }}
    >
      {children.map((worktree) => (
        <WorktreeChild
          key={worktree.path}
          slug={slug}
          worktree={worktree}
          showChanges={showChanges}
        />
      ))}
    </ul>
  );
}
