// Board — a view over exactly three sources (SPEC §8.4,
// live-work spec §3.5): the registry review queue (FIRST
// lane, read-only), bundle todo files (lanes by todo
// status: todo / doing / blocked / done), and plan cards
// derived from plan headers (read-only). ONLY todo cards
// drag — a drag is exactly one server todo mutation (the
// lib writer under `wb todo set`) and nothing else. Plan
// and review cards carry no handle; clicking one opens its
// source. Deleting this section would lose no data: every
// card's source record lives in its own store.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../components/Button";
import { Lane } from "../components/Lane";
import { api, type BoardPayload, type BoardPlan, type ReviewItem, type TodoItem } from "../lib/api";
import { todoStatusLabel } from "../lib/labels";
import { useIsPhone } from "../lib/responsive";
import { sectionHref } from "../lib/routing";
import { anchor } from "./plans/anchors";
import { EmptyWell, ErrorWell, SkeletonWell, sectionTitleStyle } from "./shared";

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
  const query = useQuery({
    queryKey: ["board"],
    queryFn: () => api.getBoard({}),
  });

  const mutation = useMutation({
    mutationFn: (args: { project: string; id: string; status: string }) =>
      api.todoAction({
        slug: args.project,
        body: { verb: "set-status", id: args.id, status: args.status },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["board"] });
      void queryClient.invalidateQueries({ queryKey: ["todos"] });
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });

  if (query.isPending) return <SkeletonWell label="the board" />;
  if (query.isError) {
    return <ErrorWell section="Board" message="the board feed could not be loaded." />;
  }
  const { payload, error } = query.data;
  if (!payload) {
    return <ErrorWell section="Board" message={error ?? "the companion server did not answer."} />;
  }
  const board = payload as unknown as BoardPayload;
  const inScope = (project: string | undefined) => slug == null || project === slug;
  const review = board.review_queue.filter((item) => inScope(item.project));
  const todosIn = (lane: TodoLane) =>
    (board.todos[lane] ?? []).filter((todo) => inScope(todo.project));
  const plansIn = (bucket: string) =>
    (board.plans[bucket] ?? []).filter((plan) => inScope(plan.project));
  const total =
    review.length +
    TODO_LANES.reduce((sum, lane) => sum + todosIn(lane).length, 0) +
    (["todo", "doing", "done"] as const).reduce((sum, b) => sum + plansIn(b).length, 0);
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
          window.location.hash = sectionHref(item.project, "mockups", item.id);
        }
      }}
      footer={<>{(item.reasons ?? []).join(" · ") || "awaiting review"} · derived</>}
    />
  );

  return (
    <section>
      <h1 style={sectionTitleStyle}>Board</h1>
      {mutation.isError ? (
        <p role="alert" style={{ color: "var(--wb-danger)" }}>
          The move was refused — the card&rsquo;s file was not changed. Reload the board to see its
          current state.
        </p>
      ) : null}
      {total === 0 ? (
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
            <Lane title="Review queue" count={review.length} accent>
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
            const count = todos.length + plans.length;
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
