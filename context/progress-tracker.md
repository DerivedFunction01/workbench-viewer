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
- Repo-home BACKEND landed on main 2026-10-25 (branch
  `build/repo-home`, tip `e9f5ae1`, merged `4932a01`): the
  viewer message store + cleanup lifecycle (`lib/messages.py`),
  the messages / settings-effective API, and the worktree +
  home derivations (`lib/worktrees.py`, `lib/home.py`) —
  gate green at 128 tests. The repo-home UI phase (Home /
  Overview / Inbox / Settings panels) is still pending.
- Repo-home B2 DIFFS landed on main 2026-10-25 (branch
  `build/repo-home-b2`, tip `04fba92`, merged `930f929`):
  the §18 diff engine (`lib/diffs.py` — one (repo, base,
  target, paths) mechanism, all modes, untracked + ignored
  groups, peek policy reused), `GET /api/projects/<slug>/diff`,
  and the Changes UI (plan Changes tab + worktree panel on
  the Plans landing; the panel moves into Overview when the
  repo-home UI phase lands) — gate green at 154 tests.
- Repo-home UI phase landed on main 2026-10-25 (branch
  `build/repo-home-ui`, tip `3816724`): watcher core
  (§15.1 — outbox table in messages.db schema v2,
  same-transaction append on sent, `GET /api/outbox`,
  generic notify targets from the maintenance loop);
  active-plan resolution (§17 — `lib/active.py`, `wb
  activate`, per-worktree actives + row showcase in the
  home feed) with the lib/home.py todo seam closed (bundle
  file todos, §3.7 DB fallback); Home + Overview + Inbox
  + Settings Workspace/Messages UI; grouped worktree
  presentation (§19) in Home, Overview, and the rail.
  Gate green at 161 tests on the branch.
- Mount seams closed on main 2026-10-25 (branch
  `build/viewer-mounts`, tip `d68beb0`): ChangesPanel now
  mounts in Overview worktree drill-ins (linked worktrees
  on expansion, main checkout behind a Changes toggle;
  Home unchanged), and AnchoredComment (D7) mounts in the
  Plans reader (plan anchor) and the Mockups entry detail
  (entry anchor) alongside its Overview showcase mount.
- SWEEP WORKTREE DEDUPE landed on main 2026-10-25
  (branch `build/sweep-worktree-dedupe`, tip `787bc03`):
  the sweep canonicalizes discovered checkouts by git
  common dir — a linked worktree never registers as a
  duplicate-slug project (the P1 that broke the rail);
  the main checkout's manifest is the one that registers,
  worktrees stay visible via its worktree derivations.
  If only worktrees are discovered, the project roots at
  the main checkout (manifest loaded from there); a main
  with no manifest registers nothing. Gate green, 191
  tests.
- Annotation (spec §12) BUILT on branch `build/annotation`
  (8 step commits over `a33161a`, gate green, awaiting
  merge): annotation = a message + a nullable `selection`
  payload (messages.db schema v3; raw offsets refused
  400; replies carry no selection). One re-location
  algorithm in `lib/annotations.py` + its client mirror
  (`sections/plans/relocation.ts`), pinned identical by
  the shared fixtures `tests/fixtures/relocation.json`
  (runner: `viewer/tools/test-relocation.ts`); status is
  derived at read, never stored. Lifecycle tokens +
  `AnnotationBadge` (→ Sent / ◐ Acknowledged / ✓ Done,
  Okabe hues; text variants follow the house contrast
  discipline — `viewer/tools/verify-contrast.mjs`, 280
  pairs, 0 failures). Plans UI: in-component text
  selection, draft-on-first-keystroke composer, Okabe
  marks, margin threads, `Annotations · N`. Mockups UI:
  drill-in anchors added (stage + all cards), click-to-
  select components with pinned composer/cards,
  per-exhibit list. Pickup (§13): `messages_list` attaches
  the derived `anchor_context` (excerpt + step when
  located; stored quote / label snapshot when moved).
  Anchor-leg audit: `viewer/tools/audit-anchors.ts` —
  21 required sites, 0 failures.
- Annotation MERGED to main 2026-10-25 (merge `490d9a6`):
  gate green on the merged tree, 228 tests. Server
  restart migrates the live messages.db to schema v3.
- Vanished references + commit-less repos BUILT on
  branch `build/diff-vanished-refs` (awaiting merge):
  a zero-commit repo is a state, not an error —
  worktree entries carry head null + `no_commits`,
  diffs run against the empty tree (`base_kind:
  "empty-tree"` + note "No commits yet — everything
  here is new."); a deleted worktree path returns a
  typed `gone` diff payload; a bundle whose plan
  document no longer loads falls back to the
  un-narrowed diff with a note, and vanished declared
  paths simply contribute nothing. Raw git stderr
  never reaches a payload: reasons/errors come from
  a small label vocabulary in lib/worktrees +
  lib/diffs. Gate green, 238 tests.
- Vanished-refs fix MERGED to main 2026-10-25: gate green
  on the merged tree, 238 tests. Server restart picks up
  the new worktree/diff derivations.
- Plan syntax conformance BUILT on branch
  `build/plan-syntax` (awaiting merge): the approved
  standard lands end to end — KaTeX math in the plan
  renderer (lazy chunk, vendored woff2 fonts in the
  themes bundle, source-text fallback for unparseable
  math), task lists as styled disabled checkboxes, the
  parser exposing `## Open questions` items + count and
  the `## Critical files` path list in the plan payload,
  and the `coding_plan` skill template rewritten to the
  standard's skeleton (decisions stated precisely,
  never transcripts). Proof: the conforming fixture
  (tests/fixtures/conforming-plan.md) through
  tests/test_plans.py and viewer/tools/test-math.ts.
- Plan syntax conformance MERGED to main 2026-10-25:
  gate green on the merged tree, 246 tests. Server
  restart picks up the parser's semantic sections.
- Plan grouping BUILT on branch `build/plan-grouping`
  (awaiting merge): §21 lands — the parser extracts a
  plan's `## Subplans` declaration (fence-aware, same
  discipline as Critical files; summaries and the
  bundles feed carry it), the Plans list derives groups
  at read (children nested one level under the first
  declaring parent, counts on rows, missing declared
  paths as muted rows, self/cycles per the Rulings),
  and the reader renders Subplans entries as navigation
  rows. Proof: tests/test_plan_grouping.py (feed family)
  + viewer/tools/test-grouping.ts (derivation, 10
  checks). Dogfood note: no plan in the workspace is a
  genuine child of the grouping plan and finished plans
  are never edited, so no declaration was added to any
  real plan; grouping is proven on fixtures.
- Plan grouping MERGED to main 2026-10-25 (merge
  `61dc0ac`): gate green on the merged tree, 257 tests.
  Checkpoint republish follows; live Plans data carries
  no declarations yet, so the list renders unchanged
  until a plan declares subplans.
- API unification (release N) BUILDING on branch
  `build/api-unification`: Step 1 created the
  `api-unification` bundle and the Step 8
  alias-removal todo `t-01M5TNR7V99D3P2ENBA85N0W2F`
  (status `todo`; it stays open through release N and
  is executed in release N+1).
- API unification release N closeout (build side,
  branch `build/api-unification`, tip `071bc0c`):
  Steps 1-5 + 7 landed in five commits (66a71a5,
  eef3144, ee9e39d, 4e2c855, 071bc0c). The server
  surface is one /api namespace: 27 canonical
  method/path patterns, with exactly 15 legacy
  patterns served through LEGACY_ROUTE_ALIASES
  (internal dispatch, never redirects) and guarded
  by tests/test_server_route_unification.py (frozen
  inventory, matcher, HTTP equivalence,
  served-without-alias tripwire, controlled-caller
  source scan). Full gate green on the branch:
  261 tests, all 4 legs. The healthcheck probes
  /api/health with the bounded release-N 404
  fallback to /health. PENDING (Step 6, release
  sequence): merge, companion restart, alias audit
  of the published artifact, checkpoint publish,
  canonical audit. Alias-removal todo
  t-01M5TNR7V99D3P2ENBA85N0W2F remains OPEN in
  `todo` status for release N+1 (Step 8); no alias,
  fallback, or inventory entry was removed.
- API unification MERGED to main 2026-10-25 (merge
  `71b4a40`, release N): gate green on the merged tree,
  272 tests (257 + the route-unification suite). Only
  the tracker conflicted; both sides' entries kept.
  Release sequence continues: restart, alias audit,
  checkpoint publish, canonical audit.
- Mobile variant BUILT on branch `build/mobile-variant`
  (5 step commits over `b044797`: seam+survey, phone
  shell, sections, annotations, this closeout) per the
  approved plan + mobile mockup, repo-home spec §20.
  ONE breakpoint: 480px (`max-width`), the seam in
  `viewer/client/src/lib/responsive.ts` — the mockup's
  exhibits are 390px frames and its own stylesheet's
  small-screen threshold is 480px; no tablet variant.
  The audit advisory is closed by cause: the shell's
  fixed 232px rail + content row measured 445px
  intrinsic on Home (582px on Plans) in a 390px box.
  Overflow fixes, all phone-gated: bottom tab bar +
  top bar + section nav shell; Board lanes stack,
  cards full width; Home project cards (§19 grouping
  intact); Plans rows wrap (§21 grouping intact);
  reader rails stack under their blocks; Changes
  summaries wrap, diff body keeps its own scroller;
  kit fix — SegmentedControl clamps (max-width 100%)
  and wraps between pills; MockupDetail single column
  is `minmax(0, 1fr)` after the bare-`1fr` blowout
  (cards measured 398px in a 358px column) was found
  by the probe. Annotations (§20): same lifecycle,
  badges, pickup; composer in-flow full-width with
  the connector ornaments dropped (annotation
  mockup's proven 390px treatment); anchor-moved
  lists with its quote, never dropped — proven with
  synthetic threads injected into the probe cache
  only (live data carries zero annotations). Proof:
  14/14 routes at 390×844 report zero viewport
  offenders on live data; desktop A/B at 1440×900
  vs `b044797` is geometry-identical on 8 routes
  (rail 232px, content 232×1208, no tab bar).
  Exceptions vs the mockup, explicit: (1) the top
  bar's theme toggle is NOT reproduced — appearance
  controls live on Settings only (§3 standing
  ruling); (2) specimen-only status chips with no
  real-data counterpart (project-head "Doing", per-
  step chips) are not reproduced. Gate PASS on the
  branch tree: 272 tests, all 4 legs. PENDING
  (parent release sequence): merge by SHA, merged-
  tree gate, companion restart, checkpoint publish
  with the 390px audit; the PR waits on this landing.
- Mobile variant MERGED to main 2026-10-25 (merge
  `91746f0`): gate green on the merged tree, 272 tests.
  Checkpoint publish follows; its audit must prove the
  phone rendering in the published artifact itself
  (tab bar, no sideways scroll, drill-in click-through).
- Plan closeout enforcement BUILT on branch
  `build/plan-closeout-enforcement` (awaiting merge):
  the plans feed now flags the two Status/filing
  contradictions from the plan syntax standard's
  Closeout section as bundle errors the Plans list
  already renders inline — an active plan declaring
  complete, and a finished plan declaring anything
  other than complete/superseded — each exactly one
  `closeout:` error naming the fix. No flag for a
  missing Status header (the run record under
  finished/ stays clean) and none for bundle
  directories (their state rides their todos).
  Proof: tests/test_plan_closeout.py — the fixture
  matrix across the filing states, declared-status
  normalization pins, and a real-corpus pass over this
  repo's own .plans/ after the 2026-10-25 sweep
  (zero flags, coverage-guarded). Gate green on the
  branch: 287 tests. PENDING (parent release
  sequence): merge by SHA, merged-tree gate, restart,
  checkpoint publish; on merge the parent closes the
  closeout plan itself out under this rule and
  verifies the live feed shows zero flags.
- Plan closeout enforcement MERGED to main 2026-10-25
  (merge `bbda3ab`): gate green on the merged tree,
  287 tests. Server restart makes the flag live; the
  enforcement plan is closed out under its own rule in
  the same pass.
- Mobile Plans rows MERGED to main 2026-10-25 (merge
  `ea86452`): phone rows are structurally stacked
  (column, title full width, metadata beneath) instead
  of relying on flex wrap. Gate green on the merged
  tree. Checkpoint publish follows; the owner's device is
  the decisive check (headless Chromium stacked even
  before the fix).
- Subplan declaration precision BUILT on branch
  `build/subplan-declaration-precision` (awaiting
  merge): the parser's `## Subplans` extraction counts
  an extracted span as a declaration only when it ends
  in `.md`; everything else in the section is prose
  about subplans and declares nothing. The proving
  case is the plan syntax standard itself — no
  exemption, no carve-out: its rules bullets
  (backticked `.plans/` and `Parent:`, plain text up
  to an em-dash) extracted three phantom "missing"
  children; it now extracts zero. A declared `.md`
  path that resolves to nothing still renders as a
  missing child row per section 21. Proof:
  TestSubplans precision fixtures (a mixed section
  extracts exactly the one `.md`; a pure-prose section
  extracts none) + TestSubplanPrecisionCorpus over
  this repo's own .plans/ (standard declaration-free,
  every corpus declaration naming a plan file); the
  grouping fixtures are unchanged and green. Gate
  green on the branch: 291 tests. PENDING (parent
  release sequence): merge by SHA, companion restart
  — server-side only, no republish.
- Subplan declaration precision MERGED to main
  2026-10-25: gate green on the merged tree, 291 tests.
  Server restart makes it live; the precision plan is
  closed out in the same pass.
- Overview plans card removal BUILT on branch
  `build/overview-plans-removal` (awaiting merge):
  repo-home spec section 22 lands — the Overview's
  flat Plans card and its PlanList are deleted (the
  Plans section is the only plan list; the card had
  no section 21 grouping, no finished view, no
  checklist strips, no bundle error lines, and it
  violated the strip's own references-never-re-
  implemented rule). The section 17 Active plan
  showcase and the worktree panel are unchanged.
  A Plans reference joins the Todos & review strip
  between Todos and In triage, in the strip's
  link-and-count pattern: the link plus the active-
  plan count from the home payload Overview already
  loads (the plans block's counts buckets, todo +
  doing; archived plans bucket done, so the count
  is the not-done plans — no new fetch, nothing
  fabricated). The plans query and its orphaned
  imports leave Overview with the card. The
  showcase's empty state now points at the Plans
  section instead of "the plan list below". Gate
  green on the branch: 291 tests. PENDING (parent
  release sequence): merge by SHA, checkpoint
  publish (client change), audit of Overview at
  desktop and phone widths against section 22.
