// Plan anchors (repo-home spec §14.5): derived STRUCTURALLY
// at render time, never authored — heading sections by
// slug, step blocks by step number, tables and diagrams by
// index within their section. Ids only, in the
// `<section>/<component>` shape; no annotation UI, no
// manifest. A rename of a heading = a new anchor, by rule.

export function slugify(text: string): string {
  const slug = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "section";
}

export const anchor = {
  planList: "plans/plan-list",
  planReader: "plans/plan-reader",
  planHeader: "plans/plan-header",
  section: (heading: string) => `plans/section-${slugify(heading)}`,
  step: (n: number) => `plans/step-${n}`,
  table: (heading: string, index: number) => `plans/table-${slugify(heading)}-${index}`,
  diagram: (heading: string, index: number) => `plans/diagram-${slugify(heading)}-${index}`,
  todoTable: "todos/todo-table",
  boardLanes: "board/board-lanes",
};
