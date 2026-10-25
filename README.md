# Workbench Viewer — the harness contract

One harness for every project repo in this workspace: a
companion server (always on, loopback) plus a single artifact
with four sections — **Mockups, Plans, Todos, Board** — fed by
each project's own data. Built from
`2026-10-25-workbench-viewer-repo.md`; the
mockup data model is example-project's subplan 09, Part B.

## Adopting the harness (a project repo's whole cost)

1. Add ONE tracked file at your repo root, `workbench.yaml`:

   ```yaml
   # Restricted YAML subset: flat `key: value` lines only,
   # `#` comments, no nesting, no lists. Unknown keys are an
   # error, so typos surface instead of silently doing nothing.
   name: My Project
   slug: my-project            # optional; default: directory name
   registry: workbench/registry.db   # optional — Mockups + Todos
   plans: .plans                     # optional — Plans + Board
   mockups: workbench/entries        # optional
   archive: workbench/archive        # optional
   ```

   Every path is relative to your repo root. Omit a key and
   that section is simply absent for your project — sections
   degrade independently. Omit the file and the harness cannot
   see your repo at all (opt-in by layout).

2. Make sure your repo root sits under one of the server's
   sweep roots (default: the workspace root — the parent of
   this repo). The sweep finds manifests at repo roots only,
   prunes `.git`/`.venv`/`node_modules`/`var`, and never
   descends into a repo it has found. Nothing else is required:
   no code, no imports, no config on your side.

3. Create your registry when you want Mockups/Todos:
   `wb --project <slug> init` (or the first `wb add` creates
   it). The DB, the generated `registry.json` beside it, your
   `entries/` and `archive/` are **your untracked data** —
   gitignore them. Mockups are transient workspace material;
   the durable record of a landed design is your SPEC/plan,
   never the registry.

## The rules that keep it honest

- **One mutation path.** `wb` and the viewer server call the
  same `lib/` functions; the server holds no SQL. Never edit
  `registry.db` or `registry.json` by hand.
- **Ruled status, derived staleness.** Statuses (`canonical`,
  `implemented`, `deferred`, `unexplored`, `hard-gate`,
  `abandoned`) change only with a ruling note. Staleness —
  age, days since verified, content drift — is computed at
  read time and shown as a badge; only `wb verify` clears it.
- **Approval binds to state.** Approving a mockup records the
  internal-state snapshot it covered. Change the state and the
  approval visibly stops covering it until re-approved.
- **The board is a view.** Todo cards, plan cards (placed by
  plan header status), and the review queue — derived, never a
  fourth store.
- **Overlay rule.** Your project must build, test, and run
  with this harness absent. If it ever *needs* the viewer,
  that is a defect in the project, not a feature of the viewer.
- **another-project is excluded by design** — its own maintenance
  system, external to this workspace. Do not add a manifest
  there.

## Operating the harness

- Server: `.venv/bin/python run.py` (127.0.0.1:8792 by
  default; `config.json` + `WB_VIEWER_*` env overrides — see
  `config.example.json`). Always-on under systemd
  (`ops/install-unit.sh`) with a watchdog (`ops/watchdog.sh`,
  healthcheck cron every ~5 min).
- `GET /health` reports the resolved config hash and the last
  sweep's project list — "why doesn't it see my repo?" is
  answered there.
- The artifact is published from `viewer/` via `./viewer.sh`
  (drift-guarded copy to the runtime tree, then a builder
  publish pass). Editing in the viewer is OFF by default
  (`file_editing_enabled` in the server config).
