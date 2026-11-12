# Viewer sync — the artifact source lives in this repo

The Workbench Viewer artifact (`workbench-viewer`) is
**deployed**, not separate: its source is canonical in this
folder (`viewer/`) of the workbench-viewer repo, and
`viewer.sh` at the repo root moves it to its runtime
location (the `workbench-viewer` runtime space in the
sibling ts-spaces tree, resolved via `VIEWER_RUNTIME_DIR`).

## Commands (from the repo root)

- `./viewer.sh status` — sha256 drift report between
  `viewer/` and the runtime sync set. Exit 3 on drift.
- `./viewer.sh pull` — runtime → repo. Run after any
  builder-driven change to the artifact, then commit.
- `./viewer.sh deploy [--force]` — repo → runtime: drift
  guard, backup, copy (transport only).
- `./viewer/deploy.sh` — the checkpoint path:
  `viewer.sh deploy` → builder build + publish of the
  runtime space, so a checkpoint is LIVE with no manual
  steps (checkpoint rule, live-work-tracking spec §1).
  The deploy carries no built-in gate; any failing step
  stops the script before publish.

## Deploy semantics

The runtime serves the **builder-published bundle**, not
loose source: `space.json` names `client/dist/index.html`
as the entry, and per the runtime space's AGENTS.md, build,
audit, and ship happen only through the web-artifact
builder interface — a manual `bun run build` does not
publish. So deploy is two steps by design:

1. `viewer.sh deploy` — drift guard, backup, copy the sync
   set into the runtime tree (transport only).
2. **Publish** — the builder pass over the runtime tree
   (invoked by `viewer/deploy.sh` through the builder CLI
   when available), which rebuilds and publishes from the
   source now in place. Until this step runs, deployed
   source is inert.

## Sync set

The `viewer/` tree's source files, as `viewer.sh` computes
them: everything except `node_modules/`, `dist/`,
`.bun-cache/`, and `*.db*` files. One exception: the
`dist/` exclusion does not reach into `vendor/` — the
vendored space SDK's `dist/` is its shipped, pinned form,
the tree syncs whole as tracked, and the runtime must be
able to reinstall the dependency from it. That includes
`space.json`, `package.json`, `bun.lock`, `bunfig.toml`,
the tsconfigs, `client/` (source + `build.mjs`), `server/`
(source; `server/.generated/` is builder-generated in the
runtime and regenerated there on every build), and
`tools/`.

## Repo build vs builder build

`client/build.mjs` in this repo is a Bun.build **shim**
(Subplan 03): the SDK's `buildClient()` refuses to run
outside the builder pipeline, so the repo gate bundles the
same entrypoint with the same production settings directly
via Bun.build to prove the client compiles offline. The
shim is what `tools/check.sh` runs; the **builder pipeline
is the real publish path** and runs in the runtime space.
If the runtime space scaffold ships its own `build.mjs`,
the repo canonical copy is what `viewer.sh` syncs — the
shim travels with the source.

## Actions are unified (2026-11-05)

`server/src/actions.ts` is the single maintained form of
the action set: the bridge (in `server/src/bridge.ts` —
the socket attempt plus its retry policy) and every
action's description live in this repo, and a publish
copies the files byte-for-byte instead of merging them
against a space-side variant. Two consequences are
load-bearing:

- `server/src/config.ts` carries its env default in the
  form the artifact's action validator accepts (`{}`;
  env resolution is host-side in `privileged.ts`, so
  the behavior is identical). Do not "restore" the
  donor-style default — the publish would reject it.
- The one standing exception to byte-copy sync is
  `client/index.html`'s generated slug line, which is
  the space's own identity marker and stays space-side.

## Vendored SDK vs platform version

The vendored `vendor/space-sdk` in this repo was
verified byte-identical to the space's tree on
2026-11-05, against platform version **28** (236 files).
Every publish brief must require the builder to report
the platform version it built against; when that
version moves past the vendored build, queue an SDK
fold-back (builder write-back, byte-verified, then
pull) as its own pass — do not wait for a publish to
fail on the drift.

## Configuration

No machine paths or addresses are hardcoded in the synced
source. The companion server's address reaches the actions
through the env seam (`WB_VIEWER_HOST` / `WB_VIEWER_PORT`,
defaults in `server/src/config.ts` only — the same names
the Python server's seam reads). The runtime location is
`VIEWER_RUNTIME_DIR` (see `viewer.sh` / `viewer/deploy.sh`).
