# Architecture Context

## Stack

| Layer    | Technology                              | Role |
| -------- | --------------------------------------- | ---- |
| Core     | Python 3.11, stdlib only                | `lib/` — sweep, registry, todos, plan parser, validators, staleness |
| CLI      | Python (argparse), thin caller          | `wb` — every verb is a lib/ call |
| Server   | Python stdlib `http.server`, loopback   | Feeds + guarded writes; holds **no SQL** |
| Artifact | TypeScript space: React 19 + Tailwind CSS v4 (client) + actions + privileged raw-socket bridge | The one viewer UI — frontend fundamentals DECIDED (SPEC §11; frozen layout below) |
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
  git repo viewer's documented trap). Its internal layout
  is frozen below (Target directory layout) — the approved
  fundamentals (SPEC §11) as amended.
- **Frontend fundamentals — DECIDED (the owner, 2026-10-25;
  SPEC §11):** the viewer's theme/tokens/fonts, styling
  approach, concrete frontend dependencies, and `viewer/`
  internal layout are approved and recorded in SPEC §11
  (design record:
  `2026-10-25-workbench-viewer-fundamentals.md`;
  styling reference: `context/ui-context.md`). Theme system
  = modes (dark/light) × palettes (olive DEFAULT; teal is
  palette #2 — SPEC §13 resolution 4); tokens sourced from
  `tokens/tokens.json`; themes-folder CSS organization with
  the single-file fallback (§11.2); Inter + IBM Plex Mono
  bundled; React 19 + Tailwind CSS v4, `@tanstack/react-query`,
  `marked` + DOMPurify (degraded-plan rendering only),
  `mermaid` ^11 lazy, `highlight.js` lazy; Biome lint/format
  (SPEC §13 resolution 5). The plan-level constraints that
  bind: the artifact is one self-contained bundle (nothing
  fetched from a CDN at runtime) and reaches the server only
  through the raw-socket bridge. Founding Steps 5–6 are
  unblocked; they map to build Subplans 06–07 of the viewer
  build program (`.plans/2026-10-25-viewer-build-program.md`).
- `ops/` — systemd unit template, installer, watchdog,
  healthcheck.
- Project repos (external) — own their data: `workbench.yaml`
  manifest (tracked), registry DB + entries + archive
  (untracked). This repo never writes project code, only
  project workbench data, and only through lib/ mutations or
  the guarded save.

## Target directory layout (FROZEN — build Subplan 01, 2026-10-25)

This tree is the single layout reference for the viewer
build program; later subplans cite it, not the fundamentals
file. Backend = AS BUILT (no churn). Frontend = fundamentals
§9 as amended by SPEC §11.2.

```
workbench-viewer/
  AGENTS.md                  entry (Six-File adaptation)
  README.md                  the harness contract
  SPEC.md                    this repo's spec (tracked,
                             APPROVED — §13 resolution 6)
  workbench.yaml             project zero's own manifest
  config.example.json        settings-seam example (actual
                             config.json is untracked)
  viewer.env.example         env-override example (actual
                             viewer.env is untracked)
  viewer.sh                  artifact sync (status|pull|deploy)
  init_venv.py               venv builder (uv, Python 3.11)
  requirements.txt
  run.py                     server entry (binds per config)
  wb                         the CLI: thin caller over lib/
  context/                   project-overview / architecture /
                             ui-context / code-standards /
                             ai-workflow-rules / progress-tracker
  tokens/
    tokens.json              DTCG source of truth for all
                             --wb-* tokens (SPEC §11.2)
  lib/                       Python, stdlib only — AS BUILT
    __init__.py
    registry.py              entries/history/todos schema +
                             the ONE mutation path (CAS,
                             ruling discipline, export fold)
    manifest.py              workbench.yaml restricted-subset
                             parsing/validation
    sweep.py                 roots → manifests → projects
    staleness.py             derived staleness (read-only)
    validators.py            uniformity validators registry
    files.py                 entry files: peek + guarded save
    export.py                registry.json export / rebuild
    util.py                  shared helpers (UTC timestamps)
    plans/
      __init__.py
      parser.py              house-format → structured doc
  server/                    Python stdlib, loopback — AS BUILT
    config.py                the settings seam (file+env)
    server.py                routing, feeds, guarded writes,
                             mutation endpoints (no SQL)
    healthcheck.py           /api/health probe (the
                             watchdog's check)
  ops/                       AS BUILT
    workbench-viewer-server.service.template
    install-unit.sh
    watchdog.sh
  viewer/                    the artifact source (canonical
                             here; synced by viewer.sh)
    SYNC.md                  the viewer.sh sync contract
    space.json               runtime + slug
    package.json             bun manifest (deps pinned)
    biome.json               lint + format (pinned Biome)
    tsconfig.json  tsconfig.*.json
    COMPONENTS.md            component contracts (Subplan 04)
    tools/
      gen-tokens.mjs         tokens.json → themes/ generator
    client/
      build.mjs              the artifact build
      src/
        main.tsx
        App.tsx              shell: rail, top bar, routing
        themes/              generated from tokens/tokens.json,
                             checked in; generator in build
          index.css          entry — @imports one file per
                             palette (fallback: one generated
                             theme.css — SPEC §11.2)
          fonts.css          bundled @font-face (Inter +
                             IBM Plex Mono woff2, local only)
          <palette>.css      one per palette, scoped to its
                             root selector, modes inside
        sections/
          Mockups.tsx        storyboard grid + contact sheet
          MockupDetail.tsx   drill-in: state panel, approval,
                             disposition bar, review log
          Plans.tsx          list rail + reading pane
          Todos.tsx
          Board.tsx          lanes + cards
        components/          the kit — one file per concept
          Chip.tsx  Badge.tsx  Button.tsx  Card.tsx
          Lane.tsx  Frame.tsx  StateControls.tsx
          EmptyState.tsx  Sheet.tsx  Tooltip.tsx …
        lib/
          api.ts             socket client (raw-socket bridge)
          format.ts          dates, numbers, hashes
          labels.ts          THE label map
    server/
      src/
        actions.ts           typed actions over the bridge
        privileged.ts        raw node:net socket bridge to
                             127.0.0.1:8792
  tests/                     unittest suites mirroring lib/
                             and server/
  tools/
    check.sh                 the ONE repo gate (biome + tsc +
                             build + unittest; Subplan 03)
```

Runtime / untracked (never in the tree above): `config.json`,
`viewer.env`, `state/` (lock, logs, edit backups, health
file), `workbench/` project-zero data (`registry.db`,
`registry.json`, `entries/`, `archive/`), `.venv/`,
`.plans/` (plan files are not tracked in this repo — the
build program lives there), the rendered
`workbench-viewer-server.service`, `__pycache__/`.

**Deviations from fundamentals §9, named:**

- **The §9 `lib/` split is NOT adopted.** §9 imagined
  `lib/db.py` / `mutations.py` / `review.py` /
  `state_schema.py` / a `validators/` package /
  `plans/structure.py` / `todos.py`. The built lib is
  `registry.py`-centred (schema + mutations + todos in
  `registry.py`; single-module `validators.py`,
  `manifest.py`, `files.py`) and works — it stays as built.
- **`theme.css` → `themes/` folder** (the owner's amendment,
  SPEC §11.2): §9's single generated `theme.css` is replaced
  by the `themes/` folder above, with the single-file form
  kept as the documented fallback.
- **As-built reconciliations:** §9's `config/viewer.example.json`
  is the root `config.example.json`; §9's `server/run.py` is
  the root `run.py` (server/ holds config/server/healthcheck);
  §9's `deploy` script + `var/` are the built `viewer.sh` +
  `state/`. §9's `viewer/server/src/` nesting is kept as
  frozen above.

**Export / portability rule:** no hardcoded paths or
machine assumptions in code; everything path-like derives
from the existing config seam (the config file plus the
`WB_*` env overrides — `WB_VIEWER_*` in this repo).
Export-with-zero-code-edits is the proof: the repo must run
on another machine from a fresh clone with only config
changes. Tracked docs use relative paths only.

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
(`POST /api/projects/rescan`). `wb projects` runs the
same sweep locally — it imports lib/ and is not an HTTP
caller. No filesystem watcher in v1.

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
- **Artifact items share the registry**: the Artifacts
  section is a sibling collection beside Mockups,
  discriminated by `kind = artifact` in the same `entries`
  table — no second store, no schema change. The split is
  at the feed: each collection's feed serves only its own
  kinds, while the export fold stays whole. An artifact
  item's questions are its declared `state_schema`, its
  answers are `state_json` bound by a review disposition,
  and its preview renders its main file in a sandboxed
  iframe over the guarded peek path.
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

`GET /api/health` · `GET /api/config` · `GET /api/projects` ·
`POST /api/projects/rescan` · `GET /api/projects/<slug>/mockups`
(`?archived=1`) · `GET /api/projects/<slug>/entries/<id>` ·
`GET|POST /api/projects/<slug>/entries/<id>/file` ·
`POST /api/projects/<slug>/entries/<id>/action`
(`{verb, ...}` → lib/ mutation, actor=viewer) ·
`GET /api/projects/<slug>/plans` · `GET /api/projects/<slug>/plan?path=` ·
`POST /api/projects/<slug>/plan/resolve`
(`{path, base_sha256, answers}` → the plan file's sentinel
questions answered in place via lib composition + the
guarded save) ·
`GET /api/projects/<slug>/todos` · `GET /api/todos` ·
`POST /api/projects/<slug>/todos` (`{verb, ...}`) · `GET /api/board`.

The whole HTTP surface lives under `/api`. The 15 legacy
unprefixed patterns were served as exact aliases for one
published checkpoint cycle after the unification and were
removed in the following cycle (the unification plan's
Step 8); they now return 404.

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
