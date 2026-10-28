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
  artifact: "Artifact",
  plan: "Plan",
  todo: "Todo",
  review: "Review",
};

const SECTION_LABELS: Record<string, string> = {
  overview: "Overview",
  mockups: "Mockups",
  artifacts: "Artifacts",
  plans: "Plans",
  todos: "Todos",
  board: "Board",
  settings: "Settings",
  inbox: "Inbox",
  repos: "Repos",
};

/** A repo's publication posture (lib/repos.py): whether a
 * remote exists and whether the branch tracks one. */
const PUBLICATION_LABELS: Record<string, string> = {
  local_only: "Local only",
  remote_no_upstream: "Remote · no upstream",
  tracking: "Tracking",
};

/** The exposure derivation's levels (lib/repos.py): what
 * is not backed up, worst first. */
const EXPOSURE_LABELS: Record<string, string> = {
  local_only: "Local only",
  uncommitted_work: "Uncommitted work",
  unbacked_commits: "Unbacked commits",
  backed_up: "Backed up",
};

const SYNC_STATE_LABELS: Record<string, string> = {
  local_only: "Local only",
  no_upstream: "No upstream",
  diverged: "Diverged",
  ahead: "Ahead",
  behind: "Behind",
  synced: "Synced",
};

/** The registry's expected-publication vocabulary
 * (lib/repo_state.py EXPECTED_VALUES). */
const EXPECTED_LABELS: Record<string, string> = {
  published: "Published",
  local_ok: "Local OK",
  untracked: "Untracked",
};

const MESSAGE_STATE_LABELS: Record<string, string> = {
  draft: "Draft",
  sent: "Sent",
  acknowledged: "Acknowledged",
  done: "Done",
  archived: "Archived",
};

/** §17.2 provenance: how a worktree's active plan was
 * resolved. `declared` is a ruling; the rest are derived
 * signals, and recency names its own weakness. */
const ACTIVE_SOURCE_LABELS: Record<string, string> = {
  declared: "Declared",
  branch: "By branch",
  unique: "Only one in progress",
  recency: "By recency",
  none: "No active plan",
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
export const messageStateLabel = (raw: string | null | undefined) =>
  from(MESSAGE_STATE_LABELS, raw);
export const activeSourceLabel = (raw: string | null | undefined) =>
  from(ACTIVE_SOURCE_LABELS, raw);
export const publicationLabel = (raw: string | null | undefined) => from(PUBLICATION_LABELS, raw);
export const exposureLabel = (raw: string | null | undefined) => from(EXPOSURE_LABELS, raw);
export const syncStateLabel = (raw: string | null | undefined) => from(SYNC_STATE_LABELS, raw);
export const expectedLabel = (raw: string | null | undefined) => from(EXPECTED_LABELS, raw);

/** Human label for a project-section availability state. */
export function availabilityLabel(available: boolean, degraded: boolean): string {
  if (degraded) return "Degraded";
  return available ? "Available" : "Not set up";
}
