# Architecture Context

## Stack

| Layer    | Technology                              | Role |
| -------- | --------------------------------------- | ---- |
| Core     | Python 3.11, stdlib only                | `lib/` — sweep, registry, todos, plan parser, validators, staleness |
| CLI      | Python (argparse), thin caller          | `wb` — every verb is a lib/ call |
| Server   | Python stdlib `http.server`, loopback   | Feeds + guarded writes; holds **no SQL** |
| Artifact | TypeScript space (client + actions + privileged raw-socket bridge) | The one viewer UI — concrete frontend dependencies OPEN (see below) |
| Storage  | SQLite (stdlib `sqlite3`), one DB per project | Registry + todos, in the project's own repo |
| Supervision | systemd unit + watchdog + healthcheck cron | Always-on server |

## System Boundaries

- `lib/` — the harness core. Owns ALL SQL, the sweep, manifest
  parsing, mutations, history, export/rebuild, validators,
  staleness, and the plan parser. Stdlib only; every function
  takes explicit paths so tests run on temp fixtures.
- `wb` — the CLI. A caller over lib/; no logic of its own.
- `server/` — the companion server. HTTP layer only: routes,
  feeds assembled from lib/ reads, guarded file saves, and
  mutation endpoints that delegate to lib/. Never grows its
  own SQL — if a write is missing, it is added to lib/ first.
- `viewer/` — the artifact source (canonical here; deployed to
  the runtime tree by `viewer.sh`, published by the builder).
  A client of the server over a raw `node:net` socket (the
  hosting daemon's egress proxy breaks loopback fetch — the
  git repo viewer's documented trap). Its internal layout is
  NOT decided here — it follows the approved fundamentals
  (below).
- **OPEN — frontend fundamentals (the owner, 2026-10-25):** the
  viewer's theme/tokens/fonts, styling approach, concrete
  frontend dependencies (framework libraries, markdown
  renderer, Mermaid packaging), and `viewer/` internal layout
  are being designed separately and require the owner's approval
  before any viewer build. The plan-level constraints that DO
  bind: the artifact is one self-contained bundle (nothing
  fetched from a CDN at runtime) and reaches the server only
  through the raw-socket bridge. Steps 5–6 are held until the
  approved fundamentals land; `context/ui-context.md` is a
  placeholder until then.
- `ops/` — systemd unit template, installer, watchdog,
  healthcheck.
- Project repos (external) — own their data: `workbench.yaml`
  manifest (tracked), registry DB + entries + archive
  (untracked). This repo never writes project code, only
  project workbench data, and only through lib/ mutations or
  the guarded save.

## Discovery: sweep + manifest (spec'd before code)

**Sweep config** (server `config.json`, env `WB_VIEWER_*`
wins over file wins over defaults — one settings seam):

| Key | Default | Meaning |
| --- | ------- | ------- |
| `host` / `port` | `127.0.0.1` / `8792` | bind (8791 is the git viewer's) |
| `workspace_root` | null → parent of this repo | derivation base |
| `sweep_roots` | null → `[workspace_root]` | roots to walk |
| `sweep_manifest` | `workbench.yaml` | manifest filename |
| `sweep_max_depth` | 3 | depth bound under each root |
| `sweep_prune` | `.git`, `.venv`, `.venv311`, `node_modules`, `__pycache__`, `var`, `.artifacts` | never entered |
| `sweep_ttl_s` | 15 | sweep result cache |
| `file_editing_enabled` | `false` | guarded file saves |
| `peek_max_bytes` / `peek_max_lines` | 204800 / 2000 | peek + save caps |
| `feed_lock_timeout_ms` | 250 | per-project feed lock budget |
| `state_dir` | `state` | lock, logs, edit backups |

Sweep mechanics: walk each root to bounded depth; a directory
containing the manifest file at its top level IS a project —
record it and never descend into it. Pruned names are never
entered. Runs at server start and on explicit rescan
(`POST /projects/rescan`, `wb projects --rescan`). No
filesystem watcher in v1.

**Manifest format** (`workbench.yaml`, restricted YAML
subset): flat `key: value` lines; `#` starts a comment; blank
lines ignored; values are plain scalars (no quotes needed, no
nesting, no lists, no anchors). Unknown keys are a hard parse
error. Keys:

| Key | Required | Meaning |
| --- | -------- | ------- |
| `name` | yes | display name |
| `slug` | no | URL/id slug; default: directory name |
| `registry` | no | registry DB path (Mockups + Todos live here) |
| `plans` | no | plan-files directory (Plans + Board) |
| `mockups` | no | entries dir; default: `entries` beside the registry |
| `archive` | no | archive dir; default: `archive` beside the registry |

All paths are relative to the repo root and must not escape
it. Absent `registry` → no Mockups/Todos sections; absent
`plans` → no Plans section. Paper exercise against
example-project (2026-10-25): its real layout is
`registry: workbench/registry.db` (to be created by Part A),
`plans: .plans` (present, 11 plan files; `finished/` does not
exist yet — a missing finished dir is an empty plan archive,
correct degradation), `mockups: workbench/entries`,
`archive: workbench/archive` — the fields suffice; nothing
v2-specific leaks into the format (the same shape describes
this repo with different values).

## Storage Model

- **Per-project SQLite registry** (`registry.db`): mockup
  entries, append-only history, review log (history rows),
  todos + todo events. Discipline borrowed from the prototype
  calendar store: schema via `PRAGMA user_version` migrations,
  WAL + `busy_timeout` on every connection, ONE short
  `BEGIN IMMEDIATE` per mutation, per-row `version`
  compare-and-swap (a stale version fails naming the newer
  state). Every function takes an explicit db path.
- **`registry.json`** beside each DB: a generated canonical
  fold of the DB (entries + history + todos, sorted keys),
  stamped with its computation time and per-entry derived
  staleness. Never hand-edited; `wb rebuild` reconstructs the
  DB from it losslessly.
- **Mock files stay files**: one folder per entry under the
  project's entries dir; the DB holds metadata, pointers, the
  main-file fingerprint (`content_sha256`), the declared
  state schema, and the current internal state — never blobs.
- **Server state** (`state/` here): instance lock, logs,
  one-generation edit backups, health file. Runtime only.

### Registry schema (user_version 1)

`entries` — per subplan 09 (`id` slug PK, `title`, `kind`,
`status`, `gate`, `ruling_text`, `ruling_date`, `spec_ref`,
`plan_ref`, `source_kind`, `source_ref`, `entry_dir`,
`content_sha256`, `config_path`, `created_at`, `updated_at`,
`status_changed_at`, `last_verified_at`, `archived`,
`archived_at`, `superseded_by`, `version`), plus three columns
the review design requires: `main_file` (the file the
fingerprint covers), `state_schema` (JSON, declared internal
state), `state_json` (JSON, current internal state).

`history` — append-only: `id`, `entry_id`, `ts`, `actor`
(`cli` | `viewer` | `stale-check`), `verb`, `field`, `old`,
`new`, `note`. Review dispositions are history rows
(verb `review`, `new` = JSON `{disposition, comment?,
state_sha256?}`); an approval's state snapshot rides in that
row, and approval coverage is derived from the latest one.

`todos` — `id` slug PK, `title`, `status` (`todo` | `doing` |
`done`), `notes`, `link_kind` (`plan` | `step` | `entry` |
null), `link_ref`, `created_at`, `updated_at`, `version`.
`todo_events` mirrors `history` for todos (subplan 09's schema
predates todos; same shape, separate table, so entry history
stays entry-pure).

## Server API (feeds the artifact consumes)

`GET /health` · `GET /config` · `GET /projects` ·
`POST /projects/rescan` · `GET /projects/<slug>/mockups`
(`?archived=1`) · `GET /projects/<slug>/entries/<id>` ·
`GET|POST /projects/<slug>/entries/<id>/file` ·
`POST /projects/<slug>/entries/<id>/action`
(`{verb, ...}` → lib/ mutation, actor=viewer) ·
`GET /projects/<slug>/plans` · `GET /projects/<slug>/plan?path=` ·
`GET /projects/<slug>/todos` · `GET /todos` ·
`POST /projects/<slug>/todos` (`{verb, ...}`) · `GET /board`.

Per-project failure containment: every project feed is built
independently; a locked or broken DB degrades only that
project's payload (`degraded: true` + reason), never the
request. Feeds read with a short lock timeout; mutations use
the normal one.

## Invariants

1. One mutation path: CLI and server write only through lib/.
2. The server contains no SQL.
3. Ruled status changes only with a ruling note; canonical and
   hard-gate transitions additionally require the ruling /
   gate name at the lib/ level, whoever the caller is.
4. Staleness is derived at read time; nothing automatic ever
   writes it, clears it, or changes a ruling.
5. A mockup failing uniformity validators cannot transition
   to canonical — the approve/set-status path runs them.
6. Approval binds to the state snapshot; state edits after
   approval derive a visible "not covered" flag.
7. Data never migrates into this repo; projects never import
   the viewer; the viewer never imports project code.
8. another-project is never a project.
9. The parser never drops plan content: unstructureable
   regions pass through as markdown blocks, flagged.
