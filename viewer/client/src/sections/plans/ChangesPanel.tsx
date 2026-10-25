// Changes — the anchored diff view (repo-home §18, B2).
// One panel, three anchors: a worktree (the worktree
// picker below, standing in the Plans section until the
// repo-home Overview lands), a plan bundle (the plan
// reader's Changes tab — paths narrowed to the plan's
// declared files), and commits (Range / Commit modes).
// Modes are the §18.3 presets of the one (base, target,
// paths) triple; the staged/unstaged split (§18.2) groups
// the combined view by each file's legs. Untracked and
// ignored files render as their own §18.4 groups — never
// as diff entries. Presentational pieces take props only;
// the two section-level components (ChangesPanel,
// WorktreeChanges) own the queries, like PlanReader.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/Button";
import { DegradedBanner as KitBanner } from "../../components/DegradedBanner";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Toggle } from "../../components/Toggle";
import {
  api,
  type DiffFileEntry,
  type DiffHunk,
  type DiffPayload,
  type DiffPeek,
  type DiffPeekPayload,
  type IgnoredChangedEntry,
  type WorktreesPayload,
} from "../../lib/api";
import { EmptyWell, ErrorWell, metaStyle, SkeletonWell } from "../shared";
import { anchor } from "./anchors";

type DiffMode = "working" | "uncommitted" | "committed" | "range" | "commit";

const MODE_OPTIONS: { value: DiffMode; label: string }[] = [
  { value: "working", label: "Working" },
  { value: "uncommitted", label: "Uncommitted" },
  { value: "committed", label: "Committed" },
  { value: "range", label: "Range" },
  { value: "commit", label: "Commit" },
];

const LEG_ORDER = ["committed", "staged", "unstaged"] as const;
const LEG_LABEL: Record<string, string> = {
  committed: "Committed",
  staged: "Staged",
  unstaged: "Unstaged",
};

const LANG_BY_EXT: Record<string, string> = {
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  py: "python",
  md: "markdown",
  json: "json",
  css: "css",
  html: "xml",
  xml: "xml",
  sh: "bash",
  bash: "bash",
  yaml: "yaml",
  yml: "yaml",
  toml: "ini",
  rs: "rust",
  go: "go",
  diff: "diff",
  patch: "diff",
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const rowTint: Record<string, string | undefined> = {
  add: "color-mix(in srgb, var(--wb-status-implemented) 13%, transparent)",
  del: "color-mix(in srgb, var(--wb-status-hard-gate) 11%, transparent)",
};

const markerGlyph: Record<string, string> = {
  context: " ",
  add: "+",
  del: "−",
  meta: "\\",
};

/** Hunks with per-line syntax highlighting through the
 * LAZY highlight.js chunk (the SourceView pattern): the
 * language comes from the file extension; an unknown
 * language or a failed load renders plain text — never a
 * hole. Highlighting is per line, so a construct spanning
 * lines loses its tail coloring; the add/del tinting is
 * the primary signal and always renders. */
export function HunkView({ path, hunks }: { path: string; hunks: DiffHunk[] }) {
  const [html, setHtml] = useState<Map<string, string> | null>(null);
  const ext = path.includes(".") ? path.split(".").pop()?.toLowerCase() : undefined;
  const language = ext ? LANG_BY_EXT[ext] : undefined;
  const flat = useMemo(
    () => hunks.flatMap((hunk, hi) => hunk.lines.map((line, li) => ({ key: `${hi}:${li}`, line }))),
    [hunks],
  );

  useEffect(() => {
    if (!language) return;
    let live = true;
    (async () => {
      try {
        const hljs = (await import("highlight.js")).default;
        if (!hljs.getLanguage(language)) return;
        const out = new Map<string, string>();
        for (const { key, line } of flat) {
          if (line.kind === "context" || line.kind === "add" || line.kind === "del") {
            out.set(key, hljs.highlight(line.text, { language }).value);
          }
        }
        if (live) setHtml(out);
      } catch {
        if (live) setHtml(null);
      }
    })();
    return () => {
      live = false;
    };
  }, [flat, language]);

  if (hunks.length === 0) return null;
  return (
    <div
      style={{
        fontFamily: "var(--wb-font-mono)",
        fontSize: "var(--wb-font-size-sm)",
        lineHeight: "var(--wb-line-height-sm)",
        overflowX: "auto",
      }}
    >
      {hunks.map((hunk, hi) => (
        <div key={`${hunk.old_start}:${hunk.new_start}`}>
          <div
            style={{
              color: "var(--wb-content-muted)",
              background: "var(--wb-surface-sunken)",
              padding: "0 var(--wb-space-8)",
              whiteSpace: "pre",
            }}
          >
            {`@@ −${hunk.old_start},${hunk.old_lines} +${hunk.new_start},${hunk.new_lines} @@`}
          </div>
          {hunk.lines.map((line, li) => {
            const key = `${hi}:${li}`;
            const highlighted = html?.get(key);
            return (
              <div
                key={key}
                style={{
                  display: "grid",
                  gridTemplateColumns: "3.2em 3.2em 1.2em 1fr",
                  background: rowTint[line.kind],
                  whiteSpace: "pre",
                }}
              >
                <span
                  className="num"
                  style={{
                    color: "var(--wb-content-muted)",
                    textAlign: "right",
                    paddingRight: "var(--wb-space-8)",
                  }}
                >
                  {line.old_no ?? ""}
                </span>
                <span
                  className="num"
                  style={{
                    color: "var(--wb-content-muted)",
                    textAlign: "right",
                    paddingRight: "var(--wb-space-8)",
                  }}
                >
                  {line.new_no ?? ""}
                </span>
                <span aria-hidden="true" style={{ color: "var(--wb-content-secondary)" }}>
                  {markerGlyph[line.kind]}
                </span>
                {highlighted != null ? (
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js escapes the line text itself; its output is span markup only (the SourceView pattern)
                  <span dangerouslySetInnerHTML={{ __html: highlighted }} />
                ) : (
                  <span>{line.text}</span>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

const summaryStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: "var(--wb-space-12)",
  cursor: "pointer",
  padding: "var(--wb-space-8) var(--wb-space-12)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
};

const groupBoxStyle: React.CSSProperties = {
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  marginBottom: "var(--wb-space-8)",
  background: "var(--wb-surface-1)",
};

function countsLabel(entry: { additions: number; deletions: number }): string {
  return `+${entry.additions} −${entry.deletions}`;
}

export function DiffFileGroup({ file }: { file: DiffFileEntry }) {
  return (
    <details open style={groupBoxStyle} data-anchor={anchor.changesFile(file.path)}>
      <summary style={summaryStyle}>
        <span className="mono" style={{ fontWeight: 600 }}>
          {file.path}
        </span>
        {file.old_path ? (
          <span style={metaStyle}>
            renamed from <span className="mono">{file.old_path}</span>
          </span>
        ) : null}
        <span style={metaStyle}>{file.status}</span>
        {file.legs?.map((leg) => (
          <span key={leg} style={metaStyle}>
            {LEG_LABEL[leg] ?? leg}
          </span>
        ))}
        <span className="num" style={{ marginLeft: "auto", ...metaStyle }}>
          {countsLabel(file)}
        </span>
        {file.truncated ? (
          <span style={{ color: "var(--wb-status-stale-text)" }}>truncated</span>
        ) : null}
      </summary>
      <div style={{ borderTop: "1px solid var(--wb-border-default)" }}>
        {file.binary ? (
          <p
            style={{
              margin: 0,
              padding: "var(--wb-space-8) var(--wb-space-12)",
              color: "var(--wb-content-secondary)",
            }}
          >
            Binary file — metadata only.
          </p>
        ) : (
          <HunkView path={file.path} hunks={file.hunks} />
        )}
      </div>
    </details>
  );
}

function PeekBody({ peek }: { peek: DiffPeek }) {
  if (peek.withheld === "secret") {
    return (
      <p
        style={{
          margin: 0,
          padding: "var(--wb-space-8) var(--wb-space-12)",
          color: "var(--wb-content-secondary)",
        }}
      >
        Withheld — secret-shaped path.
      </p>
    );
  }
  if (peek.withheld) {
    return (
      <p
        style={{
          margin: 0,
          padding: "var(--wb-space-8) var(--wb-space-12)",
          color: "var(--wb-content-secondary)",
        }}
      >
        Not shown — {peek.withheld}.
      </p>
    );
  }
  if (peek.is_binary) {
    return (
      <p
        style={{
          margin: 0,
          padding: "var(--wb-space-8) var(--wb-space-12)",
          color: "var(--wb-content-secondary)",
        }}
      >
        Binary file — metadata only.
      </p>
    );
  }
  return <HunkView path={peek.path} hunks={peek.hunks} />;
}

export function UntrackedGroup({ items }: { items: DiffPeek[] }) {
  if (items.length === 0) return null;
  return (
    <section data-anchor={anchor.changesUntracked} style={{ marginTop: "var(--wb-space-16)" }}>
      <h3 style={{ fontSize: "var(--wb-font-size-base)", margin: "0 0 var(--wb-space-8)" }}>
        Untracked — <span className="num">{items.length}</span> files
      </h3>
      {items.map((item) => (
        <details key={item.path} style={groupBoxStyle}>
          <summary style={summaryStyle}>
            <span className="mono">{item.path}</span>
            <span style={metaStyle}>
              {item.is_dir ? "directory" : formatBytes(item.size_bytes)}
            </span>
            {item.withheld === "secret" ? (
              <span style={{ color: "var(--wb-status-stale-text)" }}>withheld</span>
            ) : null}
            {item.truncated ? (
              <span style={{ color: "var(--wb-status-stale-text)" }}>truncated</span>
            ) : null}
          </summary>
          {item.is_dir ? null : (
            <div style={{ borderTop: "1px solid var(--wb-border-default)" }}>
              <PeekBody peek={item} />
            </div>
          )}
        </details>
      ))}
    </section>
  );
}

function IgnoredRow({
  slug,
  worktree,
  entry,
}: {
  slug: string;
  worktree: string | null;
  entry: IgnoredChangedEntry;
}) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ["diff-peek", slug, worktree, entry.path],
    queryFn: () => api.getDiff({ slug, worktree: worktree ?? undefined, peek: entry.path }),
    enabled: open && entry.withheld == null && !entry.is_binary,
  });
  const peek = (query.data?.payload as unknown as DiffPeekPayload | null)?.peek;
  return (
    <li
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: "var(--wb-space-12)",
        padding: "var(--wb-space-4) 0",
        flexWrap: "wrap",
      }}
    >
      <span className="mono" style={{ fontSize: "var(--wb-font-size-sm)" }}>
        {entry.path}
      </span>
      <span style={metaStyle}>{formatBytes(entry.size_bytes)}</span>
      <span style={metaStyle}>recently changed</span>
      {entry.withheld === "secret" ? (
        <span style={{ color: "var(--wb-status-stale-text)", fontSize: "var(--wb-font-size-xs)" }}>
          withheld — secret-shaped
        </span>
      ) : entry.is_binary ? (
        <span style={metaStyle}>binary</span>
      ) : (
        <Button variant="ghost" onClick={() => setOpen((v) => !v)}>
          {open ? "Hide" : "Peek"}
        </Button>
      )}
      {open && peek ? (
        <div
          style={{
            flexBasis: "100%",
            border: "1px solid var(--wb-border-default)",
            borderRadius: "var(--wb-radius-md)",
          }}
        >
          <PeekBody peek={peek} />
        </div>
      ) : null}
      {open && query.isPending ? (
        <span style={{ flexBasis: "100%", color: "var(--wb-content-muted)" }}>Loading peek…</span>
      ) : null}
    </li>
  );
}

export function IgnoredGroup({
  slug,
  worktree,
  items,
  truncated,
}: {
  slug: string;
  worktree: string | null;
  items: IgnoredChangedEntry[];
  truncated: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <details data-anchor={anchor.changesIgnored} style={{ marginTop: "var(--wb-space-16)" }}>
      <summary
        style={{
          cursor: "pointer",
          color: "var(--wb-content-secondary)",
          fontSize: "var(--wb-font-size-sm)",
        }}
      >
        Ignored files changed (<span className="num">{items.length}</span>
        {truncated ? "+" : ""})
      </summary>
      <ul style={{ listStyle: "none", margin: "var(--wb-space-8) 0", padding: 0 }}>
        {items.map((entry) => (
          <IgnoredRow key={entry.path} slug={slug} worktree={worktree} entry={entry} />
        ))}
      </ul>
    </details>
  );
}

const revInputStyle: React.CSSProperties = {
  fontFamily: "var(--wb-font-mono)",
  fontSize: "var(--wb-font-size-sm)",
  background: "var(--wb-surface-sunken)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-sm)",
  color: "var(--wb-content-primary)",
  padding: "var(--wb-space-4) var(--wb-space-8)",
  minWidth: "16em",
};

export function ChangesPanel({
  slug,
  bundle = null,
  worktree = null,
}: {
  slug: string;
  bundle?: string | null;
  worktree?: string | null;
}) {
  const [mode, setMode] = useState<DiffMode>("working");
  const [split, setSplit] = useState(false);
  const [allFiles, setAllFiles] = useState(false);
  const [baseText, setBaseText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [applied, setApplied] = useState<{ base: string; target: string } | null>(null);

  const needsRevs = mode === "range" || mode === "commit";
  const query = useQuery({
    queryKey: [
      "diff",
      slug,
      bundle,
      worktree,
      mode,
      applied?.base ?? "",
      applied?.target ?? "",
      allFiles,
    ],
    queryFn: () =>
      api.getDiff({
        slug,
        bundle: bundle ?? undefined,
        worktree: worktree ?? undefined,
        mode,
        base: needsRevs ? applied?.base : undefined,
        target: mode === "range" ? applied?.target : undefined,
        all: allFiles || undefined,
      }),
    enabled: !needsRevs || applied != null,
  });

  const payload = query.data?.payload as unknown as DiffPayload | null;
  const hasLegs = payload?.files.some((f) => f.legs && f.legs.length > 0) ?? false;

  const groups = useMemo(() => {
    if (!payload) return null;
    if (!split) return [{ leg: null as string | null, files: payload.files }];
    const out: { leg: string | null; files: DiffFileEntry[] }[] = [];
    const placed = new Set<string>();
    for (const leg of LEG_ORDER) {
      const files = payload.files.filter((f) => f.legs?.includes(leg) && !placed.has(f.path));
      for (const f of files) placed.add(f.path);
      if (files.length > 0) out.push({ leg, files });
    }
    const rest = payload.files.filter((f) => !placed.has(f.path));
    if (rest.length > 0) out.push({ leg: null, files: rest });
    return out;
  }, [payload, split]);

  return (
    <div data-anchor={anchor.changesPanel}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-16)",
          flexWrap: "wrap",
          marginBottom: "var(--wb-space-12)",
        }}
      >
        <SegmentedControl
          ariaLabel="Diff mode"
          options={MODE_OPTIONS}
          value={mode}
          onChange={(next) => {
            setMode(next);
            setApplied(null);
          }}
        />
        {mode === "working" || mode === "uncommitted" ? (
          <Toggle
            checked={split}
            onChange={setSplit}
            label="Split staged / unstaged"
            disabled={!hasLegs}
          />
        ) : null}
        {bundle ? (
          <Toggle checked={allFiles} onChange={setAllFiles} label="All changed files" />
        ) : null}
      </div>

      {needsRevs ? (
        <form
          style={{
            display: "flex",
            gap: "var(--wb-space-8)",
            alignItems: "center",
            flexWrap: "wrap",
            marginBottom: "var(--wb-space-12)",
          }}
          onSubmit={(e) => {
            e.preventDefault();
            setApplied({ base: baseText.trim(), target: targetText.trim() });
          }}
        >
          <input
            style={revInputStyle}
            value={baseText}
            onChange={(e) => setBaseText(e.target.value)}
            placeholder={mode === "commit" ? "commit id" : "base commit"}
            aria-label={mode === "commit" ? "Commit id" : "Base commit"}
          />
          {mode === "range" ? (
            <input
              style={revInputStyle}
              value={targetText}
              onChange={(e) => setTargetText(e.target.value)}
              placeholder="target commit"
              aria-label="Target commit"
            />
          ) : null}
          <Button type="submit" variant="secondary">
            Show diff
          </Button>
        </form>
      ) : null}

      {needsRevs && applied == null ? (
        <EmptyWell>
          {mode === "commit"
            ? "Name a commit to see its own change."
            : "Name a base and a target commit to see the range diff."}
        </EmptyWell>
      ) : query.isPending ? (
        <SkeletonWell label="the diff" />
      ) : query.isError || !payload ? (
        <ErrorWell
          section="Changes"
          message={query.data?.error ?? "the diff could not be loaded."}
        />
      ) : (
        <>
          <p
            style={{
              color: "var(--wb-content-secondary)",
              margin: "0 0 var(--wb-space-12)",
              fontSize: "var(--wb-font-size-sm)",
            }}
          >
            <span className="mono">{payload.base ?? "—"}</span>
            {" → "}
            <span className="mono">{payload.target ?? "—"}</span>
            {" · "}
            <span className="num">{payload.totals.files}</span> files ·{" "}
            <span className="num">+{payload.totals.additions}</span> /{" "}
            <span className="num">−{payload.totals.deletions}</span>
            {payload.narrowed ? " · narrowed to the plan's declared files" : ""}
          </p>
          {payload.warnings.map((warning) => (
            <div
              key={`${warning.kind}:${warning.path}`}
              style={{ marginBottom: "var(--wb-space-8)" }}
            >
              <KitBanner
                tone="degraded"
                message={warning.message}
                detail={`File: ${warning.path}`}
              />
            </div>
          ))}
          {payload.empty ? (
            <EmptyWell>No changes in this worktree for this view.</EmptyWell>
          ) : (
            groups?.map((group) => (
              <div key={group.leg ?? "all"}>
                {group.leg ? (
                  <h3
                    style={{
                      fontSize: "var(--wb-font-size-base)",
                      margin: "var(--wb-space-16) 0 var(--wb-space-8)",
                    }}
                  >
                    {LEG_LABEL[group.leg]}
                  </h3>
                ) : null}
                {group.files.map((file) => (
                  <DiffFileGroup key={file.path} file={file} />
                ))}
              </div>
            ))
          )}
          <UntrackedGroup items={payload.untracked} />
          <IgnoredGroup
            slug={slug}
            worktree={payload.anchor.worktree}
            items={payload.ignored_changed}
            truncated={payload.ignored_truncated}
          />
        </>
      )}
    </div>
  );
}

/** The worktree-anchored entry: a worktree picker over the
 * §6 derivations + the Changes panel for the selected
 * worktree. Lives on the Plans section landing until the
 * repo-home Overview (B1 UI) gives worktrees their own
 * drill-in — the panel itself moves unchanged. */
export function WorktreeChanges({ slug }: { slug: string }) {
  const query = useQuery({
    queryKey: ["worktrees", slug],
    queryFn: () => api.getWorktrees({ slug }),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const payload = query.data?.payload as unknown as WorktreesPayload | null;
  const worktrees = payload?.worktrees ?? [];
  const value =
    selected ??
    worktrees.find((w) => w.is_main)?.branch ??
    worktrees[0]?.branch ??
    worktrees[0]?.path ??
    null;

  return (
    <section data-anchor={anchor.changesWorktrees} style={{ marginTop: "var(--wb-space-24)" }}>
      <h2
        style={{
          fontSize: "var(--wb-font-size-lg)",
          lineHeight: "var(--wb-line-height-lg)",
          margin: "0 0 var(--wb-space-8)",
        }}
      >
        Worktree changes
      </h2>
      {query.isPending ? (
        <SkeletonWell label="worktrees" />
      ) : query.isError || !payload ? (
        <ErrorWell
          section="Changes"
          message={query.data?.error ?? "the worktree list could not be loaded."}
        />
      ) : !payload.available || worktrees.length === 0 ? (
        <EmptyWell>No worktrees to show{payload.reason ? ` — ${payload.reason}` : ""}.</EmptyWell>
      ) : (
        <>
          <div style={{ marginBottom: "var(--wb-space-12)" }}>
            <SegmentedControl
              ariaLabel="Worktree"
              options={worktrees.map((w) => ({
                value: w.branch ?? w.path,
                label: w.branch ?? w.path,
              }))}
              value={value ?? ""}
              onChange={setSelected}
            />
          </div>
          {value ? <ChangesPanel slug={slug} worktree={value} /> : null}
        </>
      )}
    </section>
  );
}
