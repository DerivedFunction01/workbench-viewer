// Entry files: list + guarded peek/save (SPEC §7.1). A peek
// returns content + sha + editable + reason; a save carries
// the peek's sha and a mismatch answers 409 — surfaced here
// as a conflict notice, nothing written. In the deployed
// config editing is OFF: the panel presents that truthfully
// (read-only content, the server's own reason, no fake save).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { api } from "../../lib/api";
import { formatShortHash } from "../../lib/format";
import type { EntryFile, Envelope, PeekResult } from "./types";

const monoStyle: React.CSSProperties = {
  fontFamily: "var(--wb-font-mono)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
};

export function FilePanel({
  slug,
  entryId,
  files,
  configPath,
  onMutated,
}: {
  slug: string;
  entryId: string;
  files: EntryFile[];
  configPath: string | null;
  onMutated: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <Card title="Files">
      {files.length === 0 ? (
        <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
          No local files — this entry is held by reference, so there is nothing to peek.
        </p>
      ) : (
        <>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {files.map((file) => (
              <li key={file.path}>
                {/* The row IS the action (F6): a full-width
                    row button at row height, not a kit
                    Button squeezed into a list row. The
                    path and its annotations are the row's
                    content; the selected row takes the
                    pressed-row surface. */}
                <button
                  type="button"
                  aria-pressed={selected === file.path}
                  onClick={() => setSelected(file.path)}
                  className="focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-1 focus-visible:outline-(--wb-focus-ring)"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--wb-space-8)",
                    width: "100%",
                    minHeight: "max(38px, var(--wb-row-height))",
                    padding: "var(--wb-space-4) var(--wb-space-8)",
                    textAlign: "left",
                    cursor: "pointer",
                    background: selected === file.path ? "var(--wb-surface-1)" : "transparent",
                    border:
                      selected === file.path
                        ? "1px solid var(--wb-border-strong)"
                        : "1px solid transparent",
                    borderRadius: "var(--wb-radius-md)",
                    color: "var(--wb-content-primary)",
                  }}
                >
                  <span className="mono" style={{ overflowWrap: "anywhere" }}>
                    {file.path}
                  </span>
                  {file.is_main ? (
                    <span style={{ color: "var(--wb-content-secondary)" }}>main file</span>
                  ) : null}
                  {configPath && file.path === configPath ? (
                    <span style={{ color: "var(--wb-content-secondary)" }}>config</span>
                  ) : null}
                  <span className="num" style={{ color: "var(--wb-content-secondary)" }}>
                    {file.size_bytes} B
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {selected != null ? (
            <PeekView
              key={selected}
              slug={slug}
              entryId={entryId}
              path={selected}
              onMutated={onMutated}
            />
          ) : (
            <p style={{ color: "var(--wb-content-secondary)" }}>
              Select a file to peek it (content + sha + editability).
            </p>
          )}
        </>
      )}
    </Card>
  );
}

function PeekView({
  slug,
  entryId,
  path,
  onMutated,
}: {
  slug: string;
  entryId: string;
  path: string;
  onMutated: () => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  const peekQuery = useQuery({
    queryKey: ["entry-file", slug, entryId, path],
    queryFn: () => api.getEntryFile({ slug, entryId, path }),
  });
  const peekEnvelope = peekQuery.data as Envelope | undefined;
  const peek =
    peekEnvelope && peekEnvelope.status === 200 ? (peekEnvelope.payload as PeekResult) : null;
  const effectiveDraft = draft ?? peek?.content ?? "";

  const saveMutation = useMutation({
    mutationFn: (args: { content: string; baseSha256: string }) =>
      api.saveEntryFile({
        slug,
        entryId,
        path,
        content: args.content,
        baseSha256: args.baseSha256,
      }) as Promise<Envelope>,
    onSuccess: (result) => {
      if (result.status === 200) {
        setNotice("Saved — the save is recorded in the entry's history.");
        setConflict(null);
        setDraft(null);
        queryClient.invalidateQueries({ queryKey: ["entry-file", slug, entryId] });
        queryClient.invalidateQueries({ queryKey: ["entry", slug, entryId] });
        onMutated();
      } else if (result.status === 409) {
        setConflict(
          `${result.error ?? "The file changed on disk since it was opened."} Nothing was written — peek the file again to see the current content.`,
        );
      } else {
        setConflict(result.error ?? `Save refused (status ${result.status}). Nothing was written.`);
      }
    },
  });

  return (
    <div style={{ marginTop: "var(--wb-space-12)" }}>
      {peekQuery.isPending ? (
        <p style={{ color: "var(--wb-content-secondary)" }}>Peeking {path}…</p>
      ) : peekEnvelope && peekEnvelope.status !== 200 ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          {peekEnvelope.error ?? "The file could not be peeked."}
        </p>
      ) : peek ? (
        <>
          <p
            style={{ ...monoStyle, color: "var(--wb-content-secondary)", overflowWrap: "anywhere" }}
          >
            sha256 {peek.sha256 ?? "—"}
            {peek.truncated ? " · truncated at the peek caps" : ""}
            {peek.line_count != null ? ` · ${peek.line_count} lines` : ""}
          </p>
          {peek.withheld === "secret" ? (
            <p role="alert" style={{ color: "var(--wb-danger)" }}>
              Withheld — this path is secret-shaped and is never shown here.
            </p>
          ) : peek.is_binary ? (
            <p style={{ color: "var(--wb-content-secondary)" }}>
              Binary file — no text preview. sha {formatShortHash(peek.sha256)} identifies its
              current content.
            </p>
          ) : peek.editable ? (
            <>
              <textarea
                aria-label={`Content of ${peek.path}`}
                value={effectiveDraft}
                onChange={(event) => setDraft(event.target.value)}
                rows={14}
                style={{
                  ...monoStyle,
                  width: "100%",
                  background: "var(--wb-surface-sunken)",
                  color: "var(--wb-content-primary)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-radius-md)",
                  padding: "var(--wb-space-8)",
                }}
              />
              <div
                style={{
                  display: "flex",
                  gap: "var(--wb-space-8)",
                  marginTop: "var(--wb-space-8)",
                }}
              >
                <Button
                  disabled={
                    saveMutation.isPending || effectiveDraft === peek.content || peek.sha256 == null
                  }
                  onClick={() => {
                    if (peek.sha256) {
                      saveMutation.mutate({
                        content: effectiveDraft,
                        baseSha256: peek.sha256,
                      });
                    }
                  }}
                >
                  Save file
                </Button>
              </div>
            </>
          ) : (
            <>
              <pre
                style={{
                  ...monoStyle,
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                  maxHeight: "320px",
                  overflow: "auto",
                  background: "var(--wb-surface-sunken)",
                  border: "1px solid var(--wb-border-default)",
                  borderRadius: "var(--wb-radius-md)",
                  padding: "var(--wb-space-8)",
                  margin: 0,
                }}
              >
                {peek.content}
              </pre>
              <p style={{ color: "var(--wb-content-secondary)" }}>
                Read-only — {peek.editable_reason ?? "not editable"}.
                {peek.editable_reason === "editing disabled"
                  ? " File editing is disabled in the server config, so no save is offered."
                  : ""}
              </p>
            </>
          )}
          {conflict ? (
            <p role="alert" style={{ color: "var(--wb-danger)" }}>
              {conflict}
            </p>
          ) : null}
          {notice ? (
            <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
              {notice}
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
