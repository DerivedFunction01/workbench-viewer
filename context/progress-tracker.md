# Progress Tracker

Update this file after every meaningful implementation
change.

## Current Phase

- The viewer build program is the ACTIVE plan
  (`.plans/2026-10-25-viewer-build-program.md`, approved
  2026-10-25): founding Steps 1–4, 7, 8-units are DONE;
  this program builds the viewer itself in Subplans 01–09.
  Subplan 01 (foundations: docs + layout freeze) is DONE;
  Group G1 (Subplans 02 + 03) is next.

## Current Goal

- Build the viewer to the approved SPEC: tokens + themes
  (02) and tooling + gate (03) → component kit (04) and
  shell + bridge (05) → the four sections (06–07) →
  integration + publish gate (08) → data + declutter (09).
  Founding Steps 5–6 (the viewer builds) map to build
  Subplans 06–07.

## Completed

- Step 0: the founding plan —
  `2026-10-25-workbench-viewer-repo.md`
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

- Step 3: plan parser DONE — 11 tests green (suite total
  56): lossless partition proven over the whole real corpus
  (30+ files, header + section raws reconstruct the source
  exactly), header fields, both step shapes (numbered
  `files:`/`verify:`/`done when:` items — incl. subplan
  09's two step groups, 10 steps; `### Step N —` headings
  in the 2026-10-23 plans), numbered non-step lists never
  misparsed (bootstrap plan's open questions), status
  buckets for the board, non-conforming plans flagged and
  returned whole. Honest note: the live corpus has NO
  mermaid fence yet — that path is proven on a
  corpus-shaped fixture; a real fence will parse unchanged.

- Step 4: server + ops DONE — 14 server tests green
  (suite total 70): real launch via run.py against two
  fixture projects; every feed answers for both; a locked
  DB degrades only its own project's payload; wrong-sha
  save = 409 with the file byte-identical; editing disabled
  = 403; canonical-without-ruling via the action endpoint
  refused (400), with ruling = 200 + registry.json
  regenerated; orphan-folder reconciliation surfaces as
  problems. `server/` holds no SQL (lib/ owns it all);
  config seam in `server/config.py` (port **8792**);
  ops/ unit template + installer + watchdog mirror the git
  viewer donor; `viewer.sh` sync is ready for the (held)
  viewer source. Live smoke on the real config: healthcheck
  exit 0, sweep finds 0 projects until Step 7's manifests
  land. (curl in this shell needs --noproxy for loopback —
  the egress-proxy trap; healthcheck.py is the probe.)

- Step 7: adoptions DONE — project zero adopted itself
  (tracked `workbench.yaml`; registry initialized via `wb
  init`; 4 genuine todos seeded: fundamentals approval,
  final name, SPEC.md approval, artifact retirement;
  Mockups honestly empty — the build produced no mockups
  while Steps 5–6 are held). v2 adopted by manifest only
  (`workbench.yaml` in the `example-project` repo, the one
  authorized file; NO v2 commits, registry NOT initialized —
  it arrives with subplan 09 Part A). Live verify on the
  real config: sweep discovers exactly 2 projects (another-project
  absent by design), 0 sweep errors; v2 Plans feed lists
  its 11 plans; v2 Mockups/Todos show the correct
  not-initialized state; board aggregates both projects.

- Step 8: units DONE, publish held, declutter blocked.
  systemd unit `workbench-viewer-server` installed +
  enabled + active (venv python, port 8792); healthcheck
  exit 0 with 2 projects; watchdog cron
  `workbench-viewer-healthcheck` (every 5m, plain agent job
  — no artifact exists yet for a space owner); revival
  proven end to end (server PID killed → watchdog revived
  via systemd → health restored). PUBLISH held: no viewer
  exists while Steps 5–6 are held. DECLUTTER blocked on
  subplan 09 Part A data: no registry entries exist in any
  project, so no standalone artifact can be retired yet.
  Implementation record added to the founding plan
  (2026-10-25).

- SPEC.md APPROVED + TRACKED (the owner, 2026-10-25): the SPEC
  as a whole approved with the §13 resolutions (name
  FINAL, cross-links link-only, staleness check not
  scheduled in v1, palette #2 = TEAL, Biome adopted, SPEC
  tracked); the §11 fundamentals approved WITH amendments
  (multiple palette themes — olive is the DEFAULT palette,
  not the only one; themes-folder CSS organization with
  the single-file fallback); §14 (unified schema + uniform
  interactivity) ruled. SPEC.md is committed as its own
  commit (build Subplan 01, Step 1).

- Build Subplan 01 (foundations) DONE: `ui-context.md`
  rewritten from the approved fundamentals (no placeholder
  language remains); the OPEN frontend record in
  `architecture.md` and the HELD TypeScript paragraph in
  `code-standards.md` closed as DECIDED, pointing at SPEC
  §11; the target directory layout FROZEN in
  `architecture.md` (backend as built — the fundamentals
  §9 lib split explicitly NOT adopted; frontend per §9 as
  amended, the `theme.css` → `themes/` deviation named).
  Founding Steps 5–6 are UNHELD and map to build Subplans
  06–07.

## In Progress

- Nothing running. Build program Group G1 is next:
  Subplan 02 (tokens + themes) and Subplan 03 (tooling +
  the one gate) — independent, may run in parallel.

## Held (gated, not blocked)

- The fundamentals hold on founding Steps 5–6 is LIFTED
  (fundamentals approved 2026-10-25; the builds proceed as
  build Subplans 06–07).
- Artifact PUBLISH (build Subplan 08) and the DECLUTTER
  (build Subplan 09) each need the owner's verbatim word at
  their gate — not ruled yet. The declutter additionally
  waits on subplan 09 Part A data (no registry entries
  exist in any project yet, so no standalone artifact can
  be retired).

## Next Up

- Build Subplan 02: tokens + themes (`tokens/tokens.json`,
  the generator, the `themes/` folder + @import-inline
  build proof, teal palette #2 values + contrast
  verification).
- Build Subplan 03: tooling + the one gate (bun package in
  `viewer/`, Biome pinned + configured, tsconfigs, one
  gate command). Subplans 02 + 03 are Group G1 —
  independent, parallel-safe.
- Then Group G2: Subplan 04 (component contracts + kit) +
  Subplan 05 (shell + socket bridge); Group G3: Subplans
  06–07 (the four sections = founding Steps 5–6);
  Subplan 08 integration + conformance (publish on the owner's
  verbatim at its gate); Subplan 09 data (Part A triage) +
  declutter.

## Open Questions

- Repo/artifact name: RESOLVED — `workbench-viewer` is
  FINAL (SPEC §13 resolution 1).
- Todos store: registry DB tables (plan rec, adopted).
- Board sources: todos + plan cards + review queue, exactly
  three (plan rec, adopted).
- Cross-links to the git repo viewer artifact: RESOLVED —
  link-only (SPEC §13 resolution 2).

## Architecture Decisions

- **Frontend fundamentals DECIDED** (the owner, 2026-10-25;
  SPEC §11; closed in this repo by build Subplan 01):
  modes (dark/light) × palettes (olive DEFAULT, teal is
  palette #2), tokens sourced from `tokens/tokens.json`,
  themes-folder CSS organization with the single-file
  fallback, Inter + IBM Plex Mono bundled, React 19 +
  Tailwind CSS v4 + the §11.5 dependency set, Biome
  lint/format; the `viewer/` layout is frozen in
  architecture.md's Target directory layout section. (This
  record was OPEN during the held period; the fundamentals
  were designed separately and approved with amendments.)
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
