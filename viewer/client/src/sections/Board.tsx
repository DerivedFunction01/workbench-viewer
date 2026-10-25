// Board — shell-checkpoint frame (Subplan 05). The kanban
// (lanes, draggable todo cards) is Subplan 07; this frame
// reads the real cross-project board feed and renders its
// derived counts and lane contents as lists scoped to the
// selected project (or every project, from #/board) — the
// board is a view over todos, plans, and the review queue,
// never a fourth store (SPEC §8.4).

import { useQuery } from "@tanstack/react-query";
import { api, type BoardPayload } from "../lib/api";
import { todoStatusLabel } from "../lib/labels";
import {
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";

const BUCKETS = ["todo", "doing", "done"] as const;

export function BoardSection({
  slug,
  projectName,
}: {
  slug: string | null;
  projectName: string | null;
}) {
  const query = useQuery({
    queryKey: ["board"],
    queryFn: () => api.getBoard({}),
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
  const todoCount = BUCKETS.reduce(
    (sum, bucket) =>
      sum + (board.todos[bucket] ?? []).filter((todo) => inScope(todo.project)).length,
    0,
  );
  const planCount = BUCKETS.reduce(
    (sum, bucket) =>
      sum + (board.plans[bucket] ?? []).filter((plan) => inScope(plan.project)).length,
    0,
  );
  const scopeName = projectName ?? "all projects";

  return (
    <section>
      <h1 style={sectionTitleStyle}>Board</h1>
      {review.length === 0 && todoCount === 0 && planCount === 0 ? (
        <EmptyWell>Nothing in progress for {scopeName} — the board is empty.</EmptyWell>
      ) : (
        <>
          <p style={{ color: "var(--wb-content-secondary)" }}>
            <span className="num">{review.length}</span> awaiting review ·{" "}
            <span className="num">{todoCount}</span> todos ·{" "}
            <span className="num">{planCount}</span> plans
            {slug == null ? " across all projects" : ""}
          </p>
          {review.length > 0 ? (
            <>
              <h2>Review queue</h2>
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {review.slice(0, 10).map((item) => (
                  <li key={`${item.project ?? ""}:${item.id}`} style={listRowStyle}>
                    <span style={{ flex: 1 }}>{item.title}</span>
                    <span style={metaStyle}>{item.project_name ?? item.project}</span>
                  </li>
                ))}
              </ul>
              {review.length > 10 ? (
                <p style={{ color: "var(--wb-content-muted)" }}>
                  …and <span className="num">{review.length - 10}</span> more in the queue.
                </p>
              ) : null}
            </>
          ) : null}
          {BUCKETS.map((bucket) => {
            const todos = (board.todos[bucket] ?? []).filter((todo) => inScope(todo.project));
            if (todos.length === 0) return null;
            return (
              <div key={bucket}>
                <h2>
                  {todoStatusLabel(bucket)} · <span className="num">{todos.length}</span>
                </h2>
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {todos.map((todo) => (
                    <li key={`${todo.project ?? ""}:${todo.id}`} style={listRowStyle}>
                      <span style={{ flex: 1 }}>{todo.title}</span>
                      <span style={metaStyle}>{todo.project_name ?? todo.project}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </>
      )}
    </section>
  );
}
