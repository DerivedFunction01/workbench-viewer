// Annotations — the shared annotation UI kit (repo-home
// spec §12; annotation plan steps 5–6). An annotation is
// a MESSAGE plus a selection payload; this module owns
// the presentation + draft lifecycle the two annotation
// surfaces share: the composer (a draft is created on
// the FIRST KEYSTROKE and autosaved through the draft
// body endpoint; Send walks it to sent; Cancel dismisses
// the composer and the typed draft stays a draft under
// the store's normal TTL — an untouched composer creates
// nothing), the margin thread card, the per-anchor list,
// and the <mark> highlight machinery (client re-location
// over the rendered text; orphans/ambiguous get NO mark).
// Sections own data fetching placement and routing; all
// mutations go through the bridge actions (one path).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnnotationBadge, annotationMarkStyle } from "../components/AnnotationBadge";
import { Button } from "../components/Button";
import {
  api,
  type MessageItem,
  type MessagesPayload,
  type SelectionAnchor,
  type TextSelection,
} from "../lib/api";
import { formatRelative } from "../lib/format";
import { locateInText, type RelocationStatus } from "./plans/relocation";

export interface AnnotationThread {
  root: MessageItem;
  replies: MessageItem[];
}

/** Group a project's messages into the annotation
 * threads anchored at `anchorRef`: roots are non-archived
 * messages carrying a selection payload; replies resolve
 * to their root by walking parent_id (replies never
 * carry a selection — the root holds the anchor). */
export function groupThreads(messages: MessageItem[], anchorRef: string): AnnotationThread[] {
  const byId = new Map(messages.map((m) => [m.id, m]));
  const isRoot = (m: MessageItem) =>
    m.parent_id == null &&
    m.selection != null &&
    m.anchor_ref === anchorRef &&
    m.state !== "archived";
  const roots = messages.filter(isRoot);
  const rootIds = new Set(roots.map((r) => r.id));
  const repliesByRoot = new Map<number, MessageItem[]>();
  for (const m of messages) {
    if (m.parent_id == null) continue;
    let cur: MessageItem | undefined = m;
    const seen = new Set<number>();
    while (cur?.parent_id != null && !seen.has(cur.id)) {
      seen.add(cur.id);
      cur = byId.get(cur.parent_id);
    }
    if (cur && rootIds.has(cur.id)) {
      const list = repliesByRoot.get(cur.id) ?? [];
      list.push(m);
      repliesByRoot.set(cur.id, list);
    }
  }
  return roots.map((root) => ({
    root,
    replies: (repliesByRoot.get(root.id) ?? []).slice().sort((a, b) => a.id - b.id),
  }));
}

/** The annotation threads for one anchor (a plan path or
 * an entry id), from the project's message list. The
 * count IS the thread count: roots in draft / sent /
 * acknowledged / done (archived never counts). */
export function useAnnotationThreads(slug: string, anchorRef: string) {
  const query = useQuery({
    queryKey: ["messages", slug],
    queryFn: () => api.getMessages({ project: slug }),
  });
  const messages = useMemo(() => {
    const payload = query.data?.payload as unknown as MessagesPayload | undefined;
    return payload?.messages ?? [];
  }, [query.data]);
  const threads = useMemo(() => groupThreads(messages, anchorRef), [messages, anchorRef]);
  return { threads, count: threads.length, messagesPending: query.isPending };
}

export function authorLabelOf(author: string): string {
  return author === "owner" ? "the owner" : author === "Muse" ? "Muse" : author;
}

/** The mono anchor label for a thread root: `text ·
 * <component>` for text anchors, the component label for
 * component anchors (mockup row form). */
export function anchorLabelOf(root: MessageItem): string {
  const sel = root.selection;
  if (!sel) return root.anchor_type;
  if (sel.kind === "text") return `text · ${sel.component_label ?? sel.component_id}`;
  return sel.component_label ?? sel.component_id;
}

/** The ::selection tint for an annotation surface: the
 * live selection wears the active palette's accent
 * derivation (the --wb-highlight-selection-* tokens).
 * Sections mark their annotation root with
 * data-annotation-scope. */
export function SelectionTintStyle() {
  return (
    <style>
      {`[data-annotation-scope] ::selection { background: var(--wb-highlight-selection-fill); box-shadow: inset 0 -2px 0 var(--wb-highlight-selection-bar); }`}
    </style>
  );
}

// ----------------------------------------------------------------
// Marks: saved-annotation highlights over rendered text
// ----------------------------------------------------------------

/** Remove every annotation mark under `container`,
 * restoring the underlying text nodes. */
export function clearAnnotationMarks(container: HTMLElement) {
  for (const mark of Array.from(container.querySelectorAll("mark[data-wb-annotation]"))) {
    mark.replaceWith(document.createTextNode(mark.textContent ?? ""));
  }
  container.normalize();
}

function wrapTextRange(root: HTMLElement, start: number, end: number) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const segments: { node: Text; from: number; to: number }[] = [];
  let offset = 0;
  let node = walker.nextNode() as Text | null;
  while (node) {
    const len = node.data.length;
    const from = Math.max(0, start - offset);
    const to = Math.min(len, end - offset);
    if (from < to) segments.push({ node, from, to });
    offset += len;
    node = walker.nextNode() as Text | null;
  }
  for (const { node, from, to } of segments) {
    let target = node;
    if (from > 0) target = target.splitText(from);
    if (to - from < target.data.length) target.splitText(to - from);
    const mark = document.createElement("mark");
    mark.dataset.wbAnnotation = "";
    Object.assign(mark.style, annotationMarkStyle);
    target.parentNode?.replaceChild(mark, target);
    mark.appendChild(target);
  }
}

/** Re-locate a text selection inside an element's rendered
 * text and wrap the located span in the saved-annotation
 * mark. Returns the derived status; orphan/ambiguous
 * selections get NO mark (anchor-moved is shown in the
 * list, never guessed in the text). */
export function highlightSelectionInElement(
  el: HTMLElement,
  selection: TextSelection,
): RelocationStatus {
  const result = locateInText(el.textContent ?? "", selection);
  if (result.status !== "located") return result.status;
  wrapTextRange(el, result.start, result.end);
  return "located";
}

// ----------------------------------------------------------------
// Composer
// ----------------------------------------------------------------

function errorOf(e: unknown): string {
  return e instanceof Error ? e.message : "something went wrong.";
}

const cardStyle: React.CSSProperties = {
  background: "var(--wb-surface-1)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "10px",
  padding: "var(--wb-space-12)",
};

/** The house field look (MessageComposer's fieldStyle). */
const fieldStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  color: "var(--wb-content-primary)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-8)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  width: "100%",
  resize: "vertical",
};

export function AnnotationComposer({
  slug,
  anchorType,
  anchorRef,
  selection,
  quote,
  onClose,
  onSent,
}: {
  slug: string;
  anchorType: "text" | "component";
  anchorRef: string;
  selection: SelectionAnchor;
  /** Text annotations: the anchored quote, shown as the
   * composer's `Anchor · "…"` first line. */
  quote?: string;
  onClose: () => void;
  onSent?: () => void;
}) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const draftId = useRef<number | null>(null);
  const creating = useRef<Promise<number> | null>(null);
  const latestBody = useRef("");
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["messages"] });

  async function ensureDraft(): Promise<number> {
    if (draftId.current != null) return draftId.current;
    if (!creating.current) {
      creating.current = api
        .createMessage({
          body: {
            author: "owner",
            body: latestBody.current,
            project_slug: slug,
            anchor_type: anchorType,
            anchor_ref: anchorRef,
            selection,
          },
        })
        .then((res) => {
          const created = res.payload as unknown as MessageItem | null | undefined;
          if (!created) throw new Error(res.error ?? "the draft could not be created.");
          draftId.current = created.id;
          invalidate();
          return created.id;
        });
    }
    return creating.current;
  }

  function onBodyChange(value: string) {
    setBody(value);
    latestBody.current = value;
    if (draftId.current == null && !creating.current) {
      // First keystroke creates the draft; an untouched
      // composer creates nothing.
      if (value.length > 0) ensureDraft().catch((e) => setError(errorOf(e)));
      return;
    }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      ensureDraft()
        .then((id) => api.updateMessageBody({ id, body: latestBody.current }))
        .then((res) => {
          if (res.error) setError(res.error);
        })
        .catch((e) => setError(errorOf(e)));
    }, 600);
  }

  async function onSend() {
    if (!body.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const id = await ensureDraft();
      const upd = await api.updateMessageBody({ id, body: latestBody.current });
      if (upd.error) throw new Error(upd.error);
      const sent = await api.sendMessage({ id });
      if (sent.error) throw new Error(sent.error);
      invalidate();
      (onSent ?? onClose)();
    } catch (e) {
      setError(errorOf(e));
      setBusy(false);
    }
  }

  return (
    <div
      data-annotation-ui="true"
      style={{ position: "relative", marginTop: "var(--wb-space-16)" }}
    >
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          top: "-11px",
          left: "18px",
          width: "7px",
          height: "7px",
          borderRadius: "50%",
          background: "var(--wb-accent)",
        }}
      />
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          top: "-4px",
          left: "21px",
          width: "1.5px",
          height: "6px",
          background: "var(--wb-accent)",
        }}
      />
      <div style={{ ...cardStyle, boxShadow: "var(--wb-shadow-overlay)" }}>
        {quote !== undefined ? (
          <p
            className="mono"
            style={{
              margin: "0 0 var(--wb-space-8)",
              fontSize: "var(--wb-font-size-xs)",
              color: "var(--wb-accent)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            Anchor · “{quote}”
          </p>
        ) : null}
        <textarea
          aria-label="Annotation comment"
          placeholder="Add a comment…"
          rows={2}
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          style={fieldStyle}
        />
        {error ? (
          <p style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) 0 0" }}>{error}</p>
        ) : null}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-8)",
            marginTop: "var(--wb-space-8)",
          }}
        >
          {selection.kind === "component" ? (
            <span
              className="mono"
              style={{ fontSize: "var(--wb-font-size-xs)", color: "var(--wb-content-muted)" }}
            >
              anchor · {selection.component_label ?? selection.component_id}
            </span>
          ) : null}
          <span style={{ flex: 1 }} />
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!body.trim() || busy} onClick={onSend}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------
// Thread card + list
// ----------------------------------------------------------------

function AuthorAvatar({ author, small }: { author: string; small?: boolean }) {
  const size = small ? 20 : 26;
  const initial = (authorLabelOf(author).charAt(0) || "?").toUpperCase();
  const base: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: "50%",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "11px",
    fontWeight: 600,
    flexShrink: 0,
  };
  return author === "Muse" ? (
    <span
      aria-hidden="true"
      style={{ ...base, border: "1.5px solid var(--wb-accent)", color: "var(--wb-accent)" }}
    >
      {initial}
    </span>
  ) : (
    <span
      aria-hidden="true"
      style={{ ...base, background: "var(--wb-accent)", color: "var(--wb-on-accent)" }}
    >
      {initial}
    </span>
  );
}

export function AnnotationThreadCard({
  slug,
  thread,
  moved,
}: {
  slug: string;
  thread: AnnotationThread;
  /** Anchor-moved rendering: the stored quote is shown
   * (never dropped), labelled as moved. */
  moved?: boolean;
}) {
  const { root, replies } = thread;
  const queryClient = useQueryClient();
  const [replyBody, setReplyBody] = useState("");
  const [replyError, setReplyError] = useState<string | null>(null);
  const replyMut = useMutation({
    mutationFn: () =>
      api.createMessage({
        body: {
          author: "owner",
          body: replyBody,
          project_slug: slug,
          parent_id: root.id,
          send: true,
        },
      }),
    onSuccess: (res) => {
      if (res.error) {
        setReplyError(res.error);
        return;
      }
      setReplyBody("");
      setReplyError(null);
      queryClient.invalidateQueries({ queryKey: ["messages"] });
    },
  });
  const sel = root.selection;
  return (
    <div data-annotation-ui="true" style={cardStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-8)",
          marginBottom: "var(--wb-space-8)",
        }}
      >
        <AuthorAvatar author={root.author} />
        <span style={{ fontWeight: 600 }}>{authorLabelOf(root.author)}</span>
        <span style={{ color: "var(--wb-content-muted)", fontSize: "var(--wb-font-size-xs)" }}>
          {formatRelative(root.created_at)}
        </span>
      </div>
      {moved && sel?.kind === "text" ? (
        <div style={{ marginBottom: "var(--wb-space-8)" }}>
          <span
            style={{
              fontSize: "var(--wb-font-size-xs)",
              fontWeight: 600,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              color: "var(--wb-content-muted)",
            }}
          >
            Anchor moved
          </span>
          <p
            className="mono"
            style={{
              margin: "var(--wb-space-4) 0 0",
              fontSize: "var(--wb-font-size-xs)",
              color: "var(--wb-content-secondary)",
              whiteSpace: "pre-wrap",
            }}
          >
            “{sel.quote}”
          </p>
        </div>
      ) : null}
      <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{root.body}</p>
      {replies.map((reply) => (
        <div
          key={reply.id}
          style={{
            borderTop: "1px solid var(--wb-border-default)",
            marginTop: "var(--wb-space-8)",
            paddingTop: "var(--wb-space-8)",
            paddingLeft: "var(--wb-space-12)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--wb-space-8)",
              marginBottom: "var(--wb-space-4)",
            }}
          >
            <AuthorAvatar author={reply.author} small />
            <span style={{ fontWeight: 600, fontSize: "var(--wb-font-size-sm)" }}>
              {authorLabelOf(reply.author)}
            </span>
            <span style={{ color: "var(--wb-content-muted)", fontSize: "var(--wb-font-size-xs)" }}>
              {formatRelative(reply.created_at)}
            </span>
          </div>
          <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{reply.body}</p>
        </div>
      ))}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--wb-space-8)",
          marginTop: "var(--wb-space-8)",
        }}
      >
        <AnnotationBadge state={root.state} />
        {sel?.kind === "component" ? (
          <span
            className="mono"
            style={{ fontSize: "var(--wb-font-size-xs)", color: "var(--wb-content-muted)" }}
          >
            anchor · {sel.component_label ?? sel.component_id}
          </span>
        ) : null}
      </div>
      <div style={{ marginTop: "var(--wb-space-8)" }}>
        <textarea
          aria-label="Reply to annotation"
          placeholder="Reply…"
          rows={1}
          value={replyBody}
          onChange={(e) => setReplyBody(e.target.value)}
          style={fieldStyle}
        />
        {replyError ? (
          <p style={{ color: "var(--wb-danger)", margin: "var(--wb-space-8) 0 0" }}>{replyError}</p>
        ) : null}
        <div
          style={{ display: "flex", justifyContent: "flex-end", marginTop: "var(--wb-space-8)" }}
        >
          <Button
            variant="secondary"
            disabled={!replyBody.trim() || replyMut.isPending}
            onClick={() => replyMut.mutate()}
          >
            Reply
          </Button>
        </div>
      </div>
    </div>
  );
}

/** The per-anchor list: located threads as rows (anchor
 * label · quote · first line · badge); anchor-moved
 * threads last, as full cards under "Anchor moved" with
 * their stored quote — shown, never dropped. */
export function AnnotationList({
  slug,
  threads,
  statusOf,
}: {
  slug: string;
  threads: AnnotationThread[];
  statusOf: (root: MessageItem) => "located" | "moved";
}) {
  const located = threads.filter((t) => statusOf(t.root) === "located");
  const movedThreads = threads.filter((t) => statusOf(t.root) === "moved");
  return (
    <div data-annotation-ui="true">
      {located.length > 0 ? (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {located.map((t) => {
            const sel = t.root.selection;
            const firstLine = t.root.body.split("\n")[0] ?? "";
            return (
              <li
                key={t.root.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--wb-space-12)",
                  padding: "var(--wb-space-8) 0",
                  borderBottom: "1px solid var(--wb-border-default)",
                }}
              >
                <span
                  className="mono"
                  style={{
                    fontSize: "var(--wb-font-size-xs)",
                    color: "var(--wb-content-secondary)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {anchorLabelOf(t.root)}
                </span>
                {sel?.kind === "text" ? (
                  <span
                    style={{
                      color: "var(--wb-content-muted)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      maxWidth: "38%",
                    }}
                  >
                    “{sel.quote}”
                  </span>
                ) : null}
                <span
                  style={{
                    flex: 1,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {firstLine}
                </span>
                <AnnotationBadge state={t.root.state} />
              </li>
            );
          })}
        </ul>
      ) : null}
      {movedThreads.length > 0 ? (
        <div style={{ marginTop: "var(--wb-space-16)" }}>
          <h4 style={{ margin: "0 0 var(--wb-space-8)", color: "var(--wb-content-secondary)" }}>
            Anchor moved
          </h4>
          <div style={{ display: "grid", gap: "var(--wb-space-8)" }}>
            {movedThreads.map((t) => (
              <AnnotationThreadCard key={t.root.id} slug={slug} thread={t} moved />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
