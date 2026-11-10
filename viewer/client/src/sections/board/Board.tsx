// Board — a view over exactly three sources (SPEC §8.4,
// live-work spec §3.5), fetched as one portion per project
// (heavy-feed batching: card projections, done lanes
// paginated) and assembled client-side: the registry review queue (FIRST
// lane, read-only), bundle todo files (lanes by todo
// status: todo / doing / blocked / done), and plan cards
// derived from plan headers (read-only). ONLY todo cards
// drag — a drag is exactly one server todo mutation (the
// lib writer under `wb todo set`) and nothing else. Plan
// and review cards carry no handle; clicking one opens its
// source. Deleting this section would lose no data: every
// card's source record lives in its own store.

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/Button";
import { Lane } from "../../components/Lane";
import { api } from "../../lib/api";
import type {
  BoardPlan,
  BoardProjectPayload,
  ProjectsPayload,
  ReviewItem,
  TodoItem,
} from "../../lib/api-types";
import { boardKey, boardRootKey, plansRootKey, projectsKey, todosRootKey } from "../../lib/keys";
import { kindLabel, todoStatusLabel } from "../../lib/labels";
import { useIsPhone } from "../../lib/responsive";
import { sectionHref } from "../../lib/routing";
import { anchor } from "../plans/anchors";
import { EmptyWell, ErrorWell, SkeletonWell, sectionTitleStyle } from "../shared";
import { UpdatedAgo } from "../UpdatedAgo";

const TODO_LANES = ["todo", "doing", "blocked", "done"] as const;
type TodoLane = (typeof TODO_LANES)[number];

const cardStyle: React.CSSProperties = {
  background: "var(--wb-surface-2)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-md)",
  padding: "var(--wb-space-12)",
  width: "264px",
  maxWidth: "100%",
  boxSizing: "border-box",
  color: "var(--wb-content-primary)",
  textAlign: "left",
};

const tagStyle: React.CSSProperties = {
  color: "var(--wb-content-muted)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
};

const titleStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  display: "-webkit-box",
  WebkitLineClamp: 2,
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
};

function CardShell({
  glyph,
  projectName,
  title,
  footer,
  draggable,
  onDragStart,
  onOpen,
  styleOverride,
}: {
  glyph: string;
  projectName: string;
  title: string;
  footer: React.ReactNode;
  draggable: boolean;
  onDragStart?: (e: React.DragEvent) => void;
  onOpen?: () => void;
  /** Phone presentation: the card goes full lane width
   * (the mockup's stacked-lane card) instead of 264px. */
  styleOverride?: React.CSSProperties;
}) {
  const inner = (
    <>
      <div style={{ display: "flex", gap: "var(--wb-space-8)", alignItems: "baseline" }}>
        <span aria-hidden="true">{glyph}</span>
        <span style={{ flex: 1, ...tagStyle }}>{projectName}</span>
        {draggable ? (
          <span aria-hidden="true" style={tagStyle}>
            ⠿
          </span>
        ) : null}
      </div>
      <div style={titleStyle}>{title}</div>
      <div style={{ ...tagStyle, marginTop: "var(--wb-space-8)" }}>{footer}</div>
    </>
  );
  if (onOpen) {
    // derived cards open their source: a real <button>, so
    // the open gesture is keyboard-native — and never a
    // drag handle (draggable stays false for these).
    return (
      <button
        type="button"
        style={{ ...cardStyle, ...styleOverride, cursor: "pointer", font: "inherit" }}
        draggable={false}
        onClick={onOpen}
      >
        {inner}
      </button>
    );
  }
  return (
    <article
      style={{ ...cardStyle, ...styleOverride }}
      draggable={draggable}
      onDragStart={onDragStart}
    >
      {inner}
    </article>
  );
}

export function BoardSection({
  slug,
  projectName,
}: {
  slug: string | null;
  projectName: string | null;
}) {
  const [doneExpanded, setDoneExpanded] = useState(false);
  const [dragOver, setDragOver] = useState<TodoLane | null>(null);
  const isPhone = useIsPhone();
  const queryClient = useQueryClient();

  // Portions (heavy-feed batching): the board assembles
  // client-side from ONE call per project instead of the
  // /api/board monolith. The project list rides the
  // shell's shared ["projects"] query; each portion is its
  // own query, so portions render as they land and one
  // project's failure never parks the others. A project
  // scope fetches only its own portion.
  const projectsQuery = useQuery({
    queryKey: projectsKey,
    queryFn: () => api.listProjects({}),
  });
  const projectsPayload = projectsQuery.data?.payload as ProjectsPayload | undefined;
  const allProjects = projectsPayload?.projects ?? [];
  const targets = slug ? allProjects.filter((p) => p.slug === slug) : allProjects;

  const portionQueries = useQueries({
    queries: targets.map((p) => ({
      queryKey: boardKey(p.slug),
      queryFn: () => api.getBoardProject({ slug: p.slug }),
      refetchInterval: 30000,
    })),
  });
  const portions: BoardProjectPayload[] = [];
  const failedNames: string[] = [];
  let pendingCount = 0;
  targets.forEach((p, i) => {
    const q = portionQueries[i];
    if (!q) return;
    if (q.isPending) {
      pendingCount += 1;
      return;
    }
    const payload = q.data?.payload as BoardProjectPayload | undefined;
    if (q.isError || !payload) failedNames.push(p.name);
    else portions.push(payload);
  });

  // Done-lane pagination: page 0 rides each portion; the
  // expanded lane's "show more" fetches the next page per
  // project (offset = pages * the portion page size) and
  // accumulates the slices here. Any board mutation
  // resets the accumulation alongside the invalidation.
  const [doneExtra, setDoneExtra] = useState<
    Record<string, { todos: TodoItem[]; plans: BoardPlan[] }>
  >({});
  const [donePages, setDonePages] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  // A scope switch restarts pagination (the React-docs
  // pattern for adjusting state when a prop changes:
  // set during render, guarded by the previous value).
  const [prevSlug, setPrevSlug] = useState(slug);
  if (prevSlug !== slug) {
    setPrevSlug(slug);
    setDoneExtra({});
    setDonePages(0);
    setDoneExpanded(false);
  }
  const pageSize = portions[0]?.done_page.limit ?? 50;
  const loadedDone = (kind: "todos" | "plans") =>
    portions.reduce(
      (sum, p) => sum + (p[kind].done ?? []).length + (doneExtra[p.slug]?.[kind].length ?? 0),
      0,
    );
  const totalDone = (kind: "todos" | "plans") =>
    portions.reduce((sum, p) => sum + (p.counts[kind].done ?? 0), 0);
  const hasMoreDone =
    loadedDone("todos") < totalDone("todos") || loadedDone("plans") < totalDone("plans");
  const doneRemaining =
    totalDone("todos") - loadedDone("todos") + (totalDone("plans") - loadedDone("plans"));
  const loadMoreDone = async () => {
    setLoadingMore(true);
    try {
      const offset = (donePages + 1) * pageSize;
      const results = await Promise.all(
        portions.map((p) =>
          api.getBoardProject({ slug: p.slug, doneOffset: offset, doneLimit: pageSize }),
        ),
      );
      setDoneExtra((prev) => {
        const next = { ...prev };
        portions.forEach((p, i) => {
          const payload = results[i]?.payload as BoardProjectPayload | undefined;
          if (!payload) return;
          const cur = next[p.slug] ?? { todos: [], plans: [] };
          next[p.slug] = {
            todos: [...cur.todos, ...(payload.todos.done ?? [])],
            plans: [...cur.plans, ...(payload.plans.done ?? [])],
          };
        });
        return next;
      });
      setDonePages((n) => n + 1);
    } finally {
      setLoadingMore(false);
    }
  };

  const mutation = useMutation({
    mutationFn: (args: { project: string; id: string; status: string }) =>
      api.todoAction({
        slug: args.project,
        body: { verb: "set-status", id: args.id, status: args.status },
      }),
    onSuccess: () => {
      setDoneExtra({});
      setDonePages(0);
      void queryClient.invalidateQueries({ queryKey: boardRootKey });
      void queryClient.invalidateQueries({ queryKey: todosRootKey });
      void queryClient.invalidateQueries({ queryKey: plansRootKey });
    },
  });

  if (projectsQuery.isPending) return <SkeletonWell label="the board" />;
  if (targets.length > 0 && portions.length === 0 && failedNames.length === 0) {
    return <SkeletonWell label="the board" />;
  }
  if (targets.length > 0 && portions.length === 0) {
    return <ErrorWell section="Board" message="the board feed could not be loaded." />;
  }
  // The header's freshness label reads the OLDEST
  // portion stamp — the board is only as fresh as its
  // stalest project.
  const capturedAt = portions.reduce<string | undefined>((oldest, p) => {
    if (!p.captured_at) return oldest;
    if (!oldest) return p.captured_at;
    return Date.parse(p.captured_at) < Date.parse(oldest) ? p.captured_at : oldest;
  }, undefined);
  const review = portions.flatMap((p) => p.review_queue);
  const todosIn = (lane: TodoLane): TodoItem[] =>
    portions.flatMap((p) => [
      ...(p.todos[lane] ?? []),
      ...(lane === "done" ? (doneExtra[p.slug]?.todos ?? []) : []),
    ]);
  const plansIn = (bucket: string): BoardPlan[] =>
    portions.flatMap((p) => [
      ...(p.plans[bucket] ?? []),
      ...(bucket === "done" ? (doneExtra[p.slug]?.plans ?? []) : []),
    ]);
  const countOf = (lane: TodoLane) =>
    portions.reduce((sum, p) => {
      const plans = lane === "blocked" ? 0 : (p.counts.plans[lane] ?? 0);
      return sum + (p.counts.todos[lane] ?? 0) + plans;
    }, 0);
  const reviewTotal = portions.reduce((sum, p) => sum + p.counts.review_queue, 0);
  const total = reviewTotal + TODO_LANES.reduce((sum, lane) => sum + countOf(lane), 0);
  const scopeName = projectName ?? "all projects";

  const dropOn = (lane: TodoLane) => (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(null);
    const raw = e.dataTransfer.getData("text/plain");
    if (!raw) return;
    const [project, id, from] = raw.split("\n");
    if (!project || !id || from === lane) return;
    mutation.mutate({ project, id, status: lane });
  };

  // Phone (◆2): lanes stack vertically in lane order and
  // cards take the full lane width — no sideways scrolling
  // anywhere in the Board. Desktop keeps the 264px card in
  // the horizontally scrolling lane row.
  const cardOverride: React.CSSProperties | undefined = isPhone ? { width: "100%" } : undefined;
  const laneWrapStyle: React.CSSProperties = isPhone
    ? { width: "100%" }
    : { flexShrink: 0, width: "288px" };

  const todoCard = (todo: TodoItem) => {
    const fromDb = todo.source === "db";
    const draggable = !fromDb && todo.valid !== false && todo.id != null;
    return (
      <CardShell
        styleOverride={cardOverride}
        key={`${todo.project}:${todo.path ?? todo.id}`}
        glyph="☑"
        projectName={todo.project_name ?? todo.project ?? ""}
        title={todo.title ?? todo.path ?? "Untitled todo"}
        draggable={draggable}
        onDragStart={(e) => {
          e.dataTransfer.setData(
            "text/plain",
            `${todo.project ?? slug ?? ""}\n${todo.id ?? ""}\n${todo.status ?? ""}`,
          );
          e.dataTransfer.effectAllowed = "move";
        }}
        footer={
          <>
            {todo.bundle ? <span className="mono">{todo.bundle}</span> : null}
            {todo.feature ? <span> · {todo.feature}</span> : null}
            {todo.worktree ? <span className="mono"> · {todo.worktree}</span> : null}
            {fromDb ? <span> · registry DB — import to move</span> : null}
            {!draggable && !fromDb ? <span> · invalid front-matter</span> : null}
          </>
        }
      />
    );
  };

  const planCard = (plan: BoardPlan) => (
    <CardShell
      styleOverride={cardOverride}
      key={`${plan.project}:${plan.path}`}
      glyph="❑"
      projectName={plan.project_name ?? plan.project ?? ""}
      title={plan.title || plan.path}
      draggable={false}
      onOpen={() => {
        if (plan.project) {
          window.location.hash = sectionHref(plan.project, "plans", plan.path);
        }
      }}
      footer={
        <>
          <span className="num">{plan.step_count}</span> steps · derived
          {plan.bundle ? <span className="mono"> · {plan.bundle}</span> : null}
        </>
      }
    />
  );

  const reviewCard = (item: ReviewItem) => (
    <CardShell
      styleOverride={cardOverride}
      key={`${item.project}:${item.id}`}
      glyph="▤"
      projectName={item.project_name ?? item.project ?? ""}
      title={item.title}
      draggable={false}
      onOpen={() => {
        if (item.project) {
          // Every review card opens in the one Entries
          // collection (SPEC §8.4), whatever its kind.
          window.location.hash = sectionHref(item.project, "entries", item.id);
        }
      }}
      footer={
        <>
          {kindLabel(item.kind ?? "mockup")} ·{" "}
          {(item.reasons ?? []).join(" · ") || "awaiting review"} · derived
        </>
      }
    />
  );

  return (
    <section>
      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--wb-space-12)" }}>
        <h1 style={sectionTitleStyle}>Board</h1>
        <UpdatedAgo capturedAt={capturedAt} />
      </div>
      {mutation.isError ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          The move was refused — the card&rsquo;s file was not changed. Reload the board to see its
          current state.
        </p>
      ) : null}
      {pendingCount > 0 ? (
        <p style={{ color: "var(--wb-content-muted)" }}>
          Loading {pendingCount} project{pendingCount === 1 ? "" : "s"}…
        </p>
      ) : null}
      {failedNames.length > 0 ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          Could not load {failedNames.join(", ")} — the rest of the board is shown.
        </p>
      ) : null}
      {total === 0 && pendingCount === 0 ? (
        <EmptyWell>Nothing in progress for {scopeName} — the board is empty.</EmptyWell>
      ) : (
        <div
          data-anchor={anchor.boardLanes}
          style={{
            display: "flex",
            flexDirection: isPhone ? "column" : "row",
            gap: "var(--wb-space-16)",
            alignItems: isPhone ? "stretch" : "flex-start",
            overflowX: isPhone ? "visible" : "auto",
            paddingBottom: "var(--wb-space-8)",
          }}
        >
          <div style={laneWrapStyle}>
            <Lane title="Review queue" count={reviewTotal} accent>
              {review.length === 0 ? (
                <p style={{ color: "var(--wb-content-muted)", margin: 0 }}>
                  Nothing awaiting review
                </p>
              ) : (
                review.map(reviewCard)
              )}
            </Lane>
          </div>
          {TODO_LANES.map((lane) => {
            const todos = todosIn(lane);
            const plans = lane === "blocked" ? [] : plansIn(lane);
            const count = countOf(lane);
            const collapsed = lane === "done" && count > 12 && !doneExpanded;
            return (
              // biome-ignore lint/a11y/noStaticElementInteractions: HTML5 drag-and-drop target; the identical status move is keyboard-available in the Todos section's status select
              <div
                key={lane}
                style={laneWrapStyle}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(lane);
                }}
                onDragLeave={() => setDragOver((cur) => (cur === lane ? null : cur))}
                onDrop={dropOn(lane)}
              >
                <Lane
                  title={todoStatusLabel(lane)}
                  count={count}
                  countWarning={lane === "doing" && count > 7}
                >
                  {collapsed ? (
                    <Button variant="secondary" onClick={() => setDoneExpanded(true)}>
                      <span className="num">{count}</span> done cards — expand
                    </Button>
                  ) : (
                    <>
                      {todos.map(todoCard)}
                      {plans.map(planCard)}
                      {lane === "done" && hasMoreDone ? (
                        <Button
                          variant="secondary"
                          onClick={() => void loadMoreDone()}
                          disabled={loadingMore}
                        >
                          {loadingMore ? (
                            "Loading…"
                          ) : (
                            <>
                              Show more done cards — <span className="num">{doneRemaining}</span>{" "}
                              remaining
                            </>
                          )}
                        </Button>
                      ) : null}
                      {count === 0 ? (
                        <p style={{ color: "var(--wb-content-muted)", margin: 0 }}>
                          {dragOver === lane ? "Drop to move here" : "No cards"}
                        </p>
                      ) : null}
                    </>
                  )}
                </Lane>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
