// Typed client over the server actions (the git repo viewer's
// api.ts pattern): types come straight from
// `server/src/actions.ts` — no codegen. `import type` is
// load-bearing: the client bundle never pulls in server
// runtime, and `verbatimModuleSyntax` makes dropping `type`
// a compile error.
//
// Every action returns the bridge envelope
// `{ status, payload, error }`: `status` is the companion
// server's HTTP status (0 = unreachable over the socket),
// `payload` is the server's body verbatim, `error` its
// `{error}` string when it sent one. Sections read payloads
// through the feed types below; they never fetch directly —
// the only network this artifact touches is its own action
// channel to the privileged raw-socket bridge (SPEC §8).

import { createActionClient } from "@hatch/space-sdk/client";
import type { Actions } from "../../../server/src/actions";

export const api = createActionClient<typeof Actions>();

export type { ApiRequest, ApiResponse } from "@hatch/space-sdk/client";

// ---------------------------------------------------------------------------
// Feed payload types (the companion server's shapes, SPEC §7)
// ---------------------------------------------------------------------------

export interface ProjectSections {
  mockups: boolean;
  todos: boolean;
  plans: boolean;
  registry_declared: boolean;
  plans_declared: boolean;
}

export interface ProjectSummary {
  slug: string;
  name: string;
  root: string;
  sections: ProjectSections;
}

export interface ProjectsPayload {
  captured_at?: string;
  projects: ProjectSummary[];
  errors: unknown[];
}

export interface HealthPayload {
  ok: boolean;
  version: string;
  commit?: string;
  host: string;
  port: number;
  projects_count: number;
  sweep?: { projects: number; errors: number };
}

export interface ConfigPayload {
  config: Record<string, unknown>;
  config_hash?: string;
}

/** Every per-project feed carries this envelope (SPEC §7). */
export interface FeedEnvelope {
  slug: string;
  name: string;
  degraded: boolean;
  available: boolean;
  reason?: string;
}

export interface MockupEntry {
  id: string;
  title: string;
  kind: string;
  status: string;
  gate?: string | null;
  archived?: boolean;
  stale?: unknown;
  [key: string]: unknown;
}

export interface MockupsFeed extends FeedEnvelope {
  entries: MockupEntry[];
  triage: MockupEntry[];
  reconcile: { status: string; problems: unknown[]; error: string | null } | null;
}

export interface PlanSummary {
  path: string;
  title: string;
  status_raw: string | null;
  status_bucket: string;
  conforming: boolean;
  step_count: number;
  mermaid_count: number;
  archived: boolean;
  modified: number;
  feature?: string | null;
}

/** One bundle (live-work spec §3): a directory with an
 * optional plan + its todo files, or a legacy flat plan. */
export interface BundleItem {
  kind: "bundle" | "flat-plan";
  id: string;
  slug: string;
  path: string;
  archived: boolean;
  feature: string | null;
  plan: PlanSummary | null;
  todos: TodoItem[];
  errors: { path: string; error: string }[];
  todo_count: number;
  open_count: number;
}

export interface PlansFeed extends FeedEnvelope {
  plans: PlanSummary[];
  bundles: BundleItem[];
}

/** A plan's structured document (lib/plans/parser.py via
 * GET /projects/<slug>/plan?path=). */
export interface PlanBlock {
  type: "markdown" | "code" | "mermaid";
  text?: string;
  source?: string;
  raw: string;
  lang?: string;
}

export interface PlanSection {
  heading: string;
  level: number;
  raw: string;
  blocks: PlanBlock[];
  is_rulings: boolean;
  is_steps: boolean;
}

export interface PlanStep {
  n: number;
  title: string;
  body: string;
  files: string;
  verify: string;
  done_when: string;
  raw: string;
}

export interface PlanDoc {
  path: string;
  title: string;
  fields: Record<string, string>;
  status_raw: string | null;
  status_bucket: string;
  conforming: boolean;
  header_raw: string;
  sections: PlanSection[];
  steps: PlanStep[];
  step_count: number;
  mermaid_count: number;
  markdown: string;
  archived?: boolean;
}

export interface TodoItem {
  id: string | null;
  title: string | null;
  status: string | null;
  // bundle todo-file fields (live-work spec §3.2)
  bundle?: string | null;
  feature?: string | null;
  plan?: string | null;
  plan_step?: number | null;
  worktree?: string | null;
  body?: string;
  path?: string;
  valid?: boolean;
  errors?: string[];
  archived?: boolean;
  created?: string | null;
  updated?: string | null;
  // registry-DB fallback rows (§3.7) keep their DB shape
  source?: string;
  notes?: string;
  link_kind?: string | null;
  link_ref?: string | null;
  project?: string;
  project_name?: string;
  [key: string]: unknown;
}

export interface TodosFeed extends FeedEnvelope {
  todos: TodoItem[];
  /** "files" = bundle todo files; "db-fallback" = §3.7. */
  source?: string;
  errors?: { path: string; error: string }[];
}

export interface AllTodosPayload {
  todos: TodoItem[];
  errors?: unknown[];
}

export interface BoardPlan extends PlanSummary {
  project?: string;
  project_name?: string;
  bundle?: string;
  bundle_kind?: string;
}

export interface ReviewItem {
  id: string;
  title: string;
  reasons: string[];
  project?: string;
  project_name?: string;
  [key: string]: unknown;
}

/** One worktree derivation (lib/worktrees via
 * GET /api/projects/<slug>/worktrees, repo-home §6). */
export interface WorktreeItem {
  path: string;
  branch: string | null;
  head: string | null;
  head_short: string | null;
  is_main: boolean;
  base: string | null;
  ahead: number | null;
  behind: number | null;
  dirty: boolean | null;
  changed_count: number | null;
  degraded: boolean;
  reason: string | null;
  [key: string]: unknown;
}

export interface WorktreesPayload {
  slug: string;
  name: string;
  captured_at: string;
  available: boolean;
  reason?: string;
  worktrees: WorktreeItem[];
}

/** One rendered diff line (lib/diffs, repo-home §18). */
export interface DiffLine {
  kind: "context" | "add" | "del" | "meta";
  text: string;
  old_no: number | null;
  new_no: number | null;
}

export interface DiffHunk {
  old_start: number;
  old_lines: number;
  new_start: number;
  new_lines: number;
  lines: DiffLine[];
}

export interface DiffFileEntry {
  path: string;
  old_path: string | null;
  status: "modified" | "added" | "deleted" | "renamed";
  binary: boolean;
  additions: number;
  deletions: number;
  truncated: boolean;
  legs?: string[];
  hunks: DiffHunk[];
}

/** An untracked file's new-file rendering, or an ignored
 * file's peek (same shape; §18.4). */
export interface DiffPeek {
  path: string;
  withheld: "secret" | "symlink" | "missing" | "escapes" | null;
  is_binary: boolean;
  size_bytes: number;
  truncated: boolean;
  hunks: DiffHunk[];
  is_dir?: boolean;
}

export interface IgnoredChangedEntry {
  path: string;
  size_bytes: number;
  modified: number;
  withheld: "secret" | null;
  is_binary: boolean;
}

export interface DiffWarning {
  kind: string;
  path: string;
  message: string;
}

/** The anchored diff payload (GET /api/projects/<slug>/
 * diff, §18.5). */
export interface DiffPayload {
  slug: string;
  name: string;
  captured_at: string;
  anchor: {
    kind: "worktree" | "bundle" | "commit";
    worktree: string;
    branch: string | null;
    bundle: string | null;
  };
  mode: string;
  base: string | null;
  target: string | null;
  merge_base: string | null;
  head: string;
  narrowed: boolean;
  declared_files: string[];
  files: DiffFileEntry[];
  totals: { files: number; additions: number; deletions: number };
  empty: boolean;
  untracked: DiffPeek[];
  ignored_changed: IgnoredChangedEntry[];
  ignored_truncated: boolean;
  warnings: DiffWarning[];
}

export interface DiffPeekPayload {
  slug: string;
  name: string;
  captured_at: string;
  peek: DiffPeek;
}

export interface BoardPayload {
  todos: Record<string, TodoItem[]>;
  plans: Record<string, BoardPlan[]>;
  review_queue: ReviewItem[];
  errors?: unknown[];
  [key: string]: unknown;
}
