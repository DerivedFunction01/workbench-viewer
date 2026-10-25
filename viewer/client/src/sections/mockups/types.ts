// Local feed/detail types for the Mockups section — the
// companion server's shapes (SPEC §4/§7), read off the bridge
// envelopes in lib/api.ts. lib/api.ts carries the loose feed
// envelope; the full entry rows (the export fold: entry +
// derived + approval) and the entry-detail payload are typed
// here, where they are consumed.

export interface DerivedStaleness {
  age_days: number;
  days_since_verified: number;
  never_verified: boolean;
  drift: boolean;
  stale: boolean;
  reasons: string[];
}

export interface ApprovalCoverage {
  approved: boolean;
  covers_current: boolean;
  approved_state_sha256: string | null;
  current_state_sha256: string;
  approved_at: string | null;
}

export interface FullEntry {
  id: string;
  title: string;
  kind: string;
  status: string;
  gate?: string | null;
  ruling_text?: string | null;
  ruling_date?: string | null;
  spec_ref?: string | null;
  plan_ref?: string | null;
  source_kind: string;
  source_ref?: string | null;
  entry_dir?: string | null;
  main_file?: string | null;
  content_sha256?: string | null;
  config_path?: string | null;
  state_schema?: Record<string, unknown> | null;
  state_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  status_changed_at: string;
  last_verified_at?: string | null;
  archived: boolean;
  archived_at?: string | null;
  superseded_by?: string | null;
  version: number;
  derived?: DerivedStaleness;
  approval?: ApprovalCoverage;
}

export interface TriageItem {
  id: string;
  title: string;
  reasons: string[];
}

export interface Reconcile {
  status: string;
  problems: unknown[];
  error: string | null;
}

export interface MockupsFeedFull {
  slug: string;
  name: string;
  degraded: boolean;
  available: boolean;
  reason?: string;
  entries: FullEntry[];
  triage: TriageItem[];
  reconcile: Reconcile | null;
}

export interface HistoryRow {
  id: number;
  entry_id: string | null;
  ts: string;
  actor: string;
  verb: string;
  field: string | null;
  old: string | null;
  new: string | null;
  note: string | null;
}

export interface ReviewPayload {
  disposition?: string;
  comment?: string;
  state?: Record<string, unknown>;
  state_sha256?: string;
}

export interface LatestReview extends HistoryRow {
  payload?: ReviewPayload;
}

export interface EntryFile {
  path: string;
  size_bytes: number;
  is_main: boolean;
}

export interface EntryDetail {
  entry: FullEntry;
  derived: DerivedStaleness;
  approval: ApprovalCoverage;
  latest_review: LatestReview | null;
  history: HistoryRow[];
  files: EntryFile[];
}

export interface PeekResult {
  path: string;
  size_bytes: number;
  is_binary: boolean;
  withheld: string | null;
  content: string | null;
  sha256: string | null;
  editable: boolean;
  editable_reason: string | null;
  line_count?: number;
  truncated?: boolean;
  captured_at?: string;
}

/** The bridge envelope every action returns (lib/api.ts). */
export interface Envelope {
  status: number;
  payload: unknown;
  error: string | null;
}

export const RULED_STATUSES = [
  "canonical",
  "implemented",
  "deferred",
  "unexplored",
  "hard-gate",
  "abandoned",
] as const;

export type RuledStatusName = (typeof RULED_STATUSES)[number];

export const ENTRY_KINDS = [
  "mockup",
  "prototype",
  "test-route",
  "component-variant",
  "storyboard",
] as const;
