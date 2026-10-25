// Todos — shell-checkpoint frame (Subplan 05). The full
// list (inline add, status editing, cross-project segment)
// is Subplan 07; this frame reads the project's real todos
// feed and lists what exists, open first, done collapsed to
// a count — or the honest empty state.

import { useQuery } from "@tanstack/react-query";
import { api, type TodosFeed } from "../lib/api";
import { todoStatusLabel } from "../lib/labels";
import {
  DegradedBanner,
  EmptyWell,
  ErrorWell,
  listRowStyle,
  metaStyle,
  SkeletonWell,
  sectionTitleStyle,
} from "./shared";

export function TodosSection({ slug, projectName }: { slug: string; projectName: string }) {
  const query = useQuery({
    queryKey: ["todos", slug],
    queryFn: () => api.getProjectTodos({ slug }),
  });

  if (query.isPending) return <SkeletonWell label={`todos for ${projectName}`} />;
  if (query.isError) {
    return <ErrorWell section="Todos" message="the section feed could not be loaded." />;
  }
  const { payload, error } = query.data;
  if (!payload) {
    return <ErrorWell section="Todos" message={error ?? "the companion server did not answer."} />;
  }
  const feed = payload as unknown as TodosFeed;
  const open = feed.todos.filter((todo) => todo.status !== "done");
  const done = feed.todos.filter((todo) => todo.status === "done");

  return (
    <section>
      <h1 style={sectionTitleStyle}>Todos</h1>
      <DegradedBanner feed={feed} />
      {feed.todos.length === 0 ? (
        <EmptyWell>
          {feed.available
            ? `No todos in ${projectName} — the list is empty.`
            : `No todos for ${projectName} — this project's registry is not set up.`}
        </EmptyWell>
      ) : (
        <>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {open.map((todo) => (
              <li key={todo.id} style={listRowStyle}>
                <span style={{ flex: 1 }}>{todo.title}</span>
                <span style={metaStyle}>{todoStatusLabel(todo.status)}</span>
              </li>
            ))}
          </ul>
          {done.length > 0 ? (
            <p style={{ color: "var(--wb-content-muted)" }}>
              <span className="num">{done.length}</span> completed, collapsed.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
