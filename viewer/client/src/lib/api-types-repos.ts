// Repos + dataset payload types: the /api/repos census,
// status, files, history shapes (absorption plan) and
// the dataset Table/console shapes behind them. The
// feed payload types live in lib/api-types; the client
// itself in lib/api.

// ---------------------------------------------------------------------------
// Repos payloads (absorption plan, steps 2-7): the /api/repos
// namespace. Shapes are lib/repos.py (census, status,
// publication, exposure, tree), lib/files.py (repo peek /
// save), and lib/repo_state.py (registry, history) verbatim.
// ---------------------------------------------------------------------------

/** One repo-registry entry (lib/repo_state.py): the
 * harness-owned tracking metadata for a browsed repo. */
export interface RepoRegistryEntry {
  display_name: string;
  project: string;
  expected: "published" | "local_ok" | "untracked";
  pinned: boolean;
  ignored: boolean;
  notes: string;
  root: string;
  first_seen: string;
  last_seen: string;
}

export interface RepoRemote {
  name: string;
  url_display: string;
  host: string;
}

export interface RepoSync {
  state: "local_only" | "no_upstream" | "diverged" | "ahead" | "behind" | "synced";
  unpushed_count: number;
  oldest_unpushed_at: string | null;
}

/** The exposure derivation: what is not backed up, in one
 * record (level + the counts it was derived from). */
export interface RepoExposure {
  level: "local_only" | "uncommitted_work" | "unbacked_commits" | "backed_up";
  commits: number;
  files: number;
}

/** One census row of GET /api/repos: the census record,
 * the summary derivations, and its registry entry. A row
 * whose registry entry exists but whose repo discovery
 * did not find rides with `missing: true` and no
 * derivations. */
export interface RepoSummary {
  id: string;
  name: string;
  root: string;
  is_worktree: boolean;
  parent_id: string | null;
  branch: string | null;
  /** Full HEAD sha (the reference's `head` naming kept). */
  head: string | null;
  head_full: string | null;
  head_short: string | null;
  head_subject: string | null;
  upstream: string | null;
  ahead: number | null;
  behind: number | null;
  dirty_counts: { staged: number; unstaged: number; untracked: number } | null;
  is_clean: boolean | null;
  error: string | null;
  remotes: RepoRemote[];
  publication: "local_only" | "remote_no_upstream" | "tracking" | null;
  remote_view_as_of: string | null;
  remote_stale: boolean;
  sync: RepoSync | null;
  exposure: RepoExposure | null;
  registry: RepoRegistryEntry | null;
  missing?: boolean;
}

export interface ReposPayload {
  repos: RepoSummary[];
  captured_at: string;
}

export interface RepoFileStat {
  path: string;
  insertions: number | null;
  deletions: number | null;
  is_binary: boolean;
}

export interface RepoBranchDetail {
  name: string;
  upstream: string | null;
  ahead: number | null;
  behind: number | null;
  unpushed_commits: number;
  oldest_unpushed_at: string | null;
  contained_in_default: boolean | null;
}

export interface RepoWorktreeRow {
  path: string;
  head: string;
  branch: string | null;
}

/** GET /api/repos/<id>/status: the summary fields plus
 * the stacked groups, commits, branches, worktrees. */
export interface RepoStatusPayload extends RepoSummary {
  staged: RepoFileStat[];
  unstaged: RepoFileStat[];
  untracked: { path: string }[];
  commits: { hash: string; short: string; subject: string; date: string }[];
  branches: string[];
  branch_details: RepoBranchDetail[];
  default_branch: string | null;
  worktrees: RepoWorktreeRow[];
  captured_at: string;
}

/** One file of the full-tree enumeration (files?all=1):
 * git's own classification of the path. */
export interface RepoTreeEntry {
  path: string;
  kind: "tracked" | "untracked" | "ignored";
  hidden: boolean;
}

/** One folder of the tree skeleton: `collapsed` folders
 * (prune-list directories) carry no children in the
 * enumeration. */
export interface RepoTreeFolder {
  path: string;
  hidden: boolean;
  collapsed: boolean;
}

export interface RepoFilesPayload {
  tracked: string[];
  untracked: string[];
  captured_at: string;
  entries?: RepoTreeEntry[];
  folders?: RepoTreeFolder[];
  all_truncated?: boolean;
}

/** One directory of the lazy Files tree (files?dir=):
 * the files directly in `dir` plus its immediate
 * subfolders — the tree fetches a folder's listing only
 * when the folder is first expanded. `truncated` means
 * this one directory's listing hit its cap. */
export interface RepoDirListing {
  dir: string;
  entries: RepoTreeEntry[];
  folders: RepoTreeFolder[];
  truncated: boolean;
  captured_at: string;
}

/** GET /api/repos/<id>/file — the repo peek (lib/files.py):
 * content under the peek caps, binary as metadata only,
 * secret-shaped withheld until revealed, the diff against
 * HEAD as a raw unified-diff string (null = no changes),
 * the sha, and the editability verdict. */
export interface RepoPeek {
  path: string;
  size_bytes: number;
  is_binary: boolean;
  withheld: "secret" | null;
  content: string | null;
  diff: string | null;
  sha256: string | null;
  editable: boolean;
  editable_reason: string | null;
  line_count?: number;
  truncated?: boolean;
  /** Present (true) when a secret-shaped file was served
   * under an explicit reveal. Revealed content is never
   * cached client-side. */
  revealed?: boolean;
  /** The dataset descriptor (lib/files.py) when the file
   * is a dataset kind the Table view can open; null (or
   * absent) otherwise — secret-shaped files never carry
   * one, so a table is never offered for them. */
  dataset?: DatasetDescriptor | null;
  captured_at?: string;
}

/** The repo save's success payload (lib/files.py). */
export interface RepoSaveResult {
  path: string;
  sha256: string;
  size_bytes: number;
  backup: string;
}

export interface RepoHistoryRecord {
  at: string;
  repo: string;
  head: string | null;
  head_subject: string | null;
  branch: string | null;
  ahead: number | null;
  publication: string | null;
  dirty_total: number;
  exposure_level: string | null;
  exposed_commits: number | null;
}

export interface RepoHistoryPayload {
  records: RepoHistoryRecord[];
  timeline: { ts: string; head: string; branch: string | null }[];
  dirty_since: string | null;
  ahead_since: string | null;
}

export interface ReposRegistryPayload {
  repos: Record<string, RepoRegistryEntry>;
  captured_at: string;
}

// ---------------------------------------------------------------------------
// Dataset payloads (datasets plan, steps 5-6): the shapes
// of lib/datasets.py + lib/dataset_console.py behind
// /api/repos/<id>/dataset*. Cell values ride the modules'
// JSON-safe mapping: blobs arrive as null, dates and
// datetimes as ISO strings, decimals as exact strings,
// lists and objects mapped recursively.
// ---------------------------------------------------------------------------

/** The peek's dataset descriptor: the kind plus, for the
 * database kinds (sqlite, duckdb) only, the table names —
 * the Table view's picker input. */
export interface DatasetDescriptor {
  kind: string;
  tables?: string[];
}

export interface DatasetColumn {
  name: string;
  type: string;
}

export interface DatasetTable {
  name: string;
  columns: DatasetColumn[];
}

/** GET /api/repos/<id>/dataset — the described schema,
 * for every table of the file. */
export interface DatasetSchema {
  kind: string;
  tables: DatasetTable[];
}

/** One dataset cell after the JSON-safe mapping. */
export type DatasetCell =
  | string
  | number
  | boolean
  | null
  | DatasetCell[]
  | { [key: string]: DatasetCell };

/** GET /api/repos/<id>/dataset/rows — one bounded page:
 * `columns` is the column names in row order (the types
 * ride the schema), `rows` the value arrays parallel to
 * it, `has_more` honest about a further page. */
export interface DatasetRowsPage {
  columns: string[];
  rows: DatasetCell[][];
  has_more: boolean;
}

export interface DatasetColumnStats {
  name: string;
  null_count: number | null;
  approx_distinct: number | null;
}

/** GET /api/repos/<id>/dataset/stats — computed on
 * demand only. There is no min/max: the derivation does
 * not compute them. */
export interface DatasetStats {
  approx_rows: number;
  columns: DatasetColumnStats[];
}

/** POST /api/repos/<id>/dataset/sql — one guarded read;
 * `columns` is the result column names, `truncated`
 * marks a hit of the console's row/payload caps. */
export interface DatasetSqlResult {
  columns: string[];
  rows: DatasetCell[][];
  truncated: boolean;
}

/** One rows-page filter (the JSON array member the rows
 * endpoint validates against the schema). */
export interface DatasetFilter {
  column: string;
  op: "eq" | "ne" | "lt" | "le" | "gt" | "ge" | "contains";
  value: string;
}
