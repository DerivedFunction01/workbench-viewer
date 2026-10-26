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
  artifacts: boolean;
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

/** One resolvable question of a plan's open-questions
 * section (plan syntax standard, the sentinel): the
 * parser's record verbatim. `answer` is the recorded
 * answer ("" = unanswered); `checked` mirrors the source
 * task box (numbered/bullet items derive it from the
 * answer). */
export interface PlanQuestion {
  id: string;
  type: "choice" | "toggle" | "text";
  text: string;
  detail: string;
  options: string[];
  labels: string[];
  recommended: string | null;
  answer: string;
  checked: boolean;
  item_kind: "task" | "numbered" | "bullet";
  line: number;
  sentinel_line: number | null;
  answer_line: number | null;
}

/** One malformed sentinel, reported by the parser: the
 * question degrades to plain rendering and the break is
 * surfaced here (0-based file line + the rule broken). */
export interface PlanSentinelError {
  line: number;
  id: string | null;
  reason: string;
}

export interface PlanSummary {
  path: string;
  title: string;
  status_raw: string | null;
  status_bucket: string;
  conforming: boolean;
  step_count: number;
  open_questions_count: number;
  /** Resolvable questions carried by the summary (the
   * parser's records; [] when the plan has none). */
  questions?: PlanQuestion[];
  /** Declared subplan paths (`.plans/`-relative, §21);
   * carried by bundle summaries. */
  subplans?: string[];
  subplans_count: number;
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
 * GET /api/projects/<slug>/plan?path=). */
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
  /** The flagged questions section only: the blocks no
   * extracted question covers (prose, plain and malformed
   * items, fences). When the Questions card shows, the
   * reader renders these in place of `blocks`, so each
   * question renders once and nothing else is dropped. */
  leftover_blocks?: PlanBlock[];
  is_rulings: boolean;
  is_steps: boolean;
  is_open_questions: boolean;
  is_subplans: boolean;
  is_critical_files: boolean;
}

/** One task-list item of a plan's `## Open questions`
 * section (plan syntax standard). */
export interface PlanOpenQuestion {
  text: string;
  checked: boolean;
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
  open_questions: PlanOpenQuestion[];
  open_questions_count: number;
  /** Resolvable questions (sentinel form) + the parse's
   * malformed-sentinel report. */
  questions: PlanQuestion[];
  sentinel_errors: PlanSentinelError[];
  /** sha256 of the plan file's exact bytes — the resolve
   * write's compare-and-swap base. */
  file_sha256: string;
  /** Declared subplan paths from `## Subplans` (§21),
   * in declaration order. */
  subplans: string[];
  critical_files: string[];
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
  /** The entry's registry kind — the card opens in the
   * collection that owns the kind (artifact → Artifacts,
   * the design kinds → Mockups). */
  kind?: string;
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
  head: string | null;
  base_kind: string | null;
  note: string | null;
  gone: boolean;
  no_commits: boolean;
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

// ---------------------------------------------------------------------------
// Repo-home payloads (repo-home spec §§3-7, §15, §17): the
// /api namespace. Shapes are lib/home.py, lib/worktrees.py,
// lib/active.py, lib/messages.py verbatim.
// ---------------------------------------------------------------------------

/** One bundle's side of an active-plan resolution (§17). */
export interface ActiveBundle {
  id: string;
  slug: string;
  path: string;
  kind: string;
  feature: string | null;
  todo_count: number;
  open_count: number;
}

export interface ActivePlanRef {
  path: string;
  title: string;
  status_bucket: string;
  status_raw: string | null;
  /** Epoch seconds (the plan parser's mtime). */
  modified: number;
  feature: string | null;
}

/** The §17.2 resolution for one worktree, provenance
 * included: `source` is declared (a ruling) or one of the
 * derived signals (branch / unique / recency), or none. */
export interface ActiveResolution {
  source: "declared" | "branch" | "unique" | "recency" | "none";
  bundle: ActiveBundle | null;
  plan: ActivePlanRef | null;
  also_in_progress: { bundle: ActiveBundle; plan: ActivePlanRef | null }[];
  declared: { bundle: string; plan: string | null; since: string | null } | null;
  note: string | null;
}

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
  last_commit_at: string | null;
  untouched_days: number | null;
  no_commits: boolean;
  merged: boolean;
  likely_done: boolean;
  rebase_in_progress: boolean;
  degraded: boolean;
  reason: string | null;
  attribution: { label: string | null; plan: string | null; source: string };
  active?: ActiveResolution | null;
}

export interface WorktreesPayload {
  slug: string;
  name: string;
  captured_at: string;
  available: boolean;
  reason?: string;
  worktrees: WorktreeItem[];
}

/** One row of GET /api/home (§4 + §17 showcase). */
export interface HomeRow {
  slug: string;
  name: string;
  root: string;
  degraded: boolean;
  reasons: string[];
  git: { branch: string | null; head: string | null; head_short: string | null } | null;
  worktrees: WorktreeItem[];
  has_extra_worktrees: boolean;
  showcase: ActiveResolution | null;
  plans: {
    available: boolean;
    counts: Record<string, number>;
    in_progress: { title: string; path: string } | null;
    total: number;
  };
  todos: {
    available: boolean;
    counts: Record<string, number>;
    total: number;
    source?: string;
  };
  review: { available: boolean; triage_count: number; stale_count: number };
  last_activity: string | null;
}

export interface HomePayload {
  projects: HomeRow[];
  sweep_errors?: unknown[];
  captured_at?: string;
}

/** The §12 selection payload an annotation carries
 * (lib/messages.py verbatim): quote + surrounding context
 * for a text passage, the deterministic manifest id for
 * an exhibit component. Raw offsets are refused at
 * create; re-location happens at read/render time. */
export interface TextSelection {
  kind: "text";
  component_id: string;
  component_label?: string;
  section_heading?: string;
  quote: string;
  prefix?: string;
  suffix?: string;
}

export interface ComponentSelection {
  kind: "component";
  component_id: string;
  component_label?: string;
  entry_id?: string;
}

export type SelectionAnchor = TextSelection | ComponentSelection;

/** The derived anchor_context the server attaches to an
 * annotation at read (§12/§13; lib/annotations.py
 * verbatim): where the anchor points NOW — re-location
 * status, the located excerpt, the resolved step — or,
 * for a component, whether it is still present in the
 * exhibit's drill-in. Derived, never stored; absent on
 * non-annotation messages. */
export interface AnchorContextText {
  kind: "text";
  relocated: boolean;
  status: string;
  component_id: string | null;
  component_label: string | null;
  section_heading: string | null;
  step: number | null;
  quote: string | null;
  excerpt: string | null;
  component_missing: boolean;
}

export interface AnchorContextComponent {
  kind: "component";
  component_id: string | null;
  component_label: string | null;
  entry_id: string | null;
  entry_title: string | null;
  present: boolean;
  status: string;
}

export type AnchorContext = AnchorContextText | AnchorContextComponent;

export interface MessageItem {
  id: number;
  project_slug: string | null;
  anchor_type: string;
  anchor_ref: string | null;
  author: string;
  body: string;
  showcase: { main?: unknown; docs?: unknown[] } | null;
  selection: SelectionAnchor | null;
  anchor_context?: AnchorContext | null;
  state: "draft" | "sent" | "acknowledged" | "done" | "archived";
  created_at: string;
  updated_at: string;
  sent_at: string | null;
  acked_at: string | null;
  done_at: string | null;
  archived_at: string | null;
  parent_id: number | null;
  awaiting_pickup?: boolean;
}

export interface MessagesPayload {
  messages: MessageItem[];
  picked_up?: number;
  captured_at?: string;
}

export interface EffectiveSettingsPayload {
  config: Record<string, unknown>;
  config_hash?: string;
  config_file?: string;
  messages: {
    db: string;
    policy: Record<string, number>;
    counts?: Record<string, number>;
    last_cleanup_at?: string | null;
    last_cleanup_counts?: Record<string, number> | null;
    outbox_rows?: number;
    notify_checkpoint?: number;
    error?: string;
  };
  captured_at?: string;
}
