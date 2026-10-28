// The Files tab's peek pane (absorption plan, step 8):
// opens on CONTENT; the file's diff against HEAD is the
// second view of the Content | Diff toggle (the peek's
// `diff` field — a raw unified-diff string, null when the
// file matches HEAD). A dataset-kind file (the peek's
// `dataset` descriptor) adds a TABLE view between them
// (datasets plan, steps 5-6); it is the default view for
// a binary dataset, whose Content is metadata only.
// Secret-shaped files arrive
// withheld: the content is fetched only after a per-file
// reveal confirm, through a direct call that bypasses
// the query cache entirely, and dropped on hide / file
// change — revealed content is never cached. Binary is
// metadata only; Edit is offered exactly when the peek
// says editable, with the server's reason when not.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/Button";
import { SegmentedControl } from "../../components/SegmentedControl";
import { api, type RepoPeek } from "../../lib/api";
import { formatShortHash } from "../../lib/format";
import { highlightCode, highlightLines } from "../../lib/highlight";
import { DatasetTable } from "./DatasetTable";

const codeStyle: React.CSSProperties = {
  fontFamily: "var(--wb-font-mono)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  background: "var(--wb-surface-sunken)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-12)",
  overflow: "auto",
  whiteSpace: "pre",
  margin: 0,
};

/** Whole-file content with highlight.js coloring via
 * the shared helper (lib/highlight): the path's mapped
 * language, else an auto-detect fallback, else plain
 * text — never a hole. */
function CodeView({ path, content }: { path: string; content: string }) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    setHtml(null);
    let live = true;
    void highlightCode(content, path).then((out) => {
      if (live) setHtml(out);
    });
    return () => {
      live = false;
    };
  }, [content, path]);
  if (html == null) return <pre style={codeStyle}>{content}</pre>;
  // biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js escapes the source text itself; its output is span markup only (the SourceView pattern)
  return <pre style={codeStyle} dangerouslySetInnerHTML={{ __html: html }} />;
}

type DiffLineKind = "add" | "del" | "hunk" | "meta" | "context";

function diffLineKind(line: string): DiffLineKind {
  if (line.startsWith("+") && !line.startsWith("+++")) return "add";
  if (line.startsWith("-") && !line.startsWith("---")) return "del";
  if (line.startsWith("@@")) return "hunk";
  if (
    line.startsWith("diff ") ||
    line.startsWith("index ") ||
    line.startsWith("---") ||
    line.startsWith("+++") ||
    line.startsWith("\\")
  )
    return "meta";
  return "context";
}

/** The raw unified diff, line-tinted by its own prefix
 * (the diff format's markers, rendered — the string is
 * served whole; nothing is re-derived). Code lines
 * (context / add / del) are additionally syntax-
 * highlighted per line with the file's language, under
 * the tint: the marker character stays plain text, only
 * the code after it is highlighted. Header and hunk
 * lines stay plain, as before. */
function RawDiffView({ path, diff }: { path: string; diff: string }) {
  const lines = useMemo(() => diff.replace(/\n$/, "").split("\n"), [diff]);
  const [html, setHtml] = useState<Map<number, string> | null>(null);
  useEffect(() => {
    setHtml(null);
    const codeIdx: number[] = [];
    const texts: string[] = [];
    lines.forEach((line, i) => {
      const kind = diffLineKind(line);
      if (kind === "add" || kind === "del" || kind === "context") {
        codeIdx.push(i);
        texts.push(line.slice(1));
      }
    });
    let live = true;
    void highlightLines(texts, path).then((out) => {
      if (!live || !out) return;
      const map = new Map<number, string>();
      codeIdx.forEach((lineIdx, j) => {
        const h = out[j];
        if (h != null) map.set(lineIdx, h);
      });
      setHtml(map);
    });
    return () => {
      live = false;
    };
  }, [lines, path]);
  return (
    <div
      style={{
        ...codeStyle,
        padding: "var(--wb-space-8) 0",
      }}
    >
      {lines.map((line, i) => {
        const kind = diffLineKind(line);
        const highlighted = html?.get(i);
        return (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: diff lines are positional and the list is immutable per peek
            key={i}
            style={{
              whiteSpace: "pre",
              padding: "0 var(--wb-space-12)",
              background:
                kind === "add"
                  ? "color-mix(in srgb, var(--wb-status-implemented) 13%, transparent)"
                  : kind === "del"
                    ? "color-mix(in srgb, var(--wb-status-hard-gate) 11%, transparent)"
                    : undefined,
              color: kind === "hunk" || kind === "meta" ? "var(--wb-content-muted)" : undefined,
            }}
          >
            {line === "" ? (
              " "
            ) : highlighted != null ? (
              <>
                {line.slice(0, 1)}
                {/* biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js escapes the line text itself; its output is span markup only (the SourceView pattern) */}
                <span dangerouslySetInnerHTML={{ __html: highlighted }} />
              </>
            ) : (
              line
            )}
          </div>
        );
      })}
    </div>
  );
}

type PeekView = "content" | "table" | "diff";

export function PeekPane({
  repoId,
  path,
  onEdit,
}: {
  repoId: string;
  path: string;
  onEdit: (peek: RepoPeek) => void;
}) {
  // Null = no explicit choice yet: the default view is
  // derived from the peek when it lands (see below).
  const [view, setView] = useState<PeekView | null>(null);
  const [revealed, setRevealed] = useState<RepoPeek | null>(null);
  const [confirmingReveal, setConfirmingReveal] = useState(false);
  const [revealError, setRevealError] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);

  // A new file starts unrevealed, on Content, with no
  // confirm armed (the render-once rule: state resets are
  // keyed by the file, mounted fresh by the parent via
  // `key`, so these initial values are the reset).
  const query = useQuery({
    queryKey: ["repo-file", repoId, path],
    queryFn: () => api.getRepoFile({ repoId, path }),
  });
  const envelope = query.data;
  const basePeek =
    envelope && envelope.status === 200 ? (envelope.payload as unknown as RepoPeek) : null;
  const peek = revealed ?? basePeek;

  const doReveal = async () => {
    setRevealing(true);
    setRevealError(null);
    try {
      const reply = await api.getRepoFile({ repoId, path, reveal: true });
      if (reply.status === 200 && reply.payload) {
        setRevealed(reply.payload as unknown as RepoPeek);
        setConfirmingReveal(false);
      } else {
        setRevealError(reply.error ?? "the reveal was refused.");
      }
    } catch {
      setRevealError("the reveal call failed.");
    } finally {
      setRevealing(false);
    }
  };

  if (query.isPending) {
    return (
      <p style={{ color: "var(--wb-content-muted)", padding: "var(--wb-space-12)" }}>
        Peeking <span className="mono">{path}</span>…
      </p>
    );
  }
  if (!basePeek) {
    return (
      <p role="alert" style={{ color: "var(--wb-danger)", padding: "var(--wb-space-12)" }}>
        {envelope?.error ?? "The file could not be peeked."}
      </p>
    );
  }

  const isRevealedSecret = peek?.revealed === true;
  const dataset = peek?.dataset ?? null;
  // The default view: Content when the file serves text;
  // a binary dataset (no content to show) opens on its
  // Table. An explicit toggle choice always wins.
  const defaultView: PeekView = dataset && peek?.content == null ? "table" : "content";
  const activeView = view ?? defaultView;
  return (
    <div data-anchor="repos/peek" style={{ padding: "var(--wb-space-12)", minWidth: 0 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-12)",
          flexWrap: "wrap",
          marginBottom: "var(--wb-space-12)",
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: "var(--wb-font-size-sm)",
            fontWeight: 600,
            overflowWrap: "anywhere",
            minWidth: 0,
          }}
        >
          {path}
        </span>
        <SegmentedControl
          ariaLabel="Peek view"
          options={[
            { value: "content", label: "Content" },
            ...(dataset ? [{ value: "table", label: "Table" }] : []),
            { value: "diff", label: "Diff vs HEAD" },
          ]}
          value={activeView}
          onChange={(next) => setView(next as PeekView)}
        />
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: "var(--wb-space-8)" }}>
          {isRevealedSecret ? (
            <Button
              variant="ghost"
              onClick={() => {
                setRevealed(null);
                setConfirmingReveal(false);
              }}
            >
              Hide
            </Button>
          ) : null}
          {
            // biome-ignore lint/complexity/useOptionalChain: the && form narrows peek to non-null for the onEdit argument — peek?.editable would leave the callback's argument un-narrowed
            peek && peek.editable ? (
              <Button variant="secondary" onClick={() => onEdit(peek)}>
                Edit
              </Button>
            ) : null
          }
        </span>
      </div>

      <p
        className="mono"
        style={{
          fontSize: "var(--wb-font-size-xs)",
          color: "var(--wb-content-muted)",
          overflowWrap: "anywhere",
          margin: "0 0 var(--wb-space-12)",
        }}
      >
        sha256 {peek?.sha256 ? formatShortHash(peek.sha256) : "—"} ·{" "}
        <span className="num">{peek?.size_bytes ?? 0}</span> B
        {peek?.line_count != null ? (
          <>
            {" "}
            · <span className="num">{peek.line_count}</span> lines
          </>
        ) : null}
        {peek?.truncated ? " · truncated at the peek caps" : ""}
        {isRevealedSecret ? " · revealed for this view only" : ""}
      </p>

      {activeView === "diff" ? (
        peek?.diff ? (
          <RawDiffView path={path} diff={peek.diff} />
        ) : (
          <p style={{ color: "var(--wb-content-secondary)" }}>
            No changes vs HEAD — the working file matches the committed one.
          </p>
        )
      ) : activeView === "table" && dataset ? (
        <DatasetTable repoId={repoId} path={path} descriptor={dataset} />
      ) : peek?.withheld === "secret" ? (
        <div
          style={{
            border: "1px solid var(--wb-border-strong)",
            borderRadius: "var(--wb-radius-md)",
            padding: "var(--wb-space-16)",
          }}
        >
          <p style={{ margin: "0 0 var(--wb-space-8)", fontWeight: 600 }}>
            Withheld — secret-shaped path
          </p>
          <p style={{ margin: "0 0 var(--wb-space-12)", color: "var(--wb-content-secondary)" }}>
            This file's name matches the secret patterns, so its content is not served. Reveal it
            only if you need it here — the revealed content is shown for this view only and never
            cached.
          </p>
          {confirmingReveal ? (
            <span style={{ display: "inline-flex", gap: "var(--wb-space-8)", flexWrap: "wrap" }}>
              <Button variant="danger" disabled={revealing} onClick={() => void doReveal()}>
                Confirm: reveal {path}
              </Button>
              <Button variant="ghost" onClick={() => setConfirmingReveal(false)}>
                Cancel
              </Button>
            </span>
          ) : (
            <Button variant="secondary" onClick={() => setConfirmingReveal(true)}>
              Reveal file
            </Button>
          )}
          {revealError ? (
            <p role="alert" style={{ color: "var(--wb-danger)" }}>
              {revealError}
            </p>
          ) : null}
        </div>
      ) : peek?.is_binary ? (
        <p style={{ color: "var(--wb-content-secondary)" }}>
          Binary file — metadata only, no text preview. Its sha identifies the current content.
        </p>
      ) : peek?.content != null ? (
        <>
          <CodeView path={path} content={peek.content} />
          {!peek.editable ? (
            <p style={{ color: "var(--wb-content-secondary)", marginTop: "var(--wb-space-8)" }}>
              Read-only — {peek.editable_reason ?? "not editable"}.
              {peek.editable_reason === "editing disabled"
                ? " File editing is disabled in the server config, so no save is offered."
                : ""}
            </p>
          ) : null}
          {peek.truncated ? (
            <p style={{ color: "var(--wb-content-secondary)", marginTop: "var(--wb-space-8)" }}>
              Truncated at the peek caps — the whole file is larger than what is shown, so it cannot
              be edited from here.
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
