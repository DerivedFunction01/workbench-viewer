# Workbench Viewer — agent entry point

This repo is the workspace's **workbench harness**: one always-on
companion server + one artifact that shows mockups, plans, todos,
and an in-progress board for every project repo that opts in.
Founded 2026-10-25 on the Six-File Context Methodology (the owner's
JS Mastery playbook, adapted): this file is the single entry
point — there is no CLAUDE.md and no second plan system;
`.plans/` remains where plans live.

## Read order

Read these before implementing or making any architectural
decision, in this order:

1. `context/project-overview.md` — what the harness is, goals,
   features, scope
2. `context/architecture.md` — system structure, the sweep +
   manifest design, storage model, invariants
3. `context/ui-context.md` — the viewer's design context
   (the approved fundamentals, SPEC §11)
4. `context/code-standards.md` — implementation rules
5. `context/ai-workflow-rules.md` — workflow, scoping, gates,
   protected files
6. `context/progress-tracker.md` — current phase, completed
   work, open questions, next steps (update it after each
   meaningful implementation change)

The founding plan is
`2026-10-25-workbench-viewer-repo.md` (in the workspace
`.plans/` folder); the
workbench data model it inherits is specified in example-project-legacy
v2's subplan 09 (Part B). If implementation changes the
architecture, scope, or standards in the context files, update
the relevant file before continuing.

## Hard rules

- **Overlay rule.** Project repos never depend on this harness:
  they build, test, and run with the viewer absent. This repo
  never imports project code; it reads project *data files*
  (registry DBs, plan markdown, manifests) only.
- **another-project is EXCLUDED.** It has its own maintenance system
  and was external to this workspace. Never register it, never
  sweep it in, never retrofit it. Its absence is by design.
- **One mutation path.** All registry/todo writes go through
  `lib/` — the `wb` CLI and the server call the same lib
  functions. The server contains **no SQL**. Hand-editing a
  project's `registry.db` or generated `registry.json` is a
  process violation.
- **Data never migrates.** Project data (registry DB, entries,
  archive) stays in the project repo that owns it. This repo
  holds tooling only, plus its own project-zero data under
  `workbench/` (untracked, like every project's).
- **Ruled vs derived.** A mockup's `status` changes only via a
  mutation carrying a ruling note. Staleness is computed at read
  time and never written over a ruling.
- **Stdlib only** for `lib/` and `server/` (Python). The repo
  venv (built by `init_venv.py`, uv-managed Python 3.11) is the
  launch path — never system python.
- **The server's write surface is exactly two things:** guarded
  file saves (sha-checked, config-gated, default OFF) and lib/
  mutations. Nothing else writes.
- **Git:** local commits per completed plan step, author
  `DL <>` via per-command `-c user.name`/`-c user.email` flags.
  No pushes, no remotes, unless the owner rules otherwise.

## Commands

- Repo gate: `tools/check.sh` — the ONE gate (Python unittest + Biome check + typecheck + client build, fail-fast); run it before handing off any change.
- Build the venv: `python3 init_venv.py` (uv, Python 3.11)
- Tests: `.venv/bin/python -m unittest discover -s tests -v`
- Harness CLI: `.venv/bin/python wb --help`
  (verbs: `projects`, `init`, `add`, `list`, `show`, `set`,
  `set-status`, `supersede`, `verify`, `archive`, `unarchive`,
  `stale`, `validate`, `export`, `rebuild`, `bundle *`,
  `todo *`, `activate`, `print-schedule`)
- Server: `.venv/bin/python run.py` (binds per `config.json`;
  default 127.0.0.1:8792). Health: `GET /api/health`. All
  HTTP routes live under `/api`; the 15 legacy unprefixed
  patterns from before the unification were removed in
  release N+1 (the unification plan's Step 8) and return
  404.
- Viewer artifact sync: `./viewer.sh status|pull|deploy`
  (repo `viewer/` is canonical; the runtime is the
  `workbench-viewer` runtime space in the sibling ts-spaces
  tree, resolved via the config seam; publishing is a
  separate builder pass — see `viewer/SYNC.md`).
