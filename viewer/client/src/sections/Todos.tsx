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

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { SegmentedControl } from "../components/SegmentedControl";
import { api } from "../lib/api";
import type { TodoItem, TodosFeed } from "../lib/api-types";
import { boardRootKey, plansRootKey, projectsKey, todosKey, todosRootKey } from "../lib/keys";
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
import { UpdatedAgo } from "./UpdatedAgo";

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
      {/* Stale-work warning: rendered from the served
          `derived` block only (no age math here). */}
      {todo.derived?.stale && todo.derived.age_days != null ? (
        <Badge kind="stale" text={`Stale · ${todo.derived.age_days}d`} />
      ) : null}
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
    queryKey: todosKey(slug),
    queryFn: () => api.getProjectTodos({ slug }),
    enabled: scope === "project",
    refetchInterval: 30000,
  });
  // "All projects" is assembled from ONE CALL PER PROJECT
  // (heavy-feed batching, 2026-11-01), not the /api/todos
  // monolith: that aggregate re-derived every project
  // before its first byte (1.3 MB, ~2 s warm, far longer
  // cold) and parked the whole list behind the slowest
  // project. Portions are the same ["todos", slug] queries
  // the per-project view uses, so they render as they land
  // and one project's failure never parks the others.
  const projectsQuery = useQuery({
    queryKey: projectsKey,
    queryFn: () => api.listProjects({}),
    enabled: scope === "all",
  });
  const allProjects = projectsQuery.data?.payload?.projects ?? [];
  const portionQueries = useQueries({
    queries: allProjects.map((p) => ({
      queryKey: todosKey(p.slug),
      queryFn: () => api.getProjectTodos({ slug: p.slug }),
      enabled: scope === "all",
      refetchInterval: 30000,
    })),
  });
  const allPortions: TodosFeed[] = [];
  const allFailedNames: string[] = [];
  let allPendingCount = 0;
  allProjects.forEach((p, i) => {
    const q = portionQueries[i];
    if (!q) return;
    if (q.isPending) {
      allPendingCount += 1;
      return;
    }
    const payload = q.data?.payload as unknown as TodosFeed | undefined;
    if (q.isError || !payload) allFailedNames.push(p.name);
    else allPortions.push(payload);
  });
  const allTodos: TodoItem[] = allPortions.flatMap((feed) =>
    (feed.todos ?? []).map((todo) => ({
      ...todo,
      project: todo.project ?? feed.slug,
      project_name: todo.project_name ?? feed.name,
    })),
  );
  const allErrors = allPortions.flatMap((feed) => feed.errors ?? []);
  const allPending =
    scope === "all" &&
    (projectsQuery.isPending || (allPortions.length === 0 && allFailedNames.length === 0));
  const allFailed =
    scope === "all" && allProjects.length > 0 && allPortions.length === 0 && !allPending;

  // Batched rendering: long lists mount N rows at a time
  // (the "Show more" buttons below), so a several-hundred
  // row list never pays a several-hundred-row first paint.
  const BATCH = 50;
  const [openVisible, setOpenVisible] = useState(BATCH);
  const [doneVisible, setDoneVisible] = useState(BATCH);
  const [prevScope, setPrevScope] = useState(scope);
  if (prevScope !== scope) {
    setPrevScope(scope);
    setOpenVisible(BATCH);
    setDoneVisible(BATCH);
    setShowDone(false);
  }

  const mutation = useMutation({
    mutationFn: (args: { project: string; id: string; status: string }) =>
      api.todoAction({
        slug: args.project,
        body: { verb: "set-status", id: args.id, status: args.status },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: todosRootKey });
      void queryClient.invalidateQueries({ queryKey: boardRootKey });
      void queryClient.invalidateQueries({ queryKey: plansRootKey });
    },
  });

  const setStatus = (todo: TodoItem, status: string) => {
    const project = todo.project ?? slug;
    if (todo.id) mutation.mutate({ project, id: todo.id, status });
  };

  if (scope === "project" && projectQuery.isPending) {
    return <SkeletonWell label={`todos for ${projectName}`} />;
  }
  if (scope === "all" && allPending) return <SkeletonWell label="todos for all projects" />;
  if (scope === "project" && projectQuery.isError) {
    return <ErrorWell section="Todos" message="the section feed could not be loaded." />;
  }
  if (allFailed) {
    return <ErrorWell section="Todos" message="the section feed could not be loaded." />;
  }
  // The per-project view renders its own feed; the combined
  // view renders the assembled portions under a synthetic
  // feed shell (available when any portion landed).
  const feed: TodosFeed =
    scope === "project"
      ? (projectQuery.data?.payload as unknown as TodosFeed)
      : ({
          slug: "",
          name: "",
          degraded: false,
          available: allPortions.some((f) => f.available),
          todos: allTodos,
          errors: allErrors,
        } as TodosFeed);
  if (scope === "project" && !projectQuery.data?.payload) {
    return (
      <ErrorWell
        section="Todos"
        message={projectQuery.data?.error ?? "the companion server did not answer."}
      />
    );
  }
  // The header's freshness label: the project feed's own
  // stamp, or the oldest portion stamp in combined view.
  const capturedAt =
    scope === "project"
      ? feed.captured_at
      : allPortions.reduce<string | undefined>((oldest, f) => {
          if (!f.captured_at) return oldest;
          if (!oldest) return f.captured_at;
          return Date.parse(f.captured_at) < Date.parse(oldest) ? f.captured_at : oldest;
        }, undefined);
  const todos = scope === "project" ? (feed.todos ?? []) : allTodos;
  const open = todos.filter((todo) => todo.status !== "done");
  const done = todos.filter((todo) => todo.status === "done");
  const dbFallback = scope === "project" && feed.source === "db-fallback";

  return (
    <section>
      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--wb-space-12)" }}>
        <h1 style={sectionTitleStyle}>Todos</h1>
        <UpdatedAgo capturedAt={capturedAt} />
      </div>
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
      {scope === "all" && allPendingCount > 0 ? (
        <p style={{ color: "var(--wb-content-muted)" }}>
          Loading {allPendingCount} project{allPendingCount === 1 ? "" : "s"}…
        </p>
      ) : null}
      {scope === "all" && allFailedNames.length > 0 ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          Could not load {allFailedNames.join(", ")} — the rest of the list is shown.
        </p>
      ) : null}
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
              {open.slice(0, openVisible).map((todo) => (
                <TodoRow
                  key={`${todo.project ?? slug}:${todo.path ?? todo.id}`}
                  todo={todo}
                  showProject={scope === "all"}
                  onSetStatus={setStatus}
                />
              ))}
            </ul>
            {open.length > openVisible ? (
              <Button variant="secondary" onClick={() => setOpenVisible((n) => n + BATCH)}>
                Show more — <span className="num">{open.length - openVisible}</span> more open todos
              </Button>
            ) : null}
            {done.length > 0 ? (
              <>
                <Button variant="ghost" onClick={() => setShowDone(!showDone)}>
                  <span className="num">{done.length}</span> completed {showDone ? "▾" : "▸"}
                </Button>
                {showDone ? (
                  <>
                    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                      {done.slice(0, doneVisible).map((todo) => (
                        <TodoRow
                          key={`${todo.project ?? slug}:${todo.path ?? todo.id}`}
                          todo={todo}
                          showProject={scope === "all"}
                          onSetStatus={setStatus}
                        />
                      ))}
                    </ul>
                    {done.length > doneVisible ? (
                      <Button variant="secondary" onClick={() => setDoneVisible((n) => n + BATCH)}>
                        Show more — <span className="num">{done.length - doneVisible}</span> more
                        completed todos
                      </Button>
                    ) : null}
                  </>
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
