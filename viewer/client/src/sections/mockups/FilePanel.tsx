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
              <li
                key={file.path}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--wb-space-8)",
                  padding: "var(--wb-space-4) 0",
                }}
              >
                <Button
                  variant={selected === file.path ? "secondary" : "ghost"}
                  onClick={() => setSelected(file.path)}
                >
                  <span className="mono">{file.path}</span>
                </Button>
                {file.is_main ? (
                  <span style={{ color: "var(--wb-content-muted)" }}>main file</span>
                ) : null}
                {configPath && file.path === configPath ? (
                  <span style={{ color: "var(--wb-content-muted)" }}>config</span>
                ) : null}
                <span className="num" style={{ color: "var(--wb-content-muted)" }}>
                  {file.size_bytes} B
                </span>
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
            <p style={{ color: "var(--wb-content-muted)" }}>
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
        <p style={{ color: "var(--wb-content-muted)" }}>Peeking {path}…</p>
      ) : peekEnvelope && peekEnvelope.status !== 200 ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          {peekEnvelope.error ?? "The file could not be peeked."}
        </p>
      ) : peek ? (
        <>
          <p style={{ ...monoStyle, color: "var(--wb-content-muted)", overflowWrap: "anywhere" }}>
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
