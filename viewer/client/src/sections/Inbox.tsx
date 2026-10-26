// Inbox (#/inbox, repo-home spec §§5, 7 + D7): the
// cross-project message inbox — per-project inboxes are
// this same view filtered. Threads ride the §5.2
// lifecycle (a thread's state is its root's); replies are
// messages with parent_id set. Pickup is an AGENT act
// (D8) — this view never acknowledges anything; it shows
// sent-but-unacknowledged threads with their derived
// "awaiting pickup" badge (§5.3) once they age past the
// badge threshold.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { SegmentedControl } from "../components/SegmentedControl";
import { api, type MessageItem, type MessagesPayload, type ProjectSummary } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { messageStateLabel } from "../lib/labels";
import { MessageComposer } from "./inbox/MessageComposer";
import { EmptyWell, ErrorWell, metaStyle, SkeletonWell, sectionTitleStyle } from "./shared";

const STATE_FILTERS = [
  { value: "", label: "All" },
  { value: "draft", label: "Drafts" },
  { value: "sent", label: "Sent" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "done", label: "Done" },
  { value: "archived", label: "Archived" },
] as const;

function AwaitingMark() {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: "24px",
        padding: "0 var(--wb-space-8)",
        border: "1px solid var(--wb-border-strong)",
        borderRadius: "var(--wb-radius-pill)",
        fontSize: "var(--wb-font-size-xs)",
        color: "var(--wb-content-secondary)",
        whiteSpace: "nowrap",
      }}
    >
      ◷ Awaiting pickup
    </span>
  );
}

function MessageMeta({ message }: { message: MessageItem }) {
  return (
    <span
      style={{
        display: "inline-flex",
        gap: "var(--wb-space-8)",
        alignItems: "center",
        flexWrap: "wrap",
      }}
    >
      <span style={{ fontWeight: 600 }}>{message.author === "owner" ? "Owner" : "Muse"}</span>
      <span style={metaStyle}>{messageStateLabel(message.state)}</span>
      <span style={metaStyle}>{message.project_slug ?? "workspace-wide"}</span>
      {message.anchor_type !== "none" ? (
        <span style={metaStyle}>
          {message.anchor_type} · <span className="mono">{message.anchor_ref ?? ""}</span>
        </span>
      ) : null}
      <span style={metaStyle}>{formatDateTime(message.created_at)}</span>
      {message.awaiting_pickup ? <AwaitingMark /> : null}
    </span>
  );
}

function MessageActions({ message, onSelect }: { message: MessageItem; onSelect: () => void }) {
  const queryClient = useQueryClient();
  const act = useMutation({
    mutationFn: (verb: "send" | "done" | "archive") =>
      verb === "send"
        ? api.sendMessage({ id: message.id })
        : verb === "done"
          ? api.doneMessage({ id: message.id })
          : api.archiveMessage({ id: message.id }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["messages"] });
    },
  });
  const busy = act.isPending;
  return (
    <span style={{ display: "inline-flex", gap: "var(--wb-space-8)" }}>
      <Button variant="ghost" onClick={onSelect}>
        Thread
      </Button>
      {message.state === "draft" ? (
        <Button variant="secondary" disabled={busy} onClick={() => act.mutate("send")}>
          Send
        </Button>
      ) : null}
      {message.state === "acknowledged" ? (
        <Button variant="secondary" disabled={busy} onClick={() => act.mutate("done")}>
          Mark done
        </Button>
      ) : null}
      {message.state === "sent" || message.state === "acknowledged" || message.state === "done" ? (
        <Button variant="ghost" disabled={busy} onClick={() => act.mutate("archive")}>
          Archive
        </Button>
      ) : null}
    </span>
  );
}

function ThreadView({
  root,
  replies,
  projects,
}: {
  root: MessageItem;
  replies: MessageItem[];
  projects: ProjectSummary[];
}) {
  const thread = [root, ...replies];
  return (
    <Card anchor="inbox/thread" title={`Thread · ${messageStateLabel(root.state)}`}>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {thread.map((message, i) => (
          <li
            key={message.id}
            style={{
              borderBottom: i < thread.length - 1 ? "1px solid var(--wb-border-default)" : "none",
              padding: "var(--wb-space-12) 0",
              marginLeft: i === 0 ? 0 : "var(--wb-space-24)",
            }}
          >
            <MessageMeta message={message} />
            <p style={{ margin: "var(--wb-space-8) 0 0", whiteSpace: "pre-wrap" }}>
              {message.body || <span style={metaStyle}>(empty)</span>}
            </p>
            {message.showcase?.main != null ? (
              <p style={metaStyle}>
                Showcase: <span className="mono">{JSON.stringify(message.showcase.main)}</span>
                {" — "}
                opens in the project's sections.
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      <div style={{ marginTop: "var(--wb-space-12)" }}>
        <MessageComposer
          projects={projects.map((p) => ({ slug: p.slug, name: p.name }))}
          fixedProject={root.project_slug}
          parentId={root.id}
        />
      </div>
    </Card>
  );
}

export function InboxSection() {
  const [projectFilter, setProjectFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects({}),
  });
  const projects = useMemo<ProjectSummary[]>(
    () => projectsQuery.data?.payload?.projects ?? [],
    [projectsQuery.data],
  );
  const messagesQuery = useQuery({
    queryKey: ["messages", projectFilter],
    queryFn: () => api.getMessages(projectFilter ? { project: projectFilter } : {}),
    refetchInterval: 30000,
  });

  if (messagesQuery.isPending) return <SkeletonWell label="the inbox" />;
  if (messagesQuery.isError || !messagesQuery.data.payload) {
    return (
      <ErrorWell
        section="Inbox"
        message={messagesQuery.data?.error ?? "the companion server did not answer."}
      />
    );
  }
  const payload = messagesQuery.data.payload as unknown as MessagesPayload;
  const all = payload.messages;
  const byId = new Map(all.map((m) => [m.id, m]));
  const rootOf = (m: MessageItem): MessageItem => {
    let current = m;
    const seen = new Set<number>();
    while (current.parent_id != null && byId.has(current.parent_id) && !seen.has(current.id)) {
      seen.add(current.id);
      current = byId.get(current.parent_id) as MessageItem;
    }
    return current;
  };
  const roots = all.filter((m) => m.parent_id == null || !byId.has(m.parent_id));
  const repliesOf = (rootId: number) =>
    all.filter((m) => m.id !== rootId && rootOf(m).id === rootId);
  const visibleRoots = roots.filter((m) => stateFilter === "" || m.state === stateFilter);
  const selectedRoot = selectedId != null ? (roots.find((r) => r.id === selectedId) ?? null) : null;

  return (
    <section data-anchor="inbox/list">
      <h1 style={sectionTitleStyle}>Inbox</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--wb-space-16)" }}>
        <Card anchor="inbox/compose" title="New message">
          <MessageComposer projects={projects.map((p) => ({ slug: p.slug, name: p.name }))} />
        </Card>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-16)",
            flexWrap: "wrap",
          }}
        >
          <SegmentedControl
            ariaLabel="Message state filter"
            options={[...STATE_FILTERS]}
            value={stateFilter}
            onChange={setStateFilter}
          />
          <select
            aria-label="Project filter"
            value={projectFilter}
            onChange={(event) => setProjectFilter(event.target.value)}
            style={{
              background: "var(--wb-surface-sunken)",
              color: "var(--wb-content-primary)",
              border: "1px solid var(--wb-border-default)",
              borderRadius: "var(--wb-radius-md)",
              padding: "var(--wb-space-8)",
            }}
          >
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name}
              </option>
            ))}
          </select>
          <span style={metaStyle}>
            <span className="num">{visibleRoots.length}</span> threads
          </span>
        </div>
        {selectedRoot ? (
          <ThreadView
            root={selectedRoot}
            replies={repliesOf(selectedRoot.id)}
            projects={projects}
          />
        ) : null}
        {visibleRoots.length === 0 ? (
          <EmptyWell>
            {all.length === 0
              ? "No messages yet — compose one above, or an agent session will post here."
              : "No threads in this state."}
          </EmptyWell>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {[...visibleRoots].reverse().map((message) => {
              const replyCount = repliesOf(message.id).length;
              return (
                <li
                  key={message.id}
                  style={{
                    borderBottom: "1px solid var(--wb-border-default)",
                    padding: "var(--wb-space-12) 0",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: "var(--wb-space-16)",
                      alignItems: "flex-start",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <MessageMeta message={message} />
                      <p
                        style={{
                          margin: "var(--wb-space-4) 0 0",
                          color: "var(--wb-content-primary)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          maxWidth: "720px",
                        }}
                      >
                        {message.body.split("\n")[0] || "(empty)"}
                      </p>
                      {replyCount > 0 ? (
                        <span style={metaStyle}>
                          <span className="num">{replyCount}</span>{" "}
                          {replyCount === 1 ? "reply" : "replies"}
                        </span>
                      ) : null}
                    </div>
                    <MessageActions
                      message={message}
                      onSelect={() => setSelectedId(selectedId === message.id ? null : message.id)}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
