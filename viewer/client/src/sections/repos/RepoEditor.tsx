// The repo file editor (absorption plan, step 9): a
// FULL-SCREEN takeover on both form factors (the owner's
// pick) — not a modal, not inline. The editing surface is
// the reference viewer's machinery re-derived in house
// idiom: a transparent textarea over a synchronised
// highlighted layer (lazy highlight.js, the SourceView
// pattern), Tab / Shift+Tab indent with the configured
// unit, and the guarded save of lib/files.py underneath:
// sha compare-and-swap (a stale sha is a 409 — nothing
// written — answered here with reload-to-current or
// discard), and confirm_secret on the save when the file
// was revealed. Closing with unsaved changes arms the
// discard guard first — a close never silently drops a
// draft.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { SegmentedControl } from "../../components/SegmentedControl";
import { api, type RepoPeek, type RepoSaveResult } from "../../lib/api";
import { formatShortHash } from "../../lib/format";
import { detectLanguage, highlightWithLanguage } from "../../lib/highlight";

export type IndentUnit = "2 spaces" | "4 spaces" | "tab";

const INDENT_OPTIONS: { value: IndentUnit; label: string }[] = [
  { value: "2 spaces", label: "2 spaces" },
  { value: "4 spaces", label: "4 spaces" },
  { value: "tab", label: "Tab" },
];

const INDENT_STORAGE_KEY = "wb-viewer.editor-indent";

function indentString(unit: IndentUnit): string {
  return unit === "4 spaces" ? "    " : unit === "tab" ? "\t" : "  ";
}

function loadIndentUnit(): IndentUnit {
  try {
    const raw = localStorage.getItem(INDENT_STORAGE_KEY);
    if (raw === "4 spaces" || raw === "tab") return raw;
  } catch {
    // Storage unavailable: the default applies.
  }
  return "2 spaces";
}

const layerStyle: React.CSSProperties = {
  fontFamily: "var(--wb-font-mono)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  padding: "var(--wb-space-12)",
  whiteSpace: "pre",
  tabSize: 4,
};

export function RepoEditor({
  repoId,
  initialPeek,
  onClose,
}: {
  repoId: string;
  initialPeek: RepoPeek;
  /** `saved` = a save landed during the session (the
   * caller refreshes the peek either way). */
  onClose: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const path = initialPeek.path;
  const [base, setBase] = useState<RepoPeek>(initialPeek);
  const [draft, setDraft] = useState<string>(initialPeek.content ?? "");
  const [indentUnit, setIndentUnit] = useState<IndentUnit>(loadIndentUnit);
  const [conflict, setConflict] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [guard, setGuard] = useState<"discard" | "secret" | null>(null);
  const [savedOnce, setSavedOnce] = useState(false);
  const [html, setHtml] = useState<string | null>(null);

  const taRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);
  const pendingSelection = useRef<{ start: number; end: number } | null>(null);

  const dirty = draft !== (base.content ?? "");
  const isSecret = base.revealed === true;
  const [language, setLanguage] = useState<string | null>(null);

  // Detect the language ONCE per base content (the
  // shared helper: the path's mapped language, else an
  // auto-detect over the base text) — never per
  // keystroke, so the grammar cannot flip mid-edit.
  useEffect(() => {
    let live = true;
    void detectLanguage(base.content ?? "", path).then((lang) => {
      if (live) setLanguage(lang);
    });
    return () => {
      live = false;
    };
  }, [base, path]);

  // Highlight the draft in the detected language (lazy
  // chunk; falls back to plain text — the textarea shows
  // the highlighted layer through its transparent text,
  // so a missing highlight must still render the words:
  // the <code> falls back to the draft as text children
  // when html is null).
  useEffect(() => {
    if (!language) {
      setHtml(null);
      return;
    }
    let live = true;
    void highlightWithLanguage(draft, language).then((out) => {
      if (live) setHtml(out);
    });
    return () => {
      live = false;
    };
  }, [draft, language]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: draft is the trigger, not an input — the effect restores the caret after a programmatic (Tab-key) edit and reads only refs, whose identities are stable
  useLayoutEffect(() => {
    const sel = pendingSelection.current;
    const ta = taRef.current;
    if (sel && ta) {
      pendingSelection.current = null;
      ta.focus();
      ta.setSelectionRange(sel.start, sel.end);
    }
  }, [draft]);

  const syncScroll = () => {
    const ta = taRef.current;
    const pre = preRef.current;
    if (ta && pre) {
      pre.scrollTop = ta.scrollTop;
      pre.scrollLeft = ta.scrollLeft;
    }
  };

  const applyEdit = (next: string, selStart: number, selEnd: number) => {
    pendingSelection.current = { start: selStart, end: selEnd };
    setDraft(next);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Tab") return;
    event.preventDefault();
    const ta = taRef.current;
    if (!ta) return;
    const unit = indentString(indentUnit);
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const val = draft;
    const firstLineStart = val.lastIndexOf("\n", start - 1) + 1;
    const hasNewline = val.slice(start, end).includes("\n");

    if (!event.shiftKey && start === end) {
      applyEdit(
        val.slice(0, start) + unit + val.slice(end),
        start + unit.length,
        start + unit.length,
      );
      return;
    }
    if (!event.shiftKey && !hasNewline) {
      applyEdit(
        val.slice(0, start) + unit + val.slice(end),
        start + unit.length,
        start + unit.length,
      );
      return;
    }
    const regionEnd = event.shiftKey && start === end ? start : end;
    const lineEnd = val.indexOf("\n", regionEnd);
    const region = val.slice(firstLineStart, lineEnd === -1 ? val.length : lineEnd);
    const lines = region.split("\n");
    if (!event.shiftKey) {
      const indented = lines.map((line) => unit + line).join("\n");
      const next =
        val.slice(0, firstLineStart) + indented + val.slice(firstLineStart + region.length);
      applyEdit(next, start + unit.length, end + unit.length * lines.length);
    } else {
      let firstRemoved = 0;
      let totalRemoved = 0;
      const outdented = lines
        .map((line, i) => {
          let removed = 0;
          if (line.startsWith(unit)) removed = unit.length;
          else if (line.startsWith("\t")) removed = 1;
          else {
            const spaces = /^ +/.exec(line)?.[0].length ?? 0;
            removed = Math.min(spaces, unit === "\t" ? 1 : unit.length);
          }
          if (i === 0) firstRemoved = removed;
          totalRemoved += removed;
          return line.slice(removed);
        })
        .join("\n");
      const next =
        val.slice(0, firstLineStart) + outdented + val.slice(firstLineStart + region.length);
      const newStart = Math.max(firstLineStart, start - firstRemoved);
      const newEnd = Math.max(newStart, end - totalRemoved);
      applyEdit(next, newStart, newEnd);
    }
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      api.saveRepoFile({
        repoId,
        path,
        content: draft,
        baseSha256: base.sha256 ?? "",
        confirmSecret: isSecret,
      }),
    onSuccess: (reply) => {
      setGuard(null);
      if (reply.status === 200 && reply.payload) {
        const saved = reply.payload as unknown as RepoSaveResult;
        setBase({ ...base, content: draft, sha256: saved.sha256, size_bytes: saved.size_bytes });
        setConflict(null);
        setError(null);
        setSavedOnce(true);
        setNotice(
          `Saved — sha ${formatShortHash(saved.sha256)}; the previous version is kept as a backup.`,
        );
        void queryClient.invalidateQueries({ queryKey: ["repo-file", repoId, path] });
        void queryClient.invalidateQueries({ queryKey: ["repo-status", repoId] });
        void queryClient.invalidateQueries({ queryKey: ["repos"] });
      } else if (reply.status === 409) {
        setConflict(
          `${reply.error ?? "The file changed on disk since it was opened."} Nothing was written.`,
        );
      } else {
        setError(reply.error ?? `Save refused (status ${reply.status}). Nothing was written.`);
      }
    },
    onError: () => setError("The save call failed. Nothing was written."),
  });

  const reloadCurrent = async () => {
    setError(null);
    try {
      const reply = await api.getRepoFile({ repoId, path, reveal: isSecret || undefined });
      if (reply.status === 200 && reply.payload) {
        const fresh = reply.payload as unknown as RepoPeek;
        setBase(fresh);
        setDraft(fresh.content ?? "");
        setConflict(null);
        setNotice("Reloaded the current on-disk content — your unsaved edits were replaced.");
      } else {
        setError(reply.error ?? "The current content could not be reloaded.");
      }
    } catch {
      setError("The reload call failed.");
    }
  };

  const requestClose = () => {
    if (dirty) {
      setGuard("discard");
      return;
    }
    onClose(savedOnce);
  };

  return (
    <div
      data-anchor="repos/editor"
      role="dialog"
      aria-modal="true"
      aria-label={`Edit ${path}`}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 40,
        display: "flex",
        flexDirection: "column",
        background: "var(--wb-surface-canvas)",
        color: "var(--wb-content-primary)",
        fontFamily: "var(--wb-font-ui)",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-12)",
          flexWrap: "wrap",
          padding: "var(--wb-space-12) var(--wb-space-16)",
          borderBottom: "1px solid var(--wb-border-default)",
          background: "var(--wb-surface-1)",
        }}
      >
        <Button variant="ghost" onClick={requestClose}>
          ← Close
        </Button>
        <span
          className="mono"
          style={{ fontSize: "var(--wb-font-size-sm)", fontWeight: 600, overflowWrap: "anywhere" }}
        >
          {path}
        </span>
        <span
          className="mono"
          style={{
            fontSize: "var(--wb-font-size-xs)",
            color: "var(--wb-content-muted)",
          }}
        >
          {repoId} · base sha {formatShortHash(base.sha256)}
        </span>
        <span
          role="status"
          style={{
            fontSize: "var(--wb-font-size-xs)",
            color: dirty ? "var(--wb-status-stale-text)" : "var(--wb-content-muted)",
          }}
        >
          {dirty ? "Unsaved changes" : "No changes"}
        </span>
        <span
          style={{
            marginLeft: "auto",
            display: "inline-flex",
            gap: "var(--wb-space-12)",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <SegmentedControl
            ariaLabel="Indent unit"
            options={INDENT_OPTIONS}
            value={indentUnit}
            onChange={(next) => {
              setIndentUnit(next);
              try {
                localStorage.setItem(INDENT_STORAGE_KEY, next);
              } catch {
                // Preference applies for the session regardless.
              }
            }}
          />
          <Button
            disabled={!dirty || saveMutation.isPending}
            onClick={() => {
              if (isSecret) {
                setGuard("secret");
                return;
              }
              saveMutation.mutate();
            }}
          >
            Save file
          </Button>
        </span>
      </header>

      {guard === "discard" ? (
        <div
          role="alert"
          style={{
            display: "flex",
            gap: "var(--wb-space-8)",
            alignItems: "center",
            flexWrap: "wrap",
            padding: "var(--wb-space-8) var(--wb-space-16)",
            background: "color-mix(in srgb, var(--wb-status-stale) 14%, transparent)",
            borderBottom: "1px solid var(--wb-status-stale)",
          }}
        >
          <span style={{ fontSize: "var(--wb-font-size-sm)" }}>
            You have unsaved changes in {path}. Discard them and close?
          </span>
          <Button variant="danger" onClick={() => onClose(savedOnce)}>
            Discard changes
          </Button>
          <Button variant="ghost" onClick={() => setGuard(null)}>
            Keep editing
          </Button>
        </div>
      ) : null}

      {guard === "secret" ? (
        <div
          role="alert"
          style={{
            display: "flex",
            gap: "var(--wb-space-8)",
            alignItems: "center",
            flexWrap: "wrap",
            padding: "var(--wb-space-8) var(--wb-space-16)",
            background: "color-mix(in srgb, var(--wb-status-stale) 14%, transparent)",
            borderBottom: "1px solid var(--wb-status-stale)",
          }}
        >
          <span style={{ fontSize: "var(--wb-font-size-sm)" }}>
            {path} is secret-shaped. Saving writes its real content to disk — confirm only if that
            is what you intend.
          </span>
          <Button
            variant="danger"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
          >
            Confirm: save secret file
          </Button>
          <Button variant="ghost" onClick={() => setGuard(null)}>
            Cancel
          </Button>
        </div>
      ) : null}

      {conflict ? (
        <div
          role="alert"
          style={{
            display: "flex",
            gap: "var(--wb-space-8)",
            alignItems: "center",
            flexWrap: "wrap",
            padding: "var(--wb-space-8) var(--wb-space-16)",
            background: "color-mix(in srgb, var(--wb-status-stale) 14%, transparent)",
            borderBottom: "1px solid var(--wb-status-stale)",
          }}
        >
          <span style={{ fontSize: "var(--wb-font-size-sm)", flex: 1, minWidth: "200px" }}>
            Conflict: {conflict}
          </span>
          <Button variant="secondary" onClick={() => void reloadCurrent()}>
            Reload current content
          </Button>
          <Button variant="ghost" onClick={() => onClose(savedOnce)}>
            Discard my changes
          </Button>
        </div>
      ) : null}

      {error ? (
        <p
          role="alert"
          style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) var(--wb-space-16)" }}
        >
          {error}
        </p>
      ) : null}
      {notice && !conflict ? (
        <p
          role="status"
          style={{
            color: "var(--wb-content-secondary)",
            margin: "var(--wb-space-8) var(--wb-space-16)",
          }}
        >
          {notice}
        </p>
      ) : null}

      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 0,
          background: "var(--wb-surface-sunken)",
        }}
      >
        <pre
          ref={preRef}
          aria-hidden="true"
          style={{
            ...layerStyle,
            position: "absolute",
            inset: 0,
            overflow: "hidden",
            margin: 0,
            pointerEvents: "none",
            color: "var(--wb-content-primary)",
          }}
        >
          {html != null ? (
            // biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js escapes the source text itself; its output is span markup only (the SourceView pattern)
            <code dangerouslySetInnerHTML={{ __html: html + (draft.endsWith("\n") ? " " : "") }} />
          ) : (
            <code>{draft}</code>
          )}
        </pre>
        <textarea
          ref={taRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          onScroll={syncScroll}
          aria-label={`Edit file ${path}`}
          spellCheck={false}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          wrap="off"
          style={{
            ...layerStyle,
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            resize: "none",
            overflow: "auto",
            background: "transparent",
            border: "none",
            outline: "none",
            color: "transparent",
            caretColor: "var(--wb-content-primary)",
            WebkitTextFillColor: "transparent",
          }}
        />
      </div>
    </div>
  );
}
