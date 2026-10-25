# Workbench Viewer — SPEC

Status: **APPROVED** (the owner, 2026-10-25 — the remaining
open questions resolved from the monitor repo's hard
lessons; see §13). The fundamentals (§11) are APPROVED
(2026-10-25, with the owner's multi-theme + themes-folder
amendments) and wired in. This file is TRACKED in the
viewer repo (§13, resolution 6).

This is the viewer's own spec sheet. The viewer is a generic
harness for every project repo in this workspace; this spec
covers the harness alone. It is NOT tied to any adopting
project's spec: in particular, `example-project/SPEC.md`
specifies that project's pay-monitor application and dashboard
and says nothing about this harness, and this spec says
nothing about any project's application, data, or dashboard.
An adopting project's spec is that project's own durable
record — a mockup that lands in a project amends THAT
project's spec (see §9), never this one.

Sources this draft is drawn from (all 2026-10-25, the owner's
rulings): the founding plan
(`../.plans/2026-10-25-workbench-viewer-repo.md`),
the workbench data model in example-project subplan 09
Part B (inherited, generalized multi-project), this repo's
`context/architecture.md`, `context/project-overview.md`,
`README.md`, and the implementation as built (founding-plan
Steps 1–2 committed, Step 3 in progress at drafting time).
Where this spec and a context file disagree, the approved
version of this spec is normative for product behaviour and
the context file is updated to match.

## 0. Purpose and scope

A project accumulates scattered mockup artifacts, plan files,
and loose to-dos until nobody can say which mockup is
canonical, which plan is in flight, or what is blocked. The
Workbench Viewer fixes that by structure: one always-on
companion server reads every opt-in project's own data files
and serves ONE artifact with four sections — **Mockups,
Plans, Todos, Board**.

Goals:

1. Any question of the form "which mockup is canonical,
   what's deferred, what's stale, what's a hard gate — in
   any project" is answerable from the viewer alone.
2. Adoption cost for a new repo is one tracked file
   (`workbench.yaml`) and zero code.
3. Mockup review happens in the viewer, with a comment log,
   so design feedback never travels as chat paste-back.
4. Plans read better in the viewer than as raw files:
   formatted, structured, with diagrams drawn.

In scope: the harness — `lib/`, the `wb` CLI, the companion
server, and the artifact — and the data contract it reads
from adopting projects.

Out of scope:

- Any project's application data: no pay figures, no repo
  browsing (that is the git repo viewer's job), no project
  dashboards. The four sections are the boundary — the
  viewer renders work and design state, never project data.
- **another-project is excluded by design** — its own maintenance
  system, external to this workspace; never registered,
  never retrofitted; its absence is not an omission.
- Scheduling: the harness emits job definitions
  (`wb print-schedule`); running them is a platform concern.
- Tracked goals: they stay in the Goals tab and are not
  mirrored onto the board.

## 1. Invariants

These hold for every component, every caller, and every
project. A change that breaks one is a defect, not a design
choice.

1. **One mutation path.** All registry and todo writes go
   through `lib/`. The `wb` CLI and the server call the same
   lib functions; the server contains **no SQL**. Hand-
   editing a project's `registry.db` or generated
   `registry.json` is a process violation.
2. **Ruled status, derived staleness.** A mockup's `status`
   changes only via a mutation carrying a ruling note.
   Staleness is computed at read time (age, days since
   verified, content drift), shown as a badge beside the
   status, and is never a status and never overwrites a
   ruling. Nothing automatic clears a stale flag; only
   `wb verify` does.
3. **Approval binds to state.** Approving a mockup records
   the internal-state snapshot it covered (values + hash).
   A later state change derives a visible "not covered"
   flag until re-approval; an approval is never silently
   extended to a state it did not cover.
4. **Overlay rule.** Project repos never depend on the
   harness: they build, test, and run with the viewer
   absent. The viewer never imports project code; it reads
   project *data files* only. If a project ever NEEDS the
   viewer, that is a defect in the project.
5. **Data never migrates.** Project data (registry DB,
   entries, archive) stays in the project repo that owns
   it. This repo holds tooling only, plus its own
   project-zero data under `workbench/` (untracked, like
   every project's).
6. **The board is a view.** It derives from todos, plan
   headers, and the review queue. It is never a fourth
   store, and plan steps / todos are never copied into one
   another's stores.
7. **The parser never drops content.** A plan region the
   parser cannot structure passes through as a markdown
   block, flagged as source format (§8.2).
8. **Self-contained artifact.** Everything the artifact
   needs ships with its build; nothing is fetched from a
   CDN at runtime.
9. **Server write surface is exactly two things:** guarded
   file saves (sha-checked, config-gated, default OFF) and
   lib/ mutation endpoints. Nothing else writes.
10. **Deploy/publish stays a platform step on the owner's
    verbatim word.** Editing data in the viewer is the owner's
    direct action at his own keyboard and is recorded as
    such; it is not publishing.
11. **One schema, every repo (the owner, 2026-10-25).** Every
    adopting repo's registry DB carries the SAME schema
    (§4, §14): one schema definition, one `user_version`
    lineage, owned by lib/. No per-project schema forks or
    extensions. Project specificity lives in row values,
    declared state schemas, references, and files — never
    in new tables or columns. This is what makes the
    interactivity in §14 uniform: the same gestures, verbs,
    and refusals work identically against any repo.

## 2. Adoption contract — the manifest

A project participates by carrying ONE tracked file at its
repo root, `workbench.yaml`. That file is the project's
whole adoption cost and the only tracked trace that it
participates.

Format: a restricted YAML subset — flat `key: value` lines,
`#` comments, blank lines ignored; plain scalars only (no
nesting, no lists, no anchors). Unknown keys are a hard
parse error, so typos surface instead of silently doing
nothing. All paths are relative to the repo root and must
not escape it.

| Key        | Required | Meaning |
| ---------- | -------- | ------- |
| `name`     | yes | Display name |
| `slug`     | no  | URL/id slug; default: directory name |
| `registry` | no  | Registry DB path — Mockups + Todos live here |
| `plans`    | no  | Plan-files directory — Plans + Board |
| `mockups`  | no  | Entries dir; default: `entries` beside the registry |
| `archive`  | no  | Archive dir; default: `archive` beside the registry |

Sections degrade independently: absent `registry` → no
Mockups/Todos for that project; absent `plans` → no Plans;
a missing `finished/` subdir is an empty plan archive, not
an error. No manifest = invisible to the sweep (opt-in by
layout). Removing the manifest, or the root from the sweep
config, un-discovers the project and changes nothing in it.

The project's data — registry DB, the generated
`registry.json` beside it, `entries/`, `archive/` — is
**untracked** in the project repo (gitignored). Mockups are
transient workspace material; the durable record of a landed
design is the project's own SPEC/plan amendment (§9), never
the registry.

Creating the registry is the project's step, when it wants
Mockups/Todos: `wb --project <slug> init` (or the first
`wb add` creates it).

## 3. Discovery — the sweep

Discovery is a config-driven sweep. No per-repo path is ever
hardcoded in the viewer.

Sweep mechanics:

- The sweep walks each configured root to a bounded depth.
  A directory containing the manifest file at its top level
  IS a project: it is recorded and never descended into.
- Pruned names are never entered (default prune list in
  the config table below).
- The sweep runs at server start and on explicit rescan
  (`POST /projects/rescan`, `wb projects --rescan`). There
  is **no filesystem watcher in v1**.
- Sweep results are cached for `sweep_ttl_s`.

Server configuration is one seam — env (`WB_VIEWER_*`) wins
over the config file (`config.json`) wins over defaults:

| Key | Default | Meaning |
| --- | ------- | ------- |
| `host` / `port` | `127.0.0.1` / `8792` | Bind (8791 is the git viewer's) |
| `workspace_root` | null → parent of this repo | Derivation base |
| `sweep_roots` | null → `[workspace_root]` | Roots to walk |
| `sweep_manifest` | `workbench.yaml` | Manifest filename |
| `sweep_max_depth` | 3 | Depth bound under each root |
| `sweep_prune` | `.git`, `.venv`, `.venv311`, `node_modules`, `__pycache__`, `var`, `.artifacts` | Never entered |
| `sweep_ttl_s` | 15 | Sweep result cache |
| `file_editing_enabled` | `false` | Guarded file saves |
| `peek_max_bytes` / `peek_max_lines` | 204800 / 2000 | Peek + save caps |
| `feed_lock_timeout_ms` | 250 | Per-project feed lock budget |
| `state_dir` | `state` | Lock, logs, edit backups |

`GET /health` reports the resolved config (with hash) and
the last sweep's project list, and `GET /config` the resolved
config — "why doesn't it see my repo?" is answered from the
server, not from guesswork.

## 4. Registry — the per-project data model

Each project owns ONE SQLite registry DB, at the path its
manifest declares — and every such DB, in every adopting
repo, carries the identical unified schema defined below
(§1.11, §14): the schema in this section is not a template
each project adapts; it is the one schema lib/ creates and
migrates everywhere. Scope note: the unified schema is the
*workbench registry* schema only. A project's own
application databases, if it has any, are that project's
internal business — the viewer never reads them, and they
are not part of this spec.

Storage discipline (borrowed from proven
stores in this workspace): schema via `PRAGMA user_version`
migrations; WAL + `busy_timeout` on every connection; ONE
short `BEGIN IMMEDIATE` transaction per mutation; per-row
`version` compare-and-swap — a stale version fails naming
the newer state, never a silent overwrite. Stdlib `sqlite3`
only. Every lib function takes an explicit db path, so tests
run on temp fixtures and no caller depends on ambient state.

### 4.1 `entries` — one row per mockup

(schema `user_version` 1)

- `id` — slug, primary key; also the folder name under the
  entries or archive dir. Slugs are stable identity; titles
  are display only.
- `title`; `kind` (`mockup` | `prototype` | `test-route` |
  `component-variant` | `storyboard`).
- `status` — the RULED status (§5); `gate` — for hard-gate
  entries, the named blocker.
- `ruling_text`, `ruling_date` — the ruling, in brief
  (verbatim where short), and when.
- `spec_ref`, `plan_ref` — cross-references into the owning
  project's own spec/plans.
- `source_kind` (`entry-dir` | `artifact-slug` |
  `external`), `source_ref` — where the mock lives if not a
  local folder.
- `entry_dir` — current relative path; the row and the
  folder move together, in the archive operation.
- `main_file` — the file the fingerprint covers.
- `content_sha256` — fingerprint of the entry's main file;
  cheap to recompute; detects silent drift of the file under
  its metadata.
- `config_path` — optional per-entry config file inside the
  entry dir, editable through the same guarded save as the
  mock file itself.
- `state_schema` (JSON) — the entry's declared internal
  state (§8.1); `state_json` (JSON) — its current values.
- `created_at`, `updated_at`, `status_changed_at`,
  `last_verified_at` — timestamps (UTC ISO-8601); staleness
  math reads these.
- `archived` (0/1), `archived_at` — archive is an orthogonal
  flag, NOT a status: an archived canonical is still
  canonical, just not in the active tree.
- `superseded_by` → `entries.id` — the variant-chain link.
- `version` — CAS counter, bumped on every mutation.

Mock files stay files: one folder per entry under the
project's entries dir. The DB holds metadata, pointers, the
fingerprint, and the declared/current state — never blobs.

### 4.2 `history` — append-only audit + review log

`id`, `entry_id`, `ts`, `actor` (`cli` | `viewer` |
`stale-check`), `verb`, `field`, `old`, `new`, `note`.
Every mutation appends its event; nothing is ever updated
or deleted here. This log answers "when did this stop being
canonical, and who said so?"

Review dispositions are history rows (verb `review`,
`new` = JSON `{disposition, comment?, state_sha256?}`); an
approval's state snapshot rides in that row, and approval
coverage (§1.3) is derived from the latest approval row.
Review comments live in the same append-only log — the
triage trail travels with the entry, never as chat
paste-back.

### 4.3 `todos` + `todo_events`

Todos live in the same per-project DB, in their own tables
(one store per project, separate tables, so entry history
stays entry-pure).

`todos`: `id` slug PK, `title`, `status` (`todo` | `doing`
| `done`), `notes`, `link_kind` (`plan` | `step` | `entry`
| null), `link_ref`, `created_at`, `updated_at`, `version`.
A todo may link to a plan, a step, or a mockup entry; a link
is a reference, never a copy. `todo_events` mirrors
`history` for todos, with the same shape.

### 4.4 `registry.json` — generated export

Beside each DB sits `registry.json`: a generated canonical
fold of the DB (entries + history + todos, sorted keys),
stamped with its computation time and per-entry derived
staleness. Never hand-edited; never a second source of
truth. Every mutation regenerates it. `wb rebuild`
reconstructs the DB from it losslessly — the fresh-clone /
disaster path, and the standing proof the export is
lossless.

### 4.5 Archive mechanics

`wb archive` does, in order: (1) move `entries/<slug>/` →
`archive/<yyyy>/<slug>/` (year bucket, so the archive never
goes flat either); (2) in one `BEGIN IMMEDIATE` transaction
set `archived=1`, `archived_at`, `entry_dir`, bump
`version`, append the history row; (3) regenerate the
export. If (2) fails after (1), the row still points at the
old path and `wb validate` reports the mismatch as a
finding with its repair (`wb archive --resume` completes
the row update) — the failure is loud, never silent.
`wb unarchive` reverses it. The viewer defaults to the
active set; the archive sits behind a toggle, searchable
like everything else.

## 5. Status model — ruled vs derived

### 5.1 Ruled status vocabulary (fixed)

| Status | Meaning |
| ------ | ------- |
| `canonical` | Approved design intent — an approved mock is an exact spec |
| `implemented` | Canonical, now built in the owning project |
| `deferred` | Ruled: later |
| `unexplored` | Experiment; no ruling; NOT design intent |
| `hard-gate` | Blocked on the named `gate` |
| `abandoned` | Superseded or dead; kept for history; never resurrected silently |

Rules:

- A status changes only through a mutation carrying a
  ruling note. `canonical` and `hard-gate` transitions
  additionally require the ruling / gate name at the lib
  level, whoever the caller is.
- "Active" = the non-archived set (any ruled status,
  `archived=0`). Archive is orthogonal (§4.5).
- "Superseded" = `abandoned` WITH `superseded_by` set; the
  link is what distinguishes superseded from merely dead.
- "Stale" is NOT in this vocabulary (§5.2).

### 5.2 Derived staleness

Computed at read time (viewer, `wb stale`, export) from:
`age_days` = now − `created_at`; `days_since_verified` =
now − `last_verified_at`; `drift` = `content_sha256` ≠
current file hash (the file changed after its metadata was
last verified — a stronger signal than age).

Per-status thresholds decide the verdict. Built-in defaults
(as implemented): `unexplored` unverified > 30 days → "may
be stale"; `canonical`, `deferred`, `hard-gate` unverified
> 90 days → "verification due"; `implemented` and
`abandoned` never stale-flag (their truth lives in the built
project / history). Thresholds are overridable per project
via a `thresholds.json` beside the registry DB, read
through lib/.

A stale flag is a prompt for a verify action — `wb verify`
re-fingerprints the entry and, when the hash matches (or the
drift is accepted), sets `last_verified_at` = now. That is
the ONLY thing that clears a flag. `wb stale` is read-only
against ruled data: it may append a check-run record to
history (actor `stale-check`, no field changes) and must
never change status, `last_verified_at`, or any ruling.

## 6. The `wb` CLI

`wb` is a thin caller over lib/ (argparse verb subcommands);
it has no logic of its own. Project selection:
`wb --project <slug> <verb>`, or the project is inferred
from the working directory's `workbench.yaml`.

Entry verbs: `projects` (list what the sweep finds;
`--rescan` forces a sweep), `init`, `add`, `list`, `show`,
`set`, `set-status`, `supersede`, `verify`, `archive`,
`unarchive`, `stale`, `validate`, `export`, `rebuild`,
`set-state-schema`, `set-state`, `review`.

Todo verbs: `todo-add`, `todo-list`, `todo-set-status`,
`todo-set`.

Plus `print-schedule` — emits the staleness-check job
definition for a platform scheduler, IF one is later ruled;
the harness builds the tool, not the schedule.

Semantics that bind every verb:

- `add <slug>` creates the entry dir + row; status starts
  `unexplored` unless `--status` + `--ruling` are given.
- `set-status <id> <status> --ruling "…"` — ruled
  transitions; canonical / hard-gate require the ruling
  note / gate name; the approve / set-status path runs the
  uniformity validators (§10) — a failing entry cannot
  transition to canonical.
- `supersede <old> <new>` is ONE operation: old gets
  `superseded_by` = new and status → `abandoned`, with
  `status_changed_at` + history rows on both entries.
- `set --expect-version` performs the per-row CAS (§4).
- `validate` runs the validator registry (§10); nonzero
  exit on any finding.
- Every mutation regenerates `registry.json` (§4.4).

## 7. The companion server

One server per workspace — not one per project. Stdlib
Python (`http.server`), loopback only, binds per the config
seam (§3; default 127.0.0.1:8792). Always on, supervised:
systemd unit + watchdog + healthcheck (git-viewer pattern).
The server's job is nearly free — it serves the artifact's
feeds — so there is no cold start to pay per use.

The server is an HTTP layer only: routes, feeds assembled
from lib/ reads, guarded file saves, and mutation endpoints
that delegate to lib/. If a write is missing, it is added
to lib/ first (§1.1).

API (the feeds the artifact consumes):

- `GET /health` · `GET /config` · `GET /projects` ·
  `POST /projects/rescan`
- `GET /projects/<slug>/mockups` (`?archived=1`) ·
  `GET /projects/<slug>/entries/<id>` ·
  `GET|POST /projects/<slug>/entries/<id>/file` ·
  `POST /projects/<slug>/entries/<id>/action`
  (`{verb, ...}` → lib/ mutation, actor=viewer)
- `GET /projects/<slug>/plans` ·
  `GET /projects/<slug>/plan?path=`
- `GET /projects/<slug>/todos` · `GET /todos` ·
  `POST /projects/<slug>/todos` (`{verb, ...}`)
- `GET /board`

Conventions: request input is validated and parsed before
any logic runs. Success payloads carry `captured_at`;
failures are `{error}` with these status conventions:
400 bad input, 404 unknown project / entry, 409 stale sha
or version, 403 editing disabled / secret path, 413 over
caps.

Per-project failure containment: every project feed is
built independently; a locked or broken DB degrades only
that project's payload (`degraded: true` + reason), never
the request. Feeds read with a short lock timeout
(`feed_lock_timeout_ms`); mutations use the normal one.
Server state (`state/` in this repo) is runtime only:
instance lock, logs, one-generation edit backups, health
file.

Reconciliation: on serve, the server reconciles DB rows
against the entries/ + archive/ trees — a folder with no
row, or a row whose folder is gone, surfaces as a viewer
banner + a `wb validate` finding, guarded so a transient
scan failure reports "unknown", never mass-flags.

### 7.1 Guarded file saves (git-viewer v2.1 mechanics)

- Behind `file_editing_enabled`, default OFF — a fresh
  deployment is read-only.
- A peek returns content + `sha256` + `editable` +
  `editable_reason`; caps (`peek_max_bytes` /
  `peek_max_lines`) apply — an over-cap file is never
  editable.
- A save is a POST carrying the peek's `base_sha256`;
  mismatch answers 409 with the current hash and writes
  nothing.
- Writes are atomic (temp file + `os.replace`, mode
  preserved) with a one-generation backup.
- Secret-shaped paths are refused before existence is
  checked.
- Every save is recorded in the entry's history
  (actor=viewer).

## 8. The artifact — one viewer, four sections

A single self-contained artifact serves every project and
every entry (§1.8). It reaches the server over a raw
`node:net` socket from its privileged handler — the hosting
daemon's egress proxy breaks loopback fetch (the git repo
viewer's documented trap; designed for from day one). The
client never hardcodes the server host/port; they come from
artifact settings. Deploy is a drift-guarded copy from this
repo's `viewer/` (canonical) to the runtime tree, then a
separate builder publish pass (§1.10).

### 8.1 Mockups

Per project: the registry browser — ruled status chip +
derived stale badge per entry, filters, archive behind a
toggle.

Review happens here (§4.2):

- Dispositions: **approve / needs-changes / mark-stale**,
  each with an optional comment, as lib/ mutations
  (actor=viewer) under the same ruling-note discipline as
  the CLI — the viewer collects the note in its confirm
  dialog.
- A **triage lane**: entries awaiting review — unexplored,
  stale-flagged, or needs-changes with unaddressed
  comments — presented as one queue, so a session starts
  from the queue, not from archaeology.
- **Internal state:** each entry declares a state schema
  (toggles, variant selectors, data modes — e.g.
  empty/with-content, density, stacking on/off). The viewer
  renders controls for the declared state; the state is
  edited live, the mock re-renders against it, and only
  then is it approved — approval binds to that snapshot
  (§1.3).

### 8.2 Plans

Each project's plan dir, rendered FORMATTED, not raw
markdown: header (status, parent, rulings) as structured
fields; steps with their files / verify / done-when blocks
rendered as blocks; finished plans (`finished/`) in an
archive view. Raw markdown is one click away (source view)
but never the default.

The server parses a plan into a structured document
(fields, sections, step blocks, mermaid sources); fenced
```mermaid blocks arrive as diagram source and render
client-side — **lazily**, only on pages whose plans contain
diagrams. A diagram that fails to render falls back to its
source as a code block — never a blank hole.

Degradation rule: a plan that does not match the house
format renders whole as formatted markdown; any region the
parser cannot structure passes through as a markdown block,
flagged in the UI as source format (§1.7).

### 8.3 Todos

Per project and cross-project (`GET /todos`). Stored in
each project's registry DB (§4.3), managed by the `wb`
todo verbs and editable in the viewer through the same
lib/ mutation path. Plan steps are NOT todos and are never
copied into the todo store.

### 8.4 Board

A kanban over what is in progress, from exactly three
sources:

- **Todo cards** — columns by todo status (todo / doing /
  done). The ONLY draggable cards: a drag is exactly a
  todo-status mutation, and nothing else.
- **Plan cards** — placed by their plan's header Status
  (draft → To do, in progress → Doing, complete /
  superseded / in `finished/` → Done). They show step
  counts, not step state: per-step state does not exist in
  the house plan format and v1 does not invent it (a
  step-marker convention is a future extension, out of
  scope). Derived — read-only on the board.
- **Review queue** — mockups awaiting disposition (§8.1),
  as their own lane. Derived — read-only on the board.

Acting on a derived card opens its source (the plan, the
review item), where the action lives. The board shows no
card whose source record does not exist (§1.6).

## 9. Mockup authoring + promotion

Uniformity is an authoring discipline, checked by
validators (§10): every mockup renders inside the standard
frame; uses the shared kit and theme tokens only (no
private styling systems); declares its internal state in
the standard schema form; exposes variants as state, never
as duplicate files; and keeps explanatory prose out of
exhibits (titles, labels, data, section headers only —
explanation lives in the review/decision record, not the
exhibit).

Promotion path — a mockup becomes a project's built design
only through: status → `canonical` (a ruling) → an
amendment to the OWNING PROJECT's own spec → build in that
project → status `implemented`. No direct copy-paste
promotion skips the owning project's spec. Test routes for
design experiments live in the project's entries dir,
never as routes in the project's production code.

## 10. Validators

Validation is a registry of small validator functions
collected in one `ALL_VALIDATORS` tuple in lib/ — a
registry + `wb validate`, not a second gate program. A
project MAY run `wb validate` as a leg of its own gate;
no project is required to have the viewer installed (§1.4).
Findings fail like any other gate finding.

The v1 registry checks:

- Status vocabulary — every entry's status is in §5.1.
- Supersedes links resolve and are acyclic.
- Archived flag ⇔ folder location agrees (§4.5).
- Content fingerprints match (drift is reported, §5.2).
- Entry dirs all have rows, and rows all have dirs
  (reconciliation, §7).
- Mockup uniformity (§9): state schema declared and
  well-formed, and declared state values conform to it;
  standard frame; kit/token usage only; no variant files;
  no explanatory prose in exhibits.

An entry failing the uniformity validators cannot
transition to canonical — the approve / set-status path
runs them (§6), so a non-uniform mockup cannot be approved
by accident.

## 11. Fundamentals (approved 2026-10-25, with amendments)

Wired in on the owner's approval (2026-10-25) from the
fundamentals proposal
(`../.plans/2026-10-25-workbench-viewer-fundamentals.md`),
which is the normative detail source for full token tables,
contrast ratios, and rationale; this section records the
fundamentals as spec. Two amendments are the owner's, made at
approval: **multiple themes, not just green** (§11.1), and
the **themes-folder CSS organization** (§11.2). The
proposal's defaults on font (§11.3) and default theme mode
(§11.1) are wired in as proposed and remain flippable by
ruling; the product name remains the working name
`workbench-viewer`.

### 11.1 Theme system — modes × palettes

- **Modes:** dark (design-led) + light (full peer), both
  descended from the dashboard classic token sets (dark
  surfaces `#171912 / #21241b / #2a2e21`; light `#edeee3 /
  #f7f7ee / #e4e5d3`). Default follows the OS, with an
  in-app Auto / Dark / Light toggle persisted as a UI
  preference. Mockup preview wells carry their own
  light/dark toggle per frame — a mock is judged in the
  mode it was designed in.
- **Palettes (the owner's amendment):** the viewer provides
  DIFFERENT THEMES, not just the olive/green one. A palette
  theme is a selectable token-set variant over the same
  semantic roles (§11.2): it changes the accent and surface
  family as one coherent set. **Olive is the default
  palette** (`--wb-accent` `#4b5320` light / `#9db45c`
  dark), not the only one; further palettes (e.g. a teal in
  the git viewer's family) are added as theme files under
  the same contract. Switching palettes is a UI preference,
  like the mode.
- **What never varies by palette:** the status system —
  Okabe–Ito hues, one per ruled status, always dot + glyph
  + word (§5.1 must render distinctly in every palette);
  the ruled = filled-chip vs derived = outline-badge shape
  split; and the contrast discipline — every palette must
  pass the same contrast verification in both modes before
  it ships. Danger red is reserved for errors and
  destructive actions in all palettes.

### 11.2 Tokens + themes-folder organization

- Tokens are `--wb-<category>-<role>` CSS custom
  properties in three tiers (primitive → semantic →
  component); source of truth is a DTCG-format
  `tokens/tokens.json`; Style Dictionary is not adopted.
  All components use tokens — no hardcoded values.
- **Organization (the owner, 2026-10-25):** the generated CSS
  ships as a `themes/` folder — an entry CSS file that
  `@import`s one file per palette theme (each scoped to
  its root selector, e.g. `[data-palette="olive"]`, with
  mode variants inside), generated from `tokens.json` and
  checked in, generator in the build. This works in this
  workspace's artifact stack — proven by the git viewer's
  `theme.css` on the same Tailwind v4 build: local
  `@import`s are inlined at BUILD time into the single
  output stylesheet, so the bundle stays self-contained
  (§1.8); `@import`s sit at the top of the entry file;
  fonts are bundled woff2 via local `@font-face`, never a
  URL import; theme switching is selector switching over
  the one shipped bundle — never a runtime stylesheet swap
  or fetch. **Fallback:** if the build proof ever shows
  imports not inlined (or import order breaking the
  Tailwind cascade), the organization reverts to the
  proposal as-is — one generated `theme.css` — with the
  same tokens and the same multi-palette provision.
- Spacing `{4, 8, 12, 16, 24, 32}`; radius 6 (controls),
  10 (cards/frames), 12 (panels/lanes), 9999 (chips).

### 11.3 Typography

Inter (variable, bundled woff2) for UI — tabular figures
for data; IBM Plex Mono (bundled woff2) for codes, slugs,
hashes, paths, timestamps only. House type scale
12 / 14 / 16 / 18 / 20 / 24. Bundled, zero runtime fetch
(§1.8) — loading the fonts from a CDN at runtime is not
permitted in the built viewer, whatever a preview does.

### 11.4 Views, storyboard, flow

Rail + top-bar shell (1600px canvas). Mockups: storyboard
grid, 300px tile minimum, + contact-sheet mode, with the
drill-in (state panel, approval, disposition bar, review
log). Plans: reading view — structured step blocks,
degradation banner for non-conforming plans (§8.2). Todos:
a list. Board: lanes with the Review lane first; only todo
cards draggable (§8.4). Component libraries and Storybook
are not adopted (Storybook's stories/Controls patterns
are); the kit is hand-built from tokens.

React discipline (the owner, 2026-10-25 — the monitor's
standing rules applied to this artifact): **design
fundamentals first** — every component's appearance is
specified per variant × per state (in tokens) before it
is coded, Button's variants (primary / secondary / danger
/ ghost) × states (default / hover / active /
focus-visible / disabled) being the canonical example;
**props contracts** — typed props, data in via props,
events out, components never fetch; **components, not
monoliths** — one component per concept and file, sections
compose the kit and own no private chrome; **buttons from
ONE shared kit**; and **scrollbars are one thin global
rule** in the themes CSS, never styled per-component.

### 11.5 Frontend dependencies + `viewer/` layout

React 19 + Tailwind CSS v4 + `@tanstack/react-query`;
`marked` + DOMPurify (degraded-plan rendering only);
`mermaid` ^11, lazy chunk, `securityLevel: 'strict'`,
token-themed; `highlight.js` lazy for source view, styled
from tokens only. No CSS-in-JS, no component library. The
backend stays Python stdlib (§7). The `viewer/` internal
layout is the fundamentals proposal §9 tree, with §11.2's
`themes/` folder replacing its single generated
`theme.css`.

The two functional constraints from the placeholder era
stand unchanged: each ruled status renders DISTINCTLY and
derived staleness renders as a badge beside the status,
never as a status (§5); and the artifact is fully
self-contained (§1.8).

## 12. Conformance — how each claim is proven

- **Harness core:** lib tests on temp project fixtures —
  two projects side by side, mutations isolated per DB,
  export/rebuild round-trips lossless, a canonical
  transition without a ruling note is refused, the todo
  lifecycle walks clean from the CLI alone.
- **Parser:** round-trips the real plan corpus (the
  founding plan, subplan 09, an adopting project's master
  plan) — every step block lands in the structure, no step
  silently dropped; a mermaid fence yields its diagram
  source intact; a non-conforming plan reconstructs whole.
- **Server:** with two projects registered, every feed
  answers; a locked DB degrades that project's feed only;
  a wrong-sha edit returns 409 and writes nothing; the
  watchdog revives a killed server.
- **Viewer:** a plan with a mermaid diagram renders the
  diagram (not the fence text); a broken diagram shows
  its source block; dragging a todo card performs exactly
  the todo-status mutation; plan and review cards cannot
  be dragged and open their source instead.
- **Overlay:** an adopting project is green with the
  viewer present AND with it absent (founding-plan Step 7
  verifies this both ways, for project zero and for the
  first adopting project).

## 13. Resolved questions (formerly open)

All resolved (the owner, 2026-10-25), each from a hard lesson
in the monitor repo — recorded with its lesson so the
reasoning is not re-litigated:

1. **Name: `workbench-viewer` is FINAL** (repo, artifact
   slug, unit, env prefix). Lesson: the monitor's mocks
   that were renamed or re-slugged late shipped as `-2`
   artifacts with muddied provenance, and a rename left
   open ("System") lingered for days — names lock BEFORE
   publish, and this name is already consistent across
   the repo, server, unit, and config.
2. **Cross-links with the git repo viewer: LINK-ONLY.**
   Separate artifacts, separate servers; at most a link
   each way. Lesson: the monitor consolidated onto ONE
   dashboard and the git viewer onto ONE artifact for all
   repos — surfaces that tried to be two tools became
   neither; each viewer's job stays its own (§0).
3. **Staleness check: NOT scheduled in v1.** `wb
   print-schedule` emits the definition; enabling a
   schedule is a later, explicit ruling. Lesson: the
   monitor's crons that touched shared state (lease TTL,
   cert pickup) each needed their own explicit go, a
   cadence ruling, and a coordination fix — build the
   tool, not the schedule.
4. **Palette #2: TEAL**, descended from the git viewer's
   shipped, verified teal token set — values adapted in
   build Subplan 02 with the same contrast verification,
   not invented fresh. Lesson: the monitor's own theme.css
   already ships multiple themes (classic + launchpad +
   office) built by reusing proven token families; new
   hues are where contrast debt hides.
5. **Lint/format: BIOME adopted** for the viewer (lint +
   format for TS/CSS/JSON, one pinned version, config
   in-repo; build Subplan 03). Lesson: the monitor's
   dashboard drift incidents — a deploy clobbering
   space-side enhancements, builder changes living only
   in the space until a pull — are what a workspace with
   no format/lint standard produces: unreviewable diffs
   and two sources of truth. One pinned formatter makes
   every diff mechanical to review.
6. **This SPEC is TRACKED in the viewer repo.** Lesson
   (the harness rule the monitor program adopted): a
   ruling that lives only in an untracked file does not
   survive a fresh clone — and §2's own logic requires it:
   mockup data is untracked BECAUSE the spec amendment is
   the durable record; a durable record that is itself
   untracked is no record.

Earlier resolutions, recorded so they are not re-opened:
todos live in the registry DB (§4.3); board sources are
exactly the three in §8.4; mockup registry data is
untracked in the adopting project (§2); the server is
always-on (§7); review happens in the viewer (§8.1);
another-project is excluded (§0); fundamentals are approved and
wired in (§11), including multiple palette themes (not
just green) and the themes-folder CSS organization with
its fallback.

## 14. Unified schema + uniform interactivity (all repos)

(Ruled by the owner, 2026-10-25: all repos carry a unified
SQLite schema, and interactivity is uniform across any repo
that adopts the harness — determined here for any repo, not
for one project.)

### 14.1 The unified schema rule

- There is exactly ONE registry schema: the tables in §4
  (`entries`, `history`, `todos`, `todo_events`), defined
  once in lib/ (`SCHEMA_V1` and its successors) and stamped
  with `PRAGMA user_version`. lib/ creates it identically
  in every adopting repo and migrates it in lockstep: a
  schema change is a harness change — a new user_version
  shipped in lib/ and applied to every project's DB by the
  same code path — never a local edit in one repo.
- Any tool built against schema version N (the CLI, the
  server, the viewer, a project's gate leg) works against
  ANY project's DB at version N, unchanged. Cross-project
  feeds (§7) are possible because of this, not despite the
  per-project DBs.
- A need that seems to require a project-specific table or
  column is a design question for THIS spec (does the
  unified schema grow a general column?) — it is never
  resolved by forking one repo's schema. The escape valves
  that already exist are general by design: `kind` values,
  `state_schema` / `state_json` (per-entry declared state,
  §14.4), `spec_ref` / `plan_ref` / link references, and
  files under the entry dir.

### 14.2 The uniformity test

An interaction is UNIFORM — part of this section — if and
only if it can be defined entirely over the harness
contract: the manifest (§2), the unified schema (§4), the
plan files, and the entry files — with no reference to what
the adopting project IS (its domain, its application, its
own data). If an interaction needs project semantics, it
belongs to that project's own application and spec, and it
never appears in the viewer (§0, out of scope).

### 14.3 The uniform interaction catalogue

The same interaction, with the same name, gesture, and
result, in every adopting repo. Channels: **V** = viewer,
**C** = `wb` CLI, **S** = the same lib/ mutation served by
the server (V and S are one path, §1.1).

Discover & orient:

- List the swept projects; switch project context; rescan
  the sweep. **[V/C]**
- Read per-project health: degraded-with-reason when a
  project's DB is locked or broken, healthy otherwise —
  one project's state never masquerades as another's. **[V]**
- Combined cross-project views (todos, board) with the
  project always labeled. **[V]**

Browse & inspect mockups:

- List entries; filter by ruled status, kind, archived,
  staleness, triage reason; open one entry. **[V/C]**
- Read an entry's full append-only history / review log. **[V/C]**
- See, beside every status chip, the derived badges:
  stale verdict with its reason (age / unverified / drift),
  and approval-coverage ("not covered") when the current
  state has outrun its approval. **[V/C]**

Review (the triage workflow):

- Work the triage lane: unexplored + stale-flagged +
  needs-changes-unaddressed, as one queue. **[V]**
- Dispose: approve / needs-changes / mark-stale, each with
  a comment, recorded in the entry's log. **[V/C]**

Lifecycle mutations (all ruling-disciplined):

- Add an entry; edit its settable metadata (title, gate,
  ruling text, spec/plan refs, config/main-file pointers);
  set status WITH a ruling note; supersede (one operation,
  both entries historied); verify (re-fingerprint — the
  only stale-clearing act); archive / unarchive (folder
  move + row update as one operation). **[V/C]**

State interactivity (schema-driven, see §14.4):

- Render an entry's controls FROM its declared
  `state_schema` — toggle, selector, and mode controls are
  generated, never hand-built per entry or per project.
- Edit state live; the entry re-renders against it; the
  approval-coverage badge updates by derivation. **[V/C]**

Files:

- List an entry's files; peek a file (content + sha +
  editable + reason, under the caps); guarded-save a file
  or its config through the sha-checked path, when editing
  is enabled. **[V/C-adjacent: peek/save are lib/ `files`
  functions behind the server + viewer]**

Todos:

- Add; list per project or combined; filter by status;
  edit fields and notes; set status; link to a plan, a
  step, or an entry. **[V/C]**
- On the board, drag a todo card between columns — the
  drag IS the status mutation, with the same history
  record as any other channel. **[V]**

Plans & board:

- List a project's plans (+ finished archive); open a plan
  structured; toggle to source view; diagrams render (with
  source fallback); a non-conforming plan renders whole. **[V]**
- Board placement is identical everywhere because it is
  derived from the same inputs: todo status, plan header
  Status, review queue (§8.4). Derived cards open their
  source; they never accept edits on the board. **[V]**

Integrity (available, and identical, for every repo):

- Staleness report; drift flags; reconciliation banners
  (folder-without-row, row-without-folder); validator
  findings; regenerate the export; rebuild the DB from the
  export. **[V/C]**

Uniform refusals are part of uniform interactivity — the
same "no" everywhere: a canonical / hard-gate transition
without a ruling note / gate name is refused; a uniformity
failure blocks canonical; a stale version or sha answers a
conflict naming the current state and writes nothing; a
secret-shaped or over-cap file is not editable; a locked
DB degrades only its own project's feed.

### 14.4 What varies per project (parameters, not interactions)

These differ between repos WITHOUT creating new
interactions — they are data the uniform interactions run
over:

- Entry content itself (the mock files), entry `kind`, and
  titles/refs (`spec_ref` points into THAT project's spec;
  the gesture of following it is uniform).
- Each entry's declared `state_schema`: the SET of controls
  differs per entry; the control TYPES, their rendering,
  and the edit → re-render → approval-coverage behaviour
  are uniform.
- Per-project staleness thresholds (`thresholds.json`, §5.2):
  values differ; the verdict mechanics do not.
- Which sections a manifest declares (§2): an absent
  section is uniformly absent, never a project-specific
  substitute.

### 14.5 What is NOT uniform (by design)

- Anything defined over a project's own application data or
  domain actions (its records, its computations, its
  workflows): that interactivity belongs to the project's
  own app, under its own spec. The viewer never grows a
  per-project panel, verb, or gesture — a request for one
  is resolved either as a general harness interaction
  (defined over §14.2's contract, added for ALL repos) or
  as out of scope for the viewer.
- Project-zero dogfooding and any single project's
  adoption order create no precedents that bind other
  repos beyond this section.
