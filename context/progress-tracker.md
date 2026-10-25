# Progress Tracker

Update this file after every meaningful implementation
change.

## Current Phase

- Implementation of the founding plan, in progress
  (started 2026-10-25).

## Current Goal

- Land the harness step by step: scaffold → lib/ + `wb` →
  plan parser → server → viewer (Mockups, then Plans /
  Todos / Board) → adoptions → deploy.

## Completed

- Step 0: the founding plan —
  `../.plans/2026-10-25-workbench-viewer-repo.md`
  (drafted and refined 2026-10-25; the owner: "Implement the
  plan").
- Step 1 (in this commit): repo scaffold + the six context
  files, seeded from the Six-File templates and adapted
  (AGENTS.md entry, `.plans/` stays the plan system).
  Sweep-config + manifest formats spec'd in
  `architecture.md`; the manifest was exercised on paper
  against example-project's real layout (fields suffice,
  nothing project-specific leaks — see architecture.md).
  Per the owner's steering (2026-10-25), `ui-context.md` is a
  marked PLACEHOLDER — the viewer's fundamentals are designed
  separately and need his approval; the frontend dependency
  decision is recorded OPEN in `architecture.md`.

- Step 2: harness core (lib/ + wb) DONE — 45 unittest cases
  green under the repo venv: registry discipline (CAS,
  ruling-required transitions, atomic mutations, append-only
  history), full CLI lifecycle walk for two fixture projects
  with no cross-talk, export→rebuild round-trip identical
  (fixed clock), uniformity gate refusing canonical/approve,
  approval bound to the state snapshot, staleness explainable
  and provably non-mutating, validator registry with planted
  violations, manifest subset + sweep mechanics.

## In Progress

- Step 3: plan parser against the real corpus.

## Held (the owner's direction, 2026-10-25 — not a failure)

- Steps 5–6 (both viewer builds) and all design-bearing
  content: the viewer's fundamentals (theme, tokens, fonts,
  styling, concrete frontend dependencies, `viewer/` layout)
  are designed separately and must be approved by the owner
  before they are set into the build. Step 8's artifact
  publish is likewise held while 5–6 are held.

## Next Up

- Step 3: plan parser against the real corpus.
- Step 4: server + ops (systemd, watchdog).
- Step 7: adoptions (project zero, then v2 manifest).
- Step 8: systemd units; publish held with Steps 5–6;
  declutter blocked on subplan 09 Part A data (reported,
  not forced).

## Open Questions

- Final repo/artifact name: working name `workbench-viewer`
  (plan OQ1 — the owner's to rename).
- Todos store: registry DB tables (plan rec, adopted).
- Board sources: todos + plan cards + review queue, exactly
  three (plan rec, adopted).
- Cross-links to the git repo viewer artifact: link-only,
  deferred (plan OQ3).

## Architecture Decisions

- **Frontend fundamentals OPEN** (the owner's steering,
  2026-10-25): theme/tokens/fonts, styling, concrete
  frontend dependencies, and `viewer/` layout await his
  approval; nothing design-bearing is finalized in this repo
  until then.
- Server port **8792** (8791 is the git repo viewer's),
  recorded in `config.example.json` / server config defaults.
- Manifest parsed as a **restricted YAML subset** (flat
  scalars only) by lib/ — stdlib has no YAML, and the format
  needs nothing more; strictness makes typos loud.
- Review log and approval snapshots ride in the entries
  `history` table (verbs + JSON payloads), per subplan 09;
  approval coverage is derived from the latest approval row.
- Todos get their own tables in the same per-project DB
  (subplan 09's schema predates todos; `todo_events` mirrors
  `history` so entry history stays entry-pure).
- Artifact source is canonical in `viewer/`, synced to the
  runtime tree with `viewer.sh` (the git viewer's `ui.sh`
  pattern); publishing is a separate builder pass.

## Session Notes

- v2 has NO registry data yet (subplan 09 Part A has not
  run): Step 7's v2 verify is manifest + sweep discovery +
  Plans/Todos working + Mockups' honest empty state. The full
  mockup lifecycle proof runs on fixture projects in tests.
- The SPEC extraction effort owns v2's SPEC.md and
  `.plans/spec-extraction/` — never touch those.
