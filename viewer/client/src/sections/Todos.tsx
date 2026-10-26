// Todos — derived from bundle todo FILES across bundles
// (live-work spec §3.5; server read switch §3.7). Per-
// project and combined views; every row labels its bundle
// (and its project, in the combined view). Status changes
// go through the server's one todo mutation — the lib
// writer under `wb todo set`; creation stays with the
// generator verbs (`wb bundle new` / `wb todo new`, §3.4).
// Registry-DB todos appear ONLY via the §3.7 fallback
// (source: "db-fallback") and are read-only here until
// imported. Invalid front-matter todos render as feed
// errors on their row — never silent skips.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../components/Button";
import { SegmentedControl } from "../components/SegmentedControl";
import { api, type TodoItem, type TodosFeed } from "../lib/api";
import { todoStatusLabel } from "../lib/labels";
import { useIsPhone } from "../lib/responsive";
import { sectionHref } from "../lib/routing";
import { anchor } from "./plans/anchors";
import {
  DegradedBanner,
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";

const STATUSES = ["todo", "doing", "blocked", "done"] as const;

const selectStyle: React.CSSProperties = {
  background: "var(--wb-surface-2)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-button-radius)",
  color: "var(--wb-content-primary)",
  minHeight: "38px",
  padding: "0 var(--wb-space-8)",
  fontSize: "var(--wb-font-size-sm)",
};

function TodoRow({
  todo,
  showProject,
  onSetStatus,
}: {
  todo: TodoItem;
  showProject: boolean;
  onSetStatus: (todo: TodoItem, status: string) => void;
}) {
  const isPhone = useIsPhone();
  const invalid = todo.valid === false;
  const fromDb = todo.source === "db";
  const editable = !invalid && !fromDb && todo.id != null;
  return (
    <li
      style={{
        ...listRowStyle,
        alignItems: "flex-start",
        // Phone: checkbox + title + meta chips + status
        // select exceed the column on one line (selects
        // measured out to 634px at 390) — wrap so the
        // controls drop under the title.
        flexWrap: isPhone ? "wrap" : undefined,
      }}
    >
      <span
        style={{
          display: "inline-flex",
          minWidth: "38px",
          minHeight: "38px",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <input
          type="checkbox"
          aria-label={`Mark ${todo.title ?? "todo"} done`}
          checked={todo.status === "done"}
          disabled={!editable}
          onChange={(e) => onSetStatus(todo, e.target.checked ? "done" : "todo")}
          style={{ width: "18px", height: "18px" }}
        />
      </span>
      <span style={{ flex: 1, minWidth: isPhone ? 0 : undefined }}>
        <span>{todo.title ?? todo.path ?? "Untitled todo"}</span>
        {todo.plan ? (
          <>
            {" "}
            <a
              className="mono"
              href={todo.project ? sectionHref(todo.project, "plans", todo.plan) : undefined}
              style={{ color: "var(--wb-accent)", fontSize: "var(--wb-font-size-xs)" }}
            >
              {todo.plan}
              {todo.plan_step ? ` · step ${todo.plan_step}` : ""}
            </a>
          </>
        ) : null}
        {todo.link_kind && todo.link_ref ? (
          <span style={metaStyle}>
            {" "}
            {todo.link_kind}: <span className="mono">{todo.link_ref}</span>
          </span>
        ) : null}
        {invalid ? (
          <span style={{ display: "block", color: "var(--wb-danger)" }}>
            Invalid front-matter: {(todo.errors ?? []).join("; ")}
          </span>
        ) : null}
        {todo.body ? (
          <span
            style={{
              display: "block",
              color: "var(--wb-content-muted)",
              whiteSpace: "pre-wrap",
            }}
          >
            {todo.body}
          </span>
        ) : null}
      </span>
      {showProject && todo.project_name ? <span style={metaStyle}>{todo.project_name}</span> : null}
      {todo.bundle ? (
        <span className="mono" style={metaStyle}>
          {todo.bundle}
        </span>
      ) : null}
      {todo.feature ? <span style={metaStyle}>{todo.feature}</span> : null}
      {todo.worktree ? (
        <span className="mono" style={metaStyle}>
          {todo.worktree}
        </span>
      ) : null}
      {fromDb ? <span style={metaStyle}>registry DB</span> : null}
      {editable ? (
        <select
          aria-label={`Status of ${todo.title ?? "todo"}`}
          style={selectStyle}
          value={todo.status ?? "todo"}
          onChange={(e) => onSetStatus(todo, e.target.value)}
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {todoStatusLabel(status)}
            </option>
          ))}
        </select>
      ) : (
        <span style={metaStyle}>{todoStatusLabel(todo.status)}</span>
      )}
    </li>
  );
}

export function TodosSection({ slug, projectName }: { slug: string; projectName: string }) {
  const [scope, setScope] = useState<"project" | "all">("project");
  const [showDone, setShowDone] = useState(false);
  const queryClient = useQueryClient();

  const projectQuery = useQuery({
    queryKey: ["todos", slug],
    queryFn: () => api.getProjectTodos({ slug }),
    enabled: scope === "project",
  });
  const allQuery = useQuery({
    queryKey: ["todos", "all"],
    queryFn: () => api.getAllTodos({}),
    enabled: scope === "all",
  });
  const query = scope === "project" ? projectQuery : allQuery;

  const mutation = useMutation({
    mutationFn: (args: { project: string; id: string; status: string }) =>
      api.todoAction({
        slug: args.project,
        body: { verb: "set-status", id: args.id, status: args.status },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["todos"] });
      void queryClient.invalidateQueries({ queryKey: ["board"] });
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });

  const setStatus = (todo: TodoItem, status: string) => {
    const project = todo.project ?? slug;
    if (todo.id) mutation.mutate({ project, id: todo.id, status });
  };

  if (query.isPending) return <SkeletonWell label={`todos for ${projectName}`} />;
  if (query.isError) {
    return <ErrorWell section="Todos" message="the section feed could not be loaded." />;
  }
  const { payload, error } = query.data;
  if (!payload) {
    return <ErrorWell section="Todos" message={error ?? "the companion server did not answer."} />;
  }
  const feed = payload as unknown as TodosFeed;
  const todos = feed.todos ?? [];
  const open = todos.filter((todo) => todo.status !== "done");
  const done = todos.filter((todo) => todo.status === "done");
  const dbFallback = scope === "project" && feed.source === "db-fallback";

  return (
    <section>
      <h1 style={sectionTitleStyle}>Todos</h1>
      {scope === "project" ? <DegradedBanner feed={feed} /> : null}
      <SegmentedControl
        ariaLabel="Todo scope"
        options={[
          { value: "project", label: "This project" },
          { value: "all", label: "All projects" },
        ]}
        value={scope}
        onChange={setScope}
      />
      {dbFallback ? (
        <p style={{ color: "var(--wb-content-secondary)" }}>
          These todos still live in {projectName}&rsquo;s registry DB — no bundle todos exist yet,
          so the DB rows show until they are imported with{" "}
          <span className="mono">wb todo import-db</span>. They are read-only here.
        </p>
      ) : null}
      {feed.errors && feed.errors.length > 0 ? (
        <p style={{ color: "var(--wb-danger)" }}>
          <span className="num">{feed.errors.length}</span> todo file problem(s) — the affected rows
          below carry the exact error.
        </p>
      ) : null}
      {mutation.isError ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          The status change was refused — reload the section to see the current state.
        </p>
      ) : null}
      <div data-anchor={anchor.todoTable}>
        {todos.length === 0 ? (
          <EmptyWell>
            {scope === "all"
              ? "No todos in any project — the combined list is empty."
              : feed.available
                ? `No todos in ${projectName} — the list is empty.`
                : `No todos for ${projectName} — this project has no plans directory or registry.`}
          </EmptyWell>
        ) : (
          <>
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {open.map((todo) => (
                <TodoRow
                  key={`${todo.project ?? slug}:${todo.path ?? todo.id}`}
                  todo={todo}
                  showProject={scope === "all"}
                  onSetStatus={setStatus}
                />
              ))}
            </ul>
            {done.length > 0 ? (
              <>
                <Button variant="ghost" onClick={() => setShowDone(!showDone)}>
                  <span className="num">{done.length}</span> completed {showDone ? "▾" : "▸"}
                </Button>
                {showDone ? (
                  <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                    {done.map((todo) => (
                      <TodoRow
                        key={`${todo.project ?? slug}:${todo.path ?? todo.id}`}
                        todo={todo}
                        showProject={scope === "all"}
                        onSetStatus={setStatus}
                      />
                    ))}
                  </ul>
                ) : null}
              </>
            ) : null}
          </>
        )}
      </div>
      <p style={{ color: "var(--wb-content-muted)" }}>
        New todos are created with the generator: <span className="mono">wb todo new</span> in a
        bundle (live-work spec §3.4).
      </p>
    </section>
  );
}
