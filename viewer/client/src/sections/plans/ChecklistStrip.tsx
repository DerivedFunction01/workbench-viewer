// The bundle checklist strip: a bundle's todos as a
// row of status pills. Shared by the plan list rows
// and the reader — a bundle's todos ride its plan
// as this strip, above the document.

import type { TodoItem } from "../../lib/api-types";

export const STATUS_GLYPH: Record<string, string> = {
  todo: "○",
  doing: "●",
  blocked: "⚠",
  done: "✓",
};

export function ChecklistStrip({ todos }: { todos: TodoItem[] }) {
  if (todos.length === 0) return null;
  return (
    <ul
      style={{
        listStyle: "none",
        margin: "var(--wb-space-8) 0 0",
        padding: 0,
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--wb-space-8)",
      }}
    >
      {todos.map((todo) => (
        <li
          key={todo.path ?? todo.id ?? todo.title ?? ""}
          style={{
            border: "1px solid var(--wb-border-default)",
            borderRadius: "var(--wb-radius-pill)",
            padding: "0 var(--wb-space-8)",
            fontSize: "var(--wb-font-size-xs)",
            lineHeight: "var(--wb-line-height-xs)",
            color: todo.valid === false ? "var(--wb-danger)" : "var(--wb-content-secondary)",
          }}
        >
          <span aria-hidden="true">
            {todo.valid === false ? "⚠" : (STATUS_GLYPH[todo.status ?? ""] ?? "○")}{" "}
          </span>
          {todo.title ?? todo.path ?? "Untitled todo"}
          {todo.valid === false ? " · invalid" : ""}
        </li>
      ))}
    </ul>
  );
}
