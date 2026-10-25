// THE label map — human labels for every machine value the
// shell or a section can show (SPEC §14 uniformity: no
// machine enum is ever shown raw). Add a value here when the
// server grows one; the humanize fallback exists only so an
// unmapped value degrades to readable text, never snake_case.

const RULED_STATUS_LABELS: Record<string, string> = {
  canonical: "Canonical",
  implemented: "Implemented",
  deferred: "Deferred",
  unexplored: "Unexplored",
  "hard-gate": "Hard gate",
  abandoned: "Abandoned",
};

const DERIVED_STATE_LABELS: Record<string, string> = {
  stale: "Stale",
  "not-covered": "Approval doesn't cover current state",
  "needs-changes": "Needs changes",
  approved: "Approved",
  "in-triage": "In triage",
};

const TODO_STATUS_LABELS: Record<string, string> = {
  todo: "To do",
  doing: "Doing",
  blocked: "Blocked",
  done: "Done",
};

const PLAN_BUCKET_LABELS: Record<string, string> = {
  todo: "To do",
  doing: "In progress",
  done: "Done",
};

const KIND_LABELS: Record<string, string> = {
  mockup: "Mockup",
  plan: "Plan",
  todo: "Todo",
  review: "Review",
};

const SECTION_LABELS: Record<string, string> = {
  mockups: "Mockups",
  plans: "Plans",
  todos: "Todos",
  board: "Board",
  settings: "Settings",
};

function humanize(raw: string): string {
  const words = raw.replace(/[_-]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : raw;
}

function from(map: Record<string, string>, raw: string | null | undefined): string {
  if (!raw) return "";
  return map[raw] ?? humanize(raw);
}

export const ruledStatusLabel = (raw: string | null | undefined) => from(RULED_STATUS_LABELS, raw);
export const derivedStateLabel = (raw: string | null | undefined) =>
  from(DERIVED_STATE_LABELS, raw);
export const todoStatusLabel = (raw: string | null | undefined) => from(TODO_STATUS_LABELS, raw);
export const planBucketLabel = (raw: string | null | undefined) => from(PLAN_BUCKET_LABELS, raw);
export const kindLabel = (raw: string | null | undefined) => from(KIND_LABELS, raw);
export const sectionLabel = (raw: string | null | undefined) => from(SECTION_LABELS, raw);

/** Human label for a project-section availability state. */
export function availabilityLabel(available: boolean, degraded: boolean): string {
  if (degraded) return "Degraded";
  return available ? "Available" : "Not set up";
}
