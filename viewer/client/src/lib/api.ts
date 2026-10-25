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
  status_raw: string;
  status_bucket: string;
  conforming: boolean;
  step_count: number;
  mermaid_count: number;
  archived: boolean;
  modified: number;
}

export interface PlansFeed extends FeedEnvelope {
  plans: PlanSummary[];
}

export interface TodoItem {
  id: string;
  title: string;
  status: string;
  notes?: string;
  link_kind?: string | null;
  link_ref?: string | null;
  project?: string;
  project_name?: string;
  [key: string]: unknown;
}

export interface TodosFeed extends FeedEnvelope {
  todos: TodoItem[];
}

export interface AllTodosPayload {
  todos: TodoItem[];
}

export interface BoardPlan extends PlanSummary {
  project?: string;
  project_name?: string;
}

export interface ReviewItem {
  id: string;
  title: string;
  reasons: string[];
  project?: string;
  project_name?: string;
  [key: string]: unknown;
}

export interface BoardPayload {
  todos: Record<string, TodoItem[]>;
  plans: Record<string, BoardPlan[]>;
  review_queue: ReviewItem[];
  errors?: unknown[];
  [key: string]: unknown;
}
