# Code Standards

## General

- Keep modules small and single-purpose; fix root causes, do
  not layer workarounds.
- Stdlib only in `lib/` and `server/` — if a need seems to
  require a dependency, that is a design question for
  `progress-tracker.md`, not an install.
- Import from leaf modules; no re-export barrels, no
  backward-compat shims. When code moves, call sites update in
  the same change.

## Python

- Python 3.11 (uv-managed venv via `init_venv.py`). The venv
  interpreter is the only launch path; never system python.
- Every lib/ function that touches a DB takes an explicit
  `db_path` — no globals, no ambient "current project", so
  tests run on temp files.
- One short `BEGIN IMMEDIATE` per mutation; per-row `version`
  compare-and-swap on writes that take an expected version.
- Timestamps are UTC ISO-8601 strings, produced by one helper.
- Validate unknown external input (manifests, request bodies,
  plan files) at the boundary before trusting it; errors are
  explicit values or typed exceptions, never silent defaults.
- Tests are `unittest`, in `tests/`, mirroring the lib/
  layout; fixtures are synthetic and built in temp dirs.

## TypeScript (viewer/)

Decided with the approved fundamentals (SPEC §11; the held
record was closed by build Subplan 01, 2026-10-25):

- Follow the artifact runtime's conventions. Strict typing
  throughout (`strict` TypeScript config); `import type`
  for type-only imports; actions typed end to end.
- Token-only styling: components use the `--wb-*` tokens
  generated from `tokens/tokens.json` — no hardcoded color,
  spacing, or radius values; no CSS-in-JS; no component
  library (the kit is hand-built from tokens, SPEC §11.4).
- All dependencies are bundled at build time; nothing is
  fetched from a CDN at runtime. Fonts are bundled woff2
  (Inter for UI, IBM Plex Mono for code contexts).
- The client never hardcodes the server host/port — they come
  from artifact settings (defaults in one place).
- Lint + format is Biome: one pinned version, config
  in-repo at `viewer/biome.json` (SPEC §13 resolution 5).

## API / server

- Validate and parse request input before any logic runs.
- Response shapes are consistent: success payloads carry
  `captured_at`; failures are `{error}` with the donor's
  status conventions (400 bad input, 404 unknown project /
  entry, 409 stale sha or version, 403 editing disabled /
  secret path, 413 over caps).
- The server's write surface is exactly: guarded file saves +
  lib/ mutation endpoints. Any new write starts as a lib/
  function with a CLI verb, then gets an endpoint.

## Data and Storage

- Metadata lives in the registry DB; mock content lives in
  files; large content never goes in the DB.
- `registry.json` is generated — never edited by hand, never
  a second source of truth.

## File Organization

- `lib/` — harness core (sweep, manifest, registry, todos,
  validators, staleness, export; `lib/plans/` the parser)
- `server/` — HTTP layer + config seam + healthcheck
- `viewer/` — artifact source (internal layout frozen in
  architecture.md's Target directory layout section)
- `ops/` — systemd template, installer, watchdog
- `tests/` — unittest suites mirroring lib/ and server/
- `state/` — runtime only (gitignored)
- `workbench/` — project zero's data (gitignored)
