// The ONE message composer (repo-home spec §7 + D7):
// composing lives in exactly two places — the Inbox view,
// and an anchored comment box (AnchoredComment) that is
// this same component with the anchor preset. Drafts are
// state=draft messages from the first save (the §5.3
// draft TTL applies to them); Send creates the message
// already sent. Messages from the artifact are the owner's
// (§7.1) — author is fixed here, never a free field.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/Button";
import { api } from "../../lib/api";
import { metaStyle } from "../shared";

const ANCHOR_TYPES = ["none", "plan", "todo", "entry", "repo"] as const;

const fieldStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  color: "var(--wb-content-primary)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-8)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
};

export interface ComposerProject {
  slug: string;
  name: string;
}

export function MessageComposer({
  projects,
  fixedProject,
  presetAnchor,
  parentId,
  onPosted,
}: {
  projects: ComposerProject[];
  /** When set (a slug, or null for workspace-wide), the
   * project is fixed and no select renders. */
  fixedProject?: string | null;
  presetAnchor?: { type: string; ref: string };
  parentId?: number | null;
  onPosted?: () => void;
}) {
  const queryClient = useQueryClient();
  const [project, setProject] = useState<string>(
    fixedProject !== undefined ? (fixedProject ?? "") : (projects[0]?.slug ?? ""),
  );
  const [body, setBody] = useState("");
  const [anchorType, setAnchorType] = useState(presetAnchor?.type ?? "none");
  const [anchorRef, setAnchorRef] = useState(presetAnchor?.ref ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (send: boolean) =>
      api.createMessage({
        body: {
          author: "owner",
          body,
          project_slug: fixedProject !== undefined ? fixedProject : project || null,
          anchor_type: presetAnchor?.type ?? anchorType,
          anchor_ref: (presetAnchor?.ref ?? anchorRef) || null,
          parent_id: parentId ?? null,
          send,
        },
      }),
    onSuccess: (result) => {
      if (result.payload == null) {
        setError(result.error ?? "the message could not be saved.");
        return;
      }
      setBody("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["messages"] });
      onPosted?.();
    },
    onError: () => setError("the message could not be saved."),
  });

  const canPost = body.trim().length > 0 && !mutation.isPending;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--wb-space-8)",
      }}
    >
      <textarea
        aria-label={parentId ? "Reply" : "Message"}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        rows={parentId ? 3 : 4}
        placeholder={parentId ? "Reply on this thread…" : "Write a message for an agent session…"}
        style={{ ...fieldStyle, width: "100%", resize: "vertical" }}
      />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-8)",
          flexWrap: "wrap",
        }}
      >
        {fixedProject === undefined ? (
          <select
            aria-label="Project"
            value={project}
            onChange={(event) => setProject(event.target.value)}
            style={fieldStyle}
          >
            <option value="">Workspace-wide</option>
            {projects.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name}
              </option>
            ))}
          </select>
        ) : null}
        {presetAnchor ? (
          <span style={metaStyle}>
            anchored to {presetAnchor.type} · <span className="mono">{presetAnchor.ref}</span>
          </span>
        ) : parentId ? null : (
          <>
            <select
              aria-label="Anchor type"
              value={anchorType}
              onChange={(event) => setAnchorType(event.target.value)}
              style={fieldStyle}
            >
              {ANCHOR_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t === "none" ? "No anchor" : `Anchor: ${t}`}
                </option>
              ))}
            </select>
            {anchorType !== "none" ? (
              <input
                aria-label="Anchor reference"
                value={anchorRef}
                onChange={(event) => setAnchorRef(event.target.value)}
                placeholder="plan path, todo id, entry id…"
                style={{ ...fieldStyle, flex: 1, minWidth: "180px" }}
              />
            ) : null}
          </>
        )}
        <span style={{ flex: 1 }} />
        <Button variant="secondary" disabled={!canPost} onClick={() => mutation.mutate(false)}>
          Save draft
        </Button>
        <Button disabled={!canPost} onClick={() => mutation.mutate(true)}>
          {parentId ? "Reply" : "Send"}
        </Button>
      </div>
      {error ? (
        <p role="alert" style={{ color: "var(--wb-danger)", margin: 0 }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
