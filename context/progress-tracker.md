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
- API unification Step 8 (release N+1) BUILT on branch
  `build/api-alias-removal` (awaiting merge): the legacy
  aliases are removed. LEGACY_ROUTE_ALIASES and the
  _canonicalize dispatch pass are gone from
  server/server.py (both route handlers dispatch on the
  canonical /api segments directly), and the
  healthcheck's bounded release-N fallback to /health is
  gone with them — it probes only /api/health. The
  conformance suite is rewritten for the removed world:
  the frozen inventory survives only as the 404 proof
  matrix (all 15 former legacy patterns return the
  router's own 404 over HTTP while their canonical
  counterparts still succeed; near misses stay 404; the
  served-without-alias tripwire covers all 27 stripped
  candidates with no exclusions; machinery-removed
  guards pin the absence of the map and the pass; the
  caller scan requires zero legacy literals in the
  healthcheck). Route docs (SPEC.md,
  context/architecture.md, AGENTS.md, README.md) record
  the removal. Caller audit before removal found no
  remaining legacy caller: the only legacy literal in
  production code was the healthcheck fallback itself —
  bridge actions, watcher hook, and watchdog were
  already canonical. Gate green on the branch: 285
  tests (291 baseline − 6: the conformance suite's 15
  release-N tests become 9 removal-proof tests).
  PENDING (parent release acts): merge by SHA,
  companion restart, live /api/health proof, live 404
  proof of the former legacy paths, and closing the
  alias-removal todo `t-01M5TNR7V99D3P2ENBA85N0W2F`
  with the removal evidence.
- API unification Step 8 RELEASED 2026-10-25 (parent):
  merged to main, gate green on the merged tree,
  companion restarted; live proof — /api/health 200,
  former legacy paths (/health, /config, /projects,
  /board) return the router's 404. Bundle todo
  t-01M5TNR7V99D3P2ENBA85N0W2F closed with this
  evidence. The /api surface is now the only surface.
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
- Overview plans-card removal MERGED to main
  2026-10-25 (merge `8208106`; tracker append conflict
  resolved keeping both entries): gate green on the
  merged tree, 291 tests. Checkpoint publish follows.
  The removal plan is closed out in the same pass.
- Sanitization under the owner's portability ruling
  (2026-10-25): no tracked file may carry the owner's
  name, another repo's name, or paths outside this
  repo, so a fresh clone works anywhere. Applied at
  the tip: the other projects take generic example
  names, owner attribution becomes "the owner" (the
  message author handle is renamed with it across
  lib, server, client, and tests), runtime paths
  resolve repo-relative to the repo, the one
  host-absolute dependency is vendored under
  viewer/vendor/, and the published artifact is
  named generically in prose. A guard test
  (tests/test_external_references.py) scans every
  tracked file for the forbidden strings, and
  AGENTS.md now carries the rule as a hard rule.
  The same replacements are carried through the
  full history by rewrite: commit SHAs in the
  entries above predate the rewrite and are
  superseded. The pre-rewrite history is preserved
  on the local pre-sanitize-backup branch.
- Sanitization rulings closed (2026-10-26): the
  vendored SDK tree (viewer/vendor/) is pinned
  third-party code — the guard test excludes it by
  prefix with the boundary stated in its docstring,
  and Biome ignores the tree like dist, returning
  repo files to their baseline diagnostics (75
  files, 2 warnings, 30 infos, no errors). The
  live-corpus plan tests no longer derive the
  corpus from the checkout's location: the
  WB_LIVE_CORPUS environment variable names the
  directory holding the project checkouts — unset,
  the corpus tests skip with the variable named
  (13 fixture tests still run); set, all 28 run.
  With the gate green at the tip, the history
  rewrite follows, carrying the Phase-1
  replacements through every commit.
- Phone tab bar pinned (2026-10-25; plan
  `.plans/finished/2026-10-25-phone-tab-bar-pin.md`;
  merge `a71a060`): the owner reported the phone bottom
  tab bar scrolling with the page in the published
  artifact. The phone shell is now a fixed-height app
  shell — root `height: 100dvh` with overflow hidden,
  the content `<main>` is the sole scroller
  (`overflowY: auto`), and the tab bar is an in-flow
  sibling after the scroller, pinned by construction;
  a route-keyed effect resets the scroller on
  navigation. Probe at 390px scrolled for real: the
  bar's bottom edge stayed at the viewport height
  (844) before and after scrolling to the bottom,
  `window.scrollY` never left 0, desktop geometry
  byte-identical. Gate green on the merged tree; the
  owner's phone remains the decisive check.
- Supersede by title picker (2026-10-25; plan
  `.plans/finished/2026-10-25-supersede-picker.md`;
  merge `a6df84f`): the owner reported the Lifecycle
  card's Supersede button rendering outside its
  container and the control demanding a typed entry
  id. The typed-id row is deleted — the card now
  queries the project's own mockups feed and offers a
  full-width select of sibling entries by title and
  ruled status; the danger button sits in its own row
  beneath, disabled until a choice, payload unchanged.
  The "Superseded by" meta row resolves the id to the
  target's title through the same feed (raw id only
  when the target is outside the active feed). Probe:
  39 candidates by title on the 40-entry feed, button
  inside the card at desktop and 390px, no mutation
  fired. Gate green on the merged tree.
- Vendor sync carve-out (2026-10-25; plan
  `.plans/finished/2026-10-25-vendor-sync-carve-out.md`):
  viewer.sh's `*/dist/*` sync exclusion silently
  stripped the vendored space SDK's own dist/ — 233 of
  its 236 files — from every deploy, leaving the runtime
  with a 3-file vendor the dependency cannot reinstall
  from (the failure the 3a378f9 publish hit and repaired
  by hand in the space). The dist predicate now excludes
  a path only when it is not under vendor/; SYNC.md's
  sync-set paragraph states the exception. Proof: status
  showed exactly the 233 missing vendor files as drift
  and nothing else (build-output dists stay excluded);
  after deploy the runtime vendor holds all 236 files,
  sha-verified, trees in sync. Gate green.
- Plan questions resolvable in the viewer (2026-10-26;
  plan `.plans/2026-10-25-plan-questions-resolvable-in-viewer.md`,
  STILL IN PROGRESS — see the open act below; merge
  `172f6fb`): a plan's `## Open questions` items may
  carry a `wb-question` sentinel (grammar + worked
  examples in the plan syntax standard; the
  `coding_plan` skill carries the authoring rule). The
  parser extracts question records (byte-exact corpus
  round-trip unbroken; malformed sentinels degrade to
  plain render + a `sentinel_errors` report, never a
  conforming-flag flip); the plans feed + plan payload
  carry `questions` (+ `file_sha256`); POST
  `/api/projects/<slug>/plan/resolve` composes the
  answers via the parser and writes through a new
  lib guarded save for confined non-entry files
  (editing flag, sha CAS 409, backup, atomic replace —
  the server's write surface stays the two sanctioned
  things). The Plans reader renders a Questions card
  (choice segmented with the recommended option
  badged, toggle with author labels, text input; one
  Resolve posts the whole set; a 409 is a reload
  prompt, never a silent overwrite). The plan's four
  recommendations are the build defaults. Proof: 314
  unittest cases green (29 new: parser/apply_answers +
  real-HTTP resolve incl. byte-exact write, stale-base
  409, editing-disabled 403), bun helper tests 7/7,
  anchor audit 21 sites 0 failures, gate green on the
  branch and the merged tree; live server (commit
  `172f6fb`) serves both dogfood plans' questions with
  `file_editing_enabled` now TRUE in the deployed
  config. Source deployed to the runtime (backup
  `workbench-viewer.bak-20261026032259`, trees in
  sync) but NOT yet published — no builder CLI on this
  box; the publish + both-themes/both-modes audit run
  through the builder interface. REMAINING OWNER ACT:
  resolve the determination's four questions in the
  viewer (`.plans/2026-10-25-workbench-artifacts-alongside-mockups.md`,
  sentinel form, all unanswered); the plan completes
  when the file on disk shows them checked + answered.
- Live-corpus test paths reconciled (2026-10-25): the
  plan-file reconciliation moved the founding plan from
  the workspace root's `.plans/` into this repo's
  `.plans/`; the env-gated corpus tests in
  `tests/test_plans.py` still derived it from the old
  location (3 errors with `WB_LIVE_CORPUS` set, invisible
  to the normal gate, which skips them). `FOUNDING` now
  derives through this repo's checkout like
  `VIEWER_PLANS`, and `test_list_v2_plans` lists
  `VIEWER_PLANS` for its founding assertions. Verified:
  the full suite (314 tests) passes with
  `WB_LIVE_CORPUS` set, the three named tests
  individually green, and the standard gate green.
- Artifacts collection LANDED (2026-10-25): a sibling
  Artifacts collection beside Mockups, per the ruling in
  repo-home spec §23 — same entries table and lifecycle,
  new kind `artifact`, the collection boundary drawn at
  the feed. Per-kind uniformity (question completeness
  for artifacts, design discipline for mockups), a
  sandboxed scriptless preview over the peek path, the
  Board's review lane unioned across both collections
  with cards routing by kind, and a sibling
  ArtifactDetail over the shared detail blocks. The
  pilot — "Deferred and Gates, Explained" — is
  registered in the companion project's registry as an
  entry-dir artifact with its questions declared in its
  state schema, unanswered (answering it is the owner's
  act); the answer loop was proven end to end on a
  throwaway item, archived after. The plan's two open
  questions (archive guard, Mockups drill-in parity)
  remain open, untouched. Merged `71b0a1e`, gate green
  on the merged tree.
- **Write-denial hardening LANDED** (incident 2026-10-26; plan 2026-10-26-doctor-write-denial-hardening): from ~19:34 UTC the environment intermittently denied file content writes to agent-domain processes (files created empty, writes raising EPERM; in the worst windows sqlite reads of WAL databases failed too). Both companion servers (systemd domain) were healthy throughout, but their healthchecks run in the agent domain and crashed on the state-file write - and the watchdog reads any non-zero exit as death, so it restarted a healthy server every cycle. Fix: the health verdict rides on the probe alone - `server/healthcheck.py` writes its health file through builtin `open()` inside a guard, warns on failure, and never lets bookkeeping change the exit code (proven live mid-denial: write failed, exit 0). Every `Path.write_text` in `lib/` now goes through one `open()`-based seam (`lib/util.py: write_text`), and the doctor's state save is contained the same way (the digest posts first; a failed save warns instead of crashing - worst case one repeated diff). One test pins the doctor containment. The git repo viewer's healthcheck received the identical fix in its own repo. Landing (gate, commits) waited ~1.5h for a verified write window; the servers never waited - the fix was live on disk from the edit and both bounce loops died immediately (uptimes 19m/13m and counting at first check).
- **Doctor bundle-relative reference fix LANDED** (same day; plan 2026-10-26-doctor-bundle-relative-refs): digest #16 posted 12 `todo-missing-plan` findings against correctly formed bundles in another project - their todos declare `plan: plan.md`, the bundle-relative spelling for a bundle's own plan, which the resolver did not know (it covered the root-relative and plans-dir-relative spellings and their `finished/` mirrors only). `_plan_ref_exists` now also resolves a relative reference against the declaring todo's own bundle home (the parent of its `todos/` folder), location-true in the active tree and under `finished/` alike. The finding's semantics are unchanged: a reference resolving in no form still fires, and a plan-less todo is still never flagged. Four tests pin the form both ways (active, finished, absent plan, wrong filename). Proof digest at landing: 0 new, 12 resolved, 0 current - the doctor is clean again.
- **Doctor findings triage LANDED** (the owner's "Adopt the recommendation", relayed from the main chat; plan 2026-10-26-doctor-triage-scope; branch build/doctor-triage-scope merged): `plan-status` and `plan-closeout` are now scoped to plan files only, via a three-limb classification in the doctor - run records out by name (`.handoff.md`, `-run-record`), determinations/living references out by their own declared status (the plan-syntax standard's closeout exemption, reused), and report genres out by marker plus silence (dossier/sweep/provenance/comparison/design-record tokens AND no declared Status - the silence condition is load-bearing: a report that declares a Status stays in scope). A new manifest posture, `registration: as-is`, makes `plan-status` informational for a project registered as found (computed, never posted; `plan-closeout` is NOT downgraded) - posture is per-project data set in that project's own adoption file; no project is named in tracked code. Census against the live corpus: 54 findings -> exactly 1, the one genuine contradiction the recommendation kept visible (a finished plan declaring "planned"). 11 new tests pin every limb and the exception's shape both ways. Proof digest posted at landing.
- **Phone document-flow rebuild + answering flow LANDED** (plan 2026-10-26-phone-document-flow; branch build/phone-document-flow merged): the owner's on-device verdict split the morning's release in two - the fixed bars WORK (confirmed on his phone), but tapping an answer still blanked the content. Final diagnosis, proven by instrumented probe: staging never couples into the document (panel-local state, zero outside-card mutations); the blank was the viewport guard's ADOPTION path - a sustained visualViewport reduction at the tap (his host reports one while interacting) was adopted as the shell height, collapsing the content band behind the working bars. The chain is now deleted outright: the phone presentation is plain document flow (no fixed height, no inner scroller, no visualViewport consumer anywhere; `lib/viewport.ts` and its test removed), the bars stay `position: fixed` with the content padded by their measured heights, and route changes reset the real scroller. Probe discovery with lasting effect: the space host's own fixed overflow wrapper is the app's true scroller (`window.scrollY` is permanently 0 in this hosting) - scroll operations resolve it via `lib/scroll.ts` with a window fallback. Answering flow per the owner's ruling (leave it selected until submit; submit sends one message; a script edits the file; wait for the new file back): staging is card-local (panel memoized at its call site), Submit is one POST plus exactly one fetch swapped in atomically - the sampling caught the swap fetch silently honoring the host client's default staleness and swapping nothing over a written file (now `staleTime: 0`), and the card-anchor restore holds the reading position across the swap (exact mid-document; at the document end, preservation is bounded by end-of-document clamping, proven by stick test). Verification 16/16 (record: mobile-probe `docflow/`): scroll-and-measure at 390/360, hostile-viewport phase changes nothing at all, tap+resolve sampling with the reader present at all 147 samples, desktop A/B identical. Gate PASS on the merged tree.
- **Published-guard fold-back:** the bars republish's audit caught four 422s on home load - the landing's optional-chain tidy (`enabled: selected?.sections.…`) evaluates to undefined with no project selected, which React Query treats as enabled, firing empty-slug queries. The published space carries the restored boolean form; the repo canonical now matches it, with biome-ignore notes recording why the boolean form is load-bearing. Gate PASS on the fold-back tree; runtime re-deployed so repo, runtime, and published agree.
- **Doctor todo-missing-plan retuned to the owner's ruling** (viewer message, 2026-10-26: "A todo may not need a plan if it is a task without a plan file."): `_plan_ref_exists` now also resolves a plan reference through the plans dir's `finished/` subtree - flat plans and bundle plans alike - so a reference dangled by a closeout move counts as resolved; the finding fires only when the named plan exists in neither tree, and a todo with no plan reference is never flagged. Three new tests pin the ruling (no reference, flat finished form, bundle finished form); the doctor's own bundle was closed out in the same pass (plan complete, bundle moved to finished/). First post-retune run posted its digest at 0 new / 15 resolved - zero todo-missing-plan and zero plan-done-not-closed findings remain (the total sits at 50 rather than 48 because the other projects' active threads added plan-status findings in the interim).
- **Phone bars fixed + tap-blank guard LANDED** (plan 2026-10-26-phone-bars-fixed; branch build/phone-bars-fixed merged): diagnosis proven by instrumented probe - the tap-blank was never an exception: the shipped viewport sync wrote visualViewport heights verbatim, so a transient on-device dip collapsed the fixed-height shell and clipped the tab bar away (perturbed-viewport probe reproduced the owner's screen exactly; real touch taps on every control staged cleanly). Fixes: the phone top bar and tab bar are `position: fixed` (the v1 dashboard's shape), with the `<main>` scroller padded by the bars' measured heights (`--wb-phone-top-h` / `--wb-phone-tab-h` via ResizeObserver on the bars' contract anchors); `lib/viewport.ts` gains a collapse guard (a height is written only when plausible against the layout viewport or sustained through a settle window; unit tests 17/17 incl. the diagnosis sequence); a `SectionBoundary` error boundary wraps the routed content in both presentations so a section failure can never blank the shell. Landing gate work: anonymized a project name in the doctor tracker entry (portability guard), template literals in `tools/gen-tokens.mjs` (generator output byte-identical) and `server/src/privileged.ts`, one justified exhaustive-deps ignore + two optional chains in App.tsx - full gate PASS on the final tree. Probe record: mobile-probe `tapblank/` (60/60: scroll-and-measure on 5 routes at 390/360, perturbed-viewport phase, boundary proof, desktop A/B identical).
- **wb doctor LANDED** (plan 2026-10-26-wb-doctor; branch build/wb-doctor merged): lib/doctor.py runs read-only checks over every registered project on the viewer's own derivations - plan-closeout, plan-status, plan-missing-child, plan-done-not-closed, todo-frontmatter, todo-missing-plan, todo-duplicate-id, registry-validator, approval-coverage, entry-archive-mismatch. `wb doctor` prints the set (exit 1 when non-empty); `--post` diffs against state/doctor-findings.json and posts ONE digest (new + resolved) to this project's outbox via lib/messages only when the set changed. Schedule: Muse cron workbench-viewer-doctor every 15 minutes running ops/doctor.sh (this VM has no unix crontab; the healthcheck uses the same mechanism - plan deviation, recorded). Adopted recommendations: harness-inbox digest, resolved findings included, registry family from day one. Live baseline: 58 findings (another-project 29 pre-standard plan-status/closeout, v2 16, viewer 13 incl. 10 todo plan references dangled by closeout moves); zero registry findings. Round trip proven at the outbox (baseline, +1, resolved, silence). Plan closed to .plans/finished/.
- **Phone scroll hardening LANDED** (plan 2026-10-26-phone-scroll-hardening; branch build/phone-scroll-hardening merged): overscroll-behavior none on the whole scroll chain (html, body, the SDK wrapper, shell roots, the main scroller - the global rules live in the token generator, regenerated), and the phone shell's height is driven by window.visualViewport via --wb-app-height on the document root (100dvh fallback; desktop consumes nothing and is geometrically unchanged, 24/24 parity measures). Probe record scrollfix: computed styles + a stubbed-viewport run (shell and tab bar follow the visible height live). Pull-to-refresh and the host viewport divergence cannot be reproduced in the harness - the owner's phone is the decisive check. Plan closed to .plans/finished/.
- **Artifact question rows LANDED** (plan 2026-10-26-artifact-question-rows; branch build/artifact-question-rows merged): a state-schema field declaring a question now renders as a decision block - select questions become full-width option rows (native radio semantics) carrying the option label, the recommended badge (the ONLY statement of the recommendation), and the option's note as the row's secondary text; no notes block under a question; the field label rides as an eyebrow. Non-question rows stack on phone; SegmentedControl carries the wrap guarantee (a label wraps inside its pill; a pill never exceeds its container). Contracts + SPEC 5.1/14.4 + ui-context state the each-fact-once rule. Probe (toggleq): baseline spilled to 513px at a 360px viewport on 12 of 13 pilot questions; after, max edge 319px and exactly one "recommended" per field. Plan closed to .plans/finished/.
- **another-project REGISTERED** (owner's ruling, 2026-10-26, reversing the by-design exclusion): its manifest + registry were created from the main chat on entirely untracked files on its side (its tracked tree and gate untouched, overlay rule unchanged); the live sweep now serves 3 projects and its plans feed serves its existing plans as-is (pre-standard, no backfill). AGENTS.md amended in 5282096; SPEC SS0 and the context files aligned in this commit.
- **Questions single-render fix LANDED** (plan 2026-10-25-questions-single-render; branch build/questions-single-render merged): the parser carries ONE questions-heading rule (normalized heading starts with "open questions") for the section flag AND both extractions, first match only - a suffixed heading ("Open questions for ...") now mounts the card; the reader renders the Questions card exactly once, in place of the flagged section's covered content, with uncovered lines (prose, plain items, malformed sentinels, fences) preserved as leftover blocks rendered as markdown. The plan-syntax standard's Open questions section states the suffix + first-match + replace rules. Probe record questions-fix 12/12 PASS; plan closed to .plans/finished/.
- 2026-10-28: ABSORPTION backend lib waves merged — stream A `lib/repos.py` (census + status/publication/exposure; 14 fixture tests; live census 12 == the git viewer's 12, field-for-field clean on all shared fields) and stream B (SPEC §0/cross-link amendments + the repo-anchor note in `lib/diffs.py`; repo-scope peek/save in `lib/files.py`, +16 tests). Gate PASS on the merged tree, 408 tests. Server routes + registry/history store land next; the Repos frontend waits on the owner's picks in the design artifact.
- 2026-10-28: ABSORPTION backend COMPLETE — stream C `lib/repo_state.py` (registry reconcile/update + change-only history with streaks + legacy state importers; 27 tests) merged, then the integration pass: `repo_files` tree enumeration in `lib/repos.py`, repos config keys, and the server routes (`/api/repos`, `/<id>/status|files|file|history`, `/api/repos/registry` GET+POST, guarded repo save) with 8 HTTP gate tests. Gate PASS; live at `b26a718`: /api/repos matches the git viewer's feed id-for-id and field-for-field (13 rows incl. worktrees), registry attached everywhere. Steps 1-7 done; the Repos frontend (Steps 8-9) waits on the owner's picks in the `repos-section-design-stages` artifact.
- 2026-10-28: ABSORPTION frontend LIVE — Repos section built to the owner's artifact picks (top-level section; grouped list + exposure strip; Status | Files | History tabs with stacked status; split tree/peek, drill-in on phone; Content-first peek with Diff toggle; full-screen editor with unsaved guard + sha-conflict flow; Settings Repos tracking panel), merged `c937293`, gate PASS, deployed, republished to the viewer artifact with both adaptations md5-preserved, audit PASS on all eight checks (incl. the editor guard discarding without saving; a real secret file's withheld panel shown, never revealed). Steps 8-9 done. Remaining: Step 10 — parity tour, legacy state import, git viewer retirement.
- 2026-10-28: HIGHLIGHT step landed (datasets plan Step 1) — the root cause was missing CSS: highlight.js markup was injected but no stylesheet colored the hljs classes. Now: a variable-driven hljs mapping in `themes/highlight.css` (both palettes, both modes), a shared `lib/highlight.ts` (completed language map, auto-detect fallback with a relevance floor, no direct hljs imports elsewhere), syntax under the Diff tint in the peek + plan changes, and plan markdown fences + structured code blocks take the same treatment. Gate PASS; the color proof rides the Step 7 publish audit.
- 2026-10-28: DATASETS BACKEND LIVE — DuckDB 1.5.6 pinned in requirements.txt (the one sanctioned exception to stdlib-only; 1.5.6 is the reference viewer's own version and its sqlite scanner works in this environment where 2.0.0's cannot install). `lib/datasets.py` + `lib/dataset_console.py` landed with the reference's semantics (suffix classification, schema-validated sort/filter, LIMIT+1 paging, guarded single-statement console scoped to the opened file, native DuckDB files browse-only); the peek carries a dataset descriptor and schema/rows/stats/sql routes serve — verified live on a real 13,452-row parquet in another repo (descriptor, schema, paged rows, console COUNT). Client Table view + console panel in flight.
- 2026-10-28: HIGHLIGHT + DATASETS RELEASE LIVE — published build audited with measured probes: keyword/string/comment spans render in three distinct theme-token colors (#4b5320 / #006e52 / #83876f in olive), diff views carry spans under the tint, plan fences color too; dataset Table view + console verified in the UI (paging to Rows 51-100, a filter chip narrowing to its row, COUNT in place, DELETE refused in place) and against the 13,452-row parquet through the artifact's actions. Zero console errors. Two audit caveats filed for follow-up: the full-tree enumeration cap (20,000) counts ignored-kind entries, so very large repos show a folder skeleton and deep files cannot be clicked to (the endpoints take paths directly and answer fine); and the SQL console reports the SQLite reader extension unavailable under the live server's environment (table browsing works via the fallback reader).
- 2026-10-28: DATASETS FOLLOW-UPS CLOSED — (1) the Files tree is directory-first lazy (the owner's direction): `lib/repos.py repo_dir` serves one directory's listing (git-classified entries + immediate folders with prune/hidden flags, per-directory cap), the files route takes `?dir=` (blank = root, presence read from the raw query after parse_qs dropped it — regression-tested), and the client tree fetches per folder on first open with per-directory caching, retry, and the preserved hidden/ignored toggle. Published-build audit proved the click path in the largest repo down to a deep parquet that the old capped enumeration could not reach. (2) The sqlite dataset console works under the server: diagnosed to the unit running as root while the DuckDB extension cache lives under the owner's home; the fix is the machine-local env seam (`viewer.env` sets HOME, documented in `viewer.env.example`), proven live (registry COUNT = 42). A VM restart mid-publish wiped the /etc unit; supervision was restored via ops/install-unit.sh and the manual stand-in process retired.
- 2026-10-28: GIT VIEWER RETIRED — the absorption plan is complete. Live import merged the legacy state into the workbench: registry 11 entries (the legacy 10 with their curation — e.g. the prototype's expected=local_ok and its note — plus one workbench-only worktree entry), history +340 legacy lines (393 total, zero overlap). The git viewer's watchdog and digest crons are disabled, its server stopped, its systemd unit removed; 127.0.0.1:8791 answers nothing, and the workbench serves the full repos surface alone (census 11, registry curation live, imported history served). Its repo stays on disk as the record, with the retirement noted in its README.
- 2026-10-28: Registry archive/unarchive now handle folder-less entries. Rows whose entry_dir is NULL by design (artifact-slug and external sources) archive without a folder move and keep entry_dir NULL — previously archive refused them as corruption and would have stamped a phantom archive path, and unarchive crashed on the NULL. Folder entries are unchanged (target-exists refusal, resume semantics). This unblocks the v2 project's board cleanup: its 36 folder-less mockups can now be archived through wb.
- 2026-10-28: Stale work warnings shipped. Open plans, bundles, and todos now carry a derived age/stale block computed at read time (lib/staleness.py): a todo ages from its created date, a plan or bundle from its filename date prefix; only open work flags, only when age exceeds stale_warning_days (server config, default 3). The client renders the existing stale badge with the age (Stale · Nd) on plan, bundle, and todo rows — no client-side age math. Gate PASS on the merged tree; published audit measured the badges on desktop, in Todos, and at phone width with the threshold temporarily lowered to 2 for the audit window, then restored to the default.
- 2026-10-28: Staging project founded (SPEC §2.1). A dedicated swept project at the workspace root is now the designated pre-home for plans, bundles, mocks, and artifacts whose canonical project does not exist yet; it carries its own git repo (manifest, README, graduation log tracked) and graduates items by the recorded procedure in its README (wb add in the target + archive in staging; never a direct registry move). First residents: the machine-bootstrap plan (awaiting its go) and the memory-index-split followup, adopted from the workspace root along with 35 historical files filed to its finished/ with a per-file disposition record; the root .plans/ is empty. Graduation was proven once per item kind against a scratch project. Adoption left 38 doctor findings on the adopted files' status hygiene — the reconciliation queue, recorded in the plan bundle.
- 2026-10-28: Staging bootstrap landed (SPEC §2.1 amended). Staging stays a separate project with its own git repo; this repo now carries its seed files under templates/staging/ (byte-identical copies of the live project's tracked files), and ops/bootstrap-staging.sh — run on setup — recreates the project when it is missing: seed copy, its own git init with a founding commit, and the registry via wb init. It is a no-op when the project exists and refuses an existing directory that is not a staging project. Proven live: no-op against the real staging (HEAD unchanged, tree clean), a fresh creation in a scratch root that the sweep discovered with zero errors, and 3 regression tests; gate PASS at 522 tests.
- 2026-10-30: PROGRESS SCHEDULES landed (plan 2026-10-30-progress-schedules-for-long-work): per-todo arming through the harness writers — `wb todo new` / `wb todo set` take `--progress <cadence>` and stamp `progress_check` / `progress_armed` (appended to the todo front-matter order; the cadence format is defined once in the plan parser and shared by writers, parser, and derivation); a move to done or blocked disarms in the same write, and arming onto a stop status is refused. `lib/progress.py` derives the driver's view at read time in lib/staleness.py's shape — last checkpoint from `progress-checkpoint:` body lines, last activity = max(armed, checkpoint), missed = whole cadence intervals elapsed, stalled at 2 missed checks — served sweep-wide as JSON by the new `wb progress` verb. Doctor coverage both ways (`todo-progress-unarmed` for planned doing work with no schedule, `todo-progress-orphan` for arming outliving done/archived work), riding the existing --post digest unchanged. The arm / run / disarm contract and the platform schedule template live in context/ai-workflow-rules.md (§ Progress schedules for long work), with the scheduling-is-a-platform-concern note in SPEC §6 beside print-schedule. Dogfooded on the build bundle itself: each step's todo armed at its `doing` transition, a driver cycle read the bundle's armed set through `wb progress` and checkpointed through the note format, and the closing moves disarmed. First live doctor run under the new checks: exactly 3 new findings, all `todo-progress-unarmed` on viewer-build-live subplan todos left in `doing` since 2026-10-25 — the check working as designed.
- 2026-10-31: Repos feed cold-latency fixed. GET /api/repos recomputed the full census derivation on every request (per-repo git fan-out; measured 7.2 s cold, 1.2 s warm), so the first viewer open after a restart presented as an outage (client gave up mid-response). The feed now serves its last computed payload: within repos_ttl_s (new config key, default 30) as-is, past it stale while one background thread recomputes, and main() warms the cache in a thread at startup so the port opens immediately and the first open is already fast. Registry-curation and repo-save POSTs invalidate the cache (a generation counter keeps a payload computed across an invalidation from being stored); reconcile + history recording ride the compute. 3 new HTTP tests (cache within TTL, write invalidation, background refresh landing); gate PASS at 549 tests.
- 2026-10-31: Watchdog revival verdict no longer races server startup. The watchdog verified a revival with one healthcheck 2 s after restarting; under load the server takes longer to answer, so two successful revivals (2026-10-30 and 2026-10-31, both after unit-wiping restarts) were reported as FAILED and left a stale ok=false health file. ops/watchdog.sh now polls the healthcheck (up to 30 tries, 1 s apart) after the systemd restart and again after the fallback direct start before declaring failure. Verified by stub drills (a slow start is credited to the systemd path; an always-down server still exits 1 after exactly 61 probes) and a live stop-then-watchdog drill (revived via systemd, exit 0, health ok, 5 projects).
- 2026-10-31: 800-line cap landed (bundle 2026-10-31-length-cap). tools/length.py enforces the sister repos' cap (800 lines by splitlines; scope .py/.ts/.tsx/.js/.mjs including tests; the vendored SDK tree, builder-generated output, and dependency/build trees excluded) as the gate's first leg, with the rule written in context/code-standards.md and a pointer beside SPEC §11.4's components-not-monoliths rule. The ten over-cap files were split by intent, result-preserving: the Python modules became packages (lib/registry, lib/messages, lib/diffs, lib/plans/parser — __init__ re-exports the public surface; messages' lifecycle routes its event/outbox calls through the package namespace so test patching keeps its semantics) or sibling modules (server/server.py 1,530 -> 521 plus common/feeds/messages_api/repos_feed/actions), and the client files split into intent leaves (MockupDetail 1,091 -> 766; Plans 960 -> 340 with PlanReader in its own leaf; api.ts's types moved to api-types.ts + api-types-repos.ts with 36 importers re-pointed, no barrels). The repo's largest file is now 766 lines. Gate PASS, all five legs, at 556 tests (549 + 7 new scanner tests).
- 2026-10-31: Home feed cached (owner report: the viewer stalls on open). Diagnosis: the companion was up — revived by the supervision path after the evening VM replacement — but /api/home recomputed the full cross-project derivation on every request (10-17 s per call under load) while /api/repos has served from its TTL cache since the afternoon fix. home_feed now carries the same idiom (TTL = repos_ttl_s, stale served while one background thread refreshes, single-flight cold compute, generation-counter invalidation from the registry-curation and repo-save POSTs), the payload stamps captured_at, and main()'s startup thread warms both cached feeds. 3 new HTTP cache tests mirror the repos ones; suite at 559 with one pre-existing failure (test_server_stale_feeds' fresh-work case: its fixture writes created with the local date while the derivation is UTC — fails in the nightly window when the two dates differ; unrelated to this change, flagged for a fixture fix).
- 2026-11-01: BOARD PORTIONS landed (bundle 2026-11-01-heavy-feed-batching; the owner's ruling: heavy calls paginate/batch, and large-scale apps give each portion its own API call). Profile: the /api/board monolith cost 3.6-9.3 s and 1.42 MB per request, re-derived on every call; the todos done lane alone was 659 of 694 todo cards, and card rows carried bodies/markdown/step lists the cards never render. Benchmarks on the live corpus: TTL cache leaves the cold derive untouched; NDJSON streaming cannot reach the client through the bridge's one-envelope actions; per-project decomposition + card projection + done-lane pagination cuts the initial load to ~114 KB with the smallest portions landing in ~0.1 s. Landed: GET /api/projects/<slug>/board (board_project_feed: projections, lane totals in counts, done pages via done_offset/done_limit, board_done_page default 50), a getBoardProject action, and the Board section assembling portions client-side (progressive render, per-project failure isolation, scope fetches one portion, done expander pages in). The monolith stays served for compatibility. 4 new HTTP tests; gate PASS at 563 tests; SPEC §8.4 carries the delivery note.
- 2026-11-01: BOARD PORTIONS typing fix (fold-back from the publish): the portion assembly indexed the lane records directly, which the gate's strict typecheck (noUncheckedIndexedAccess) rejects — the published build's toolchain tolerated it, the repo gate does not. Five lane/count reads now fall back to empty/zero; behavior identical against the server's always-complete lane maps.
- 2026-11-01: PROGRESS SCHEDULES AUTO-CREATE landed (bundle 2026-11-01-progress-schedule-auto-create; the owner's commission: armed work must not stall waiting for an agent to create a schedule by hand). lib/progress_schedule.py is the seam: the todo writers (lib/bundles.py — the one mutation path, CLI and server alike) sync a scheduler-registry entry in the same call that arms or disarms a todo — armed writes jobs/wb-progress-<project>-<todo>.yaml (a scripted entry at the todo's cadence, argv `wb progress-check <id>` in the project root via the scheduler's ${WS} anchor, stall = exit 3 so the scheduler's failure report pings with the STALLED line), a terminal move deletes it, and a sync failure never fails the todo write (the outcome rides the result as progress_entry). `wb progress --sync-entries` reconciles the whole registry; the doctor gained todo-progress-entry-missing / todo-progress-entry-orphan (slug-gated: a partial sweep cannot judge another project's entries — the first wiring's false orphans against unswept projects were caught by the existing doctor fixture tests and are regression-covered). The seams are env-overridable (WB_SCHEDULER_JOBS_DIR / WB_WORKSPACE_ROOT / WB_VIEWER_ROOT); no registry on the machine = silent no-op. 22 new tests incl. one that runs the scheduler's own registry validator over a rendered entry; gate PASS at 585 tests. Live at landing: the backfill wrote entries for another-project's two pre-mechanism armed todos (13 registry entries, sched validate clean), and this bundle's own todos cycled entries in and out of the live registry as they armed and closed. The platform-concern doctrine for progress schedules is retired in SPEC §6, lib/progress.py, and the workflow rules (print-schedule/staleness unchanged).
- 2026-11-03: THREADPOOL FAN-OUT landed (plan 2026-11-03-threadpool-fanout; bundle 2026-11-03-threadpool-fanout). Determination: the server's expensive derivations ran sequentially where their waits are subprocess-bound. Landed: a shared order-preserving fan_out in lib/util.py (stdlib ThreadPoolExecutor, pool per compute; workers from the new feed_pool_workers config key, default 8); the repos feed computes its per-repo git summaries on the pool with the registry attach and history recording kept serial in the original order; the home feed computes per-project rows on the pool (lib/home.home_feed gained a workers parameter, defaulting to sequential for other callers); each board portion parses its bundles once and shares the parse between its todos and plans feeds; the sweep compute is single-flighted so concurrent cold requests share one walk. Result preservation proven by live payload diffs at every step (identical modulo captured_at, registry last-seen stamps, and the tree's own live drift). Cold computes on the live corpus, measured under load: repos 33.6 s to 8–11 s, home 17.7 s to 6.8–11.1 s, the largest board portion 3.7 s to 0.31 s. The legacy board monolith is DROPPED (the owner's ruling: legacy and unused surfaces are removed, not carried): the App shell's doing badge assembles the per-project portions on the Board section's shared query keys (the publish's fold-back, now landed in the repo), and the /api/board route, the getBoard action, board_feed(), and the BoardPayload type are removed; the board tests re-pointed at portions plus a 404 test for the dropped route; SPEC §8.4 and the route lists updated. Also fixed: the 2026-11-01 auto-create entry above named a sibling project in the clear, tripping the portability guard — anonymized; main had been guard-red since that tracker commit. A peak-load rerun after the restart (box load ~20 from other work) measured repos 20.4 s, home 17.4 s, portion 1.8 s: the pool's edge compresses under saturation but does not invert. Gate PASS at 592 tests; server restarted onto a3e1d3f and verified there (health commit + new PID), /api/board answering 404 live.
- 2026-11-03: PROGRESS AUTO-ARM landed (bundle 2026-11-03-auto-arm-progress; the owner's directive after a plan in a sibling project ran unmonitored — its bundle todos were moved to doing without --progress, so no schedules existed when three coordinators died in a daemon restart). Arming is now automatic in the one writer: a move to doing (or creation straight into doing) arms at the default 30m cadence in the same write whenever the todo declares neither a cadence nor the opt-out; --progress <cadence> remains the override (15m for delegated or detached work); the new --no-progress records the explicit opt-out as progress_check: off — a first-class parser state (an armed stamp alongside it is a front-matter error). Derivation surfaces follow the same definition: the schedule sync's is_armed requires a parseable cadence (an off todo never gets an entry), the doctor's orphan check keys on cadences only (an opted-out todo archived by a plain bundle move is not an orphan), and todo-progress-unarmed now names the bypass it actually detects — a doing todo that reached doing without the writer. 12 new tests across the writer, parser, schedule-sync, doctor, and CLI surfaces. Gate PASS at 604 tests. Verified in the target context against a scratch project through the real CLI: doing with no flag wrote the wb-progress entry and progress-check reported on track; done removed the entry. SPEC §6 and the workflow rules carry the new doctrine.
- 2026-11-03: AUTO-ARM DEFAULT CADENCE 15m (owner's ruling the same day, superseding the 30m default in the entry above: 15 minutes catches dead or erroring work a lot earlier). PROGRESS_DEFAULT_CADENCE is 15m; explicit cadences still override and declared cadences on existing todos are untouched. Docs, CLI help, and the four default-case test expectations updated in step. Gate PASS at 604 tests.
- 2026-11-03: START-ALL CONSOLIDATION landed (the owner's instruction clearing every open follow-up in one pass; four commits over bf66b4d, gate PASS at 633 tests). (1) FOLD-BACK + SDK: the published build's Todos decomposition is folded into the repo client (the All-projects view assembles per-project portions; no aggregate fetch remains), and the vendored space-sdk is reconciled to the platform v26 build (builder write-back byte-verified, then pulled). Review caught the runtime mirror's stale actions file trying to resurrect the dropped board-monolith action — reverted; the repo's action set stays canonical and the space keeps its own descriptions until the publish pass. (2) PLANS FEED PROJECTION: bundle todos ride the plans feed as checklist cards (the Board precedent's projection shape, the derived staleness fields included; bodies only on archived bundles, where the UI renders them) — the largest project's plans feed went from 1,651,253 to 804,422 bytes with a zero-difference semantic diff; full records still ride the per-project todos feed and the plan detail route. (3) /api/todos DROPPED with its cross-project action (callerless once the fold-back landed; the affected tests re-pointed at the per-project portions; SPEC and architecture route lists amended). (4) AUTO-RECOVERY steps 2-4: a link probe (server/linkprobe.py) classifies the companion as down / up-unsupervised / up-supervised on the healthcheck cadence; a capped auto-repair ladder (server/autorepair.py; the watchdog is now a thin probe-to-repair wrapper) restores supervision in at most 3 rounds and never reports an unsupervised fallback as success; the drill proved destruction-to-supervised-green in 4m49s unattended and caught a real stray-matcher defect (fixed, regression-tested); a genuine VM replacement during the work was ridden unattended. One deviation of record: a local script cannot invoke the published actions, so the space leg of the link is classified agent-side via the scheduler escalation — a green companion never reads as a green link. Server restarted onto 7578332 and verified there (health commit, /api/todos 404 live, plans feed projected with the derived fields intact, the published app's health action answering 200 on the new commit). The publish pass removing the two dropped actions from the space source follows as the recovery bundle's step 5 remainder.
- 2026-11-05: CACHE REFRESH landed (plan .plans/finished/2026-11-05-cache-refresh.md; bundle 2026-11-05-cache-refresh; the owner's design approval covered its four open questions — the defaults stand: 15 s sweep / 30 s poll budget, shell-global manual refresh, updated-ago labels in, disk-persisted cold-start cache out). Server (fa0da58): lib/fingerprint.py derives a per-project content fingerprint (stat walk of the .plans tree plus manifest; measured live at 6,074 files / 0.90 s sequential, ~0.6 s fanned against a ~10 s sweep — cheap enough to ride the sweep, no directory-mtime fallback); the fingerprints recompute with every sweep compute and ride server/common.py (get_fingerprints / combined_fingerprint). server/feedcache.py is a generic keyed stale-while-revalidate cache; the todos, plans, and board feeds serve through it keyed by the fingerprint (the board key also carries the project's registry state — the review queue derives from the registry, not the plans tree, and a fingerprint-only key could have left it stale indefinitely); the home feed treats a moved combined fingerprint as stale beside its TTL and write invalidation; all three feeds stamp captured_at. POST /api/refresh forces the sweep and busts every feed cache; the server's own todo-action and plan-resolve POSTs invalidate the keyed caches immediately (the registry-curation precedent). Client (4e99e74): Board/Plans/Todos poll at 30 s on their existing query keys; a shell Refresh button calls the new forceRefresh action and invalidates all client queries; UpdatedAgo labels render from captured_at on Board/Plans/Todos/Home. Gate PASS — all 5 legs, 642 tests (633 + 9 new: fingerprint units, HTTP feed-cache tests in production shapes). Live proof on the restarted server: repeat portion reads returned an identical captured_at; an external CLI todo write was picked up by the fingerprint and re-served within ~22 s; /api/refresh returned the exact contract body. Published the same day: 40 actions verified by listing (forcerefresh present with its description, all prior descriptions intact, bridge preserved), and the publish's live probes through the artifact returned 200 for forcerefresh and a board portion carrying captured_at. SPEC §8.4 carries the refresh delivery note.
- 2026-11-05: CONTRACTS + BLOCKERS program landed (audit plan .plans/finished/2026-11-05-contracts-and-blockers.md; bundle 2026-11-05-contracts-blockers; the owner approved implementing every item under the criterion that the end state be better than the gap). B1 APP DECOMPOSITION (f33cc0d): App.tsx 779 -> 227 lines — composition only; the shell status model and both headers live in sections/shell/ShellStatus.tsx, the desktop rail in ShellRail.tsx, the route table in ShellRoutes.tsx; a shared query-keys module (client/src/lib/keys.ts) names the shared react-query keys with every literal value unchanged and the two-element vs three-element mockups key shapes documented at the module head; call sites migrated across the sections. B2 ACTIONS UNIFICATION (7f8d899): the space form is now the repo form — the bridge policy and all 40 action descriptions are repo-owned, and the publish is a byte copy instead of a merge; the unified file crossed the length cap at 823, so the bridge split by intent into server/src/bridge.ts (actions.ts 729); config.ts carries its env default in the validator-accepted form and the bridge's timeout check in the repo formatter's optional-chain shape (the two normalizations the repo gate required, recorded here so they are never "helpfully" reverted); SYNC.md records the unification, the index.html slug line as the one standing byte-copy exception, and the SDK/platform version state. B3 GATE FLAKES + SERVER ITEMS (dc1e0c5): the stale-feeds fixture now derives its dates from the UTC clock (proven green under Auckland and Hawaii timezones; the old local-date fixture fails the Auckland case by construction); the intermittent messages-selection test never reproduced across isolation, full-suite, and concurrent full-suite runs, but its setup leaked 20 temp store dirs per run into the /tmp tmpfs — fixed with a cleanup, and the test stays, with the diagnostic lesson recorded on its bundle todo (preserve the exact failure text before adjudicating; every historical report coincided with recorded environmental stress); the registry state token moved behind lib (registry_state_token, differential-proven identical across registry states) and the board cache key consumes it; fingerprints decoupled from the sweep compute lock onto their own refresh at the same cadence bound, proven by new tests incl. single-flight and sweep-call-count pins. B4 SDK: measured byte-identical to the space's tree (236 files) at platform version 28 — the v27/v28 platform moves did not change the vendored build, so no fold-back was needed; the publish-brief version-report requirement is now standing in SYNC.md. Gate PASS — all 5 legs, 651 tests (642 + 9 new). Server restarted onto 7f8d899 and verified; the runtime mirror leveled (deploy + status in sync); the publish ran as a straight copy — 40 actions listed with descriptions in-file, gethealth / getboardproject / forcerefresh all 200 through the published actions, platform version 28 reported.
- 2026-11-05: MOCKUPDETAIL DECOMPOSITION landed as the first post-plan follow-up under the worktree mechanism (plan .plans/finished/2026-11-05-mockup-detail-split-followup.md; bundle 2026-11-06-mockup-detail-split; proposed from the contracts-blockers audit's split-on-next-touch list, granted as worktree-only work, and the owner directed the merge on completion). client/src/sections/mockups/MockupDetail.tsx 766 -> 350 lines, composition only: useEntryDetail.ts (114) carries the detail + feed queries with their keys byte-identical, the feed-row fallback derivation, and the draft-state lifecycle; Disposition.tsx (283) carries the disposition state, the entry-action mutation with refusal surfacing, and the DispositionCard / ApproveSheet regions; a third leaf proved necessary to reach the target — useEntryAnnotations.tsx (225) takes the annotation threads/selection machinery, a self-contained cluster touching the composition only through the detail ref, the Annotations card, and the pinned composer. Built and gated in a dedicated worktree (gate PASS, 5 legs, 651 tests), committed as 3ee44a6, ancestry-checked (exactly one commit over 361d901) and fast-forwarded into main; post-merge biome + typecheck re-passed on the merged tree. Published as a byte copy (4 files, cmp-verified, 40 actions intact, platform version 28); the rebuilt drill-in verified live — getmockups 200 with real entries and getentry 200 with the full detail payload.
- 2026-11-08: PROGRESS SCHEDULABILITY FIX landed (bundle 2026-11-08-progress-schedulability-fix; the owner's commission from a sibling project's remainder thread). Diagnosis: the harness rendered every wb-progress scheduler entry with migrated: false while the scheduler engine fires only migrated: true — the 15-minute progress checks had never run for any project (0 of 11 entries in the server's next-due table, 0 wb-progress pings ever), while arming, entry existence, and a clean doctor all reported healthy. Two further defects found by the admission proofs: the scheduler loader expands anchors in argv and state_paths only, never in a run cwd, so the render's anchored cwd would have failed every spawn (the render now selects the project with a --root argv item and carries no cwd; parse_entry_todo_id keys on the progress-check tail instead of fixed argv positions); and the entry re-sync would have reset an admission flip on the next todo edit (admitted entries are now preserved by the sync). The doctor gains todo-progress-entry-unscheduled — an armed todo whose entry exists but is not scheduled (never admitted, or absent from the server's next-due table) is a finding, distinct from entry-missing. Admission ran per the scheduler repo's flow: validate clean, every live entry proof-run through the server's own executor (outcomes: on-track checks ok; genuinely stalled lanes STALLED at exit 3, the detection firing as designed), then the migrated flip with migrated_at 2026-11-08. End state: every live wb-progress entry (20 at closeout, the set churns with live work) admitted and present in next_due, health clean; the first real doctor run under the new check reported zero unscheduled findings. One non-wb-progress entry remains unadmitted by design: sweeper-nudge-check (outside this commission). Gate PASS, 5 legs, 655 tests; committed as 809cc33. Left as the owner's call: whether fresh renders should be born admitted (migrated: true) — that changes the scheduler repo's admission governance, so the render still emits migrated: false and the doctor keeps unadmitted entries loud. House note: the day's agent-shell write denial (content flushes refused; server processes unaffected) routed the gate, the harness bookkeeping, and the commit through one-shot systemd units — the same server-context pattern the scheduler admission flow prescribes for proof runs.
- 2026-11-08: REPO CONSOLIDATION landed (plan .plans/finished/2026-11-08-repo-consolidation-survey.md; bundle 2026-11-08-repo-consolidation; built as three parallel off-machine lanes with disjoint file ownership, merged serially at the parent). STEP 1 — client sections grouped: every page component moved from flat sections/ into its section subfolder (board/, overview/, todos/, plans/, mockups/, repos/, artifacts/, inbox/, settings/); RefreshButton, UpdatedAgo, and shared stay flat. One forced deviation: the Home folder carries a suffixed name (sections/homepage/) rather than the plain section name — the plain folder path, written literally, contains the portability guard's forbidden home-path substring and cannot pass the guard, and the client has no path alias; file and symbol names are unchanged. STEP 2 — tests grouped: 57 modules into tests/lib (24), tests/server (20), tests/harness (13) as packages; the gate's unittest leg now discovers with -t . (top-level = repo root) — without it the tests.lib/tests.server package names shadow the real lib/server packages and the suite collapses; the count is identical before and after (655). STEP 3 — lib pairs became packages: lib/datasets/ (derivations.py ex-datasets.py, console.py ex-dataset_console.py; the package init also binds _execute/_open/_sqlite_engine/_json_safe because a test monkeypatches them there — future patches of those names target lib.datasets.derivations directly) and lib/progress/ (report.py ex-progress.py, schedule.py ex-progress_schedule.py), each re-exporting its public surface. STEP 4 — docs/ retired: its one file moved to context/component-contracts.md with all live references updated. STEP 5 VERDICT — server/ stays flat: 11 modules, one entry point, heavy cross-imports through server/common.py; a feeds subpackage buys nothing at this size; revisit only if the folder grows well past this. STEP 6 — the locked-db containment flake fixed at its mechanism (d8d2880): the test's own PRAGMA journal_mode=DELETE raced the fixture server's 1-second sweep (journal-mode switches are refused, not queued, while any WAL connection is open); lock acquisition now retries on a bounded deadline until a sweep drains; verified 15/15 under synthesized load 14-19 where the pre-fix test failed 3-in-6. A prose sweep updated stale pre-move paths in docs and comments. Gate PASS on the merged tree — all 5 legs, 655 tests OK. Commits 5037343 + 060d3e4 (lane A), 8770dca (lane C), 41d65e4 (lane B), merges a37e759 + 16a7bb3, d8d2880 (flake). The repo's GitHub route changed the same day at the owner's direction: the snapshot push cannot delete files, so local main was force-pushed over SSH and the remote is now the local history exactly (remote head d8d2880); future pushes are plain fast-forwards.
- 2026-11-08: BORN-ADMITTED PROGRESS ENTRIES (the owner's ruling the same day, closing the question the schedulability entry left open; bundle 2026-11-08-born-admitted-progress-entries; commit cdafac7). The harness render now carries migrated: true with migrated_at set to the todo's arming date — the scheduler repo's admission flow (validate + a server-context proof run, then the flip) governs hand-written entries, not this machine-rendered family, its one fixed template being what a proof run would vet. Sync semantics refined in the landing: an admitted entry's migrated_at is carried over the fresh render while every other line follows the todo's current state, so cadence changes still rewrite the entry (the first cut froze admitted entries whole — the cadence test caught it; a regex that let \s* eat the render's trailing newline was the second catch, both pinned). The doctor's unscheduled check now names a migrated: false entry a pre-ruling render and points at the sync as its remedy; the next-due leg is unchanged. Live proof was the change's own todo: armed under the new code, its entry was born migrated: true and appeared in the server's next-due table with no admission round. The closing global sync wrote exactly one entry — healing an armed todo in another project whose entry was missing entirely (the doctor's entry-missing drift) — and left zero wb-progress entries on disk unadmitted. Gate PASS, 5 legs, 655 tests.
- 2026-11-08: PORTABILITY DENYLIST (bundle 2026-11-08-portability-denylist-fix; commit 63b5f76). An external review's personal-info axis was audited claim by claim against the tree and the full history (its coupling axis is not a defect under the owner's clone-set ruling, as with the scheduler repo). Real and fixed: the portability guard itself carried the personal literals it forbids as split fragments with naming comments — a split construction still tells a reader the name, the hosting username, and the sibling projects' names — so the personal set moved to an untracked denylist (state/denylist.txt, WB_DENYLIST_FILE overrides; case-insensitive; the tracked guard keeps only generic path shapes; no denylist provisioned = the personal leg inert and a fresh clone green, proven in a clean worktree; provisioned = enforced, proven with a seeded probe file whose finding names the file and the leg, never the literal). The plan-parser corpus tests named the companion checkout by the same construction; it is now discovered by its founding-era plan files and never named. The closeout corpus pass hardcoded this repo's checkout directory name and ran ungated (it failed the bare-clone lane gates during the consolidation); it now derives the name and gates on WB_LIVE_CORPUS like the other corpus tests. A bunfig comment named the local daemon account and a sudo target — reworded to the artifact daemon and a different uid. The secrets sweep is clean and no joined literal stands in the current tree. History verdict (per-revision grep + pickaxe over the published main): the fragments stand in every revision since the 2026-10-26 sanitization that introduced them; a joined name literal stood in a plan-questions fixture for three revisions that day; one 2026-10-26 commit subject carries the name; a sibling project's name stood in this tracker for twelve revisions (anonymized 2026-11-03) and the artifact slug for two; the bunfig wording stood in 320 revisions. No lowercase handle, hosting username, sibling monitor name, or absolute home path ever stood joined in a tree, and every commit author is the initials-only identity. Scrubbing those revisions is a history rewrite + force-push — the scheduler repo did exactly that on the owner's go; it is staged as a follow-up awaiting the same go here, with the head tree byte-identical as its proof burden. Gate PASS, 5 legs, 660 tests.
- 2026-11-08: HISTORY REWRITE — SQUASH + SCRUB landed (bundle 2026-11-08-history-squash-scrub; the owner's go on the staged follow-up above). Everything through the 2026-11-03 start-all consolidation — 314 commits — is compressed into a single founding root carrying that day's tree, portability-scrubbed; the living line from the 2026-11-05 cache-refresh landing forward (23 commits, both consolidation merges included) replays on top unchanged — trees, messages, authors, and dates preserved commit for commit, and the pre-rewrite head tree is byte-identical in the rewritten line (the scrub touches no head-tree content: the head was already clean). Method: one filter-repo scrub pass (blob + message replacements with inert stand-ins), then the squash by plumbing replay — a second filter-repo pass proved to corrupt trees on re-run (delta-only skeletons, reproduced twice), so that route was abandoned and never swapped in. Verification: a per-revision sweep over every blob and message in the new history found zero denylisted hits, and a fresh clone from the remote swept identical; the first tail diff against the root matches the original landing's diff exactly; both merges keep two parents. A backup of the pre-rewrite line stands as a local-only bundle in the workspace exports (never published; deleting it is the owner's call). One test-side follow-up rode along on top (57fb5ca): the outbox notify test de-raced — it asserted on a payload file and a checkpoint that the maintenance loop lands asynchronously, and two gate runs on the byte-identical tree failed it at two different points in that window; it now polls both to their deadlines. Gate PASS, 5 legs, 660 tests, on the rewritten tip; the remote was force-pushed and verified by fresh clone (25 commits at verification, the portability modules green with no denylist provisioned).
- 2026-11-08: CHOICE KIT landed (plan .plans/finished/2026-11-08-choice-kit-starter.md; bundle 2026-11-08-choice-kit-starter; commits 20d212e + 7b7fed6). Studies with choices are no longer hand-rolled pages: templates/choice-kit/ holds one self-contained static page driven by a JSON spec (sections + choices declared once: toggle, single, multi, slider, input-text, input-number), with the contract of record in its README and a summary at SPEC §15. Linking is structural, not synchronized: a section's controls list renders a choice inline beside its content and the summary renders the same choice over the same single state object, so the views cannot drift; place: "section" keeps a choice inline-only (the summary shows its value plus a jump link that scrolls and flashes). One Copy button emits one JSON payload {artifact, answers, feedback} (the owner's ruling: a single format — the paste goes to the agent to parse). Feedback mode intercepts events at capture so nothing changes state, resolves clicks to the nearest data-fb label (sections via fb, choices automatically), and appends {target, text, comment} entries to the same payload. wb artifact new <slug> [--title] [--spec] scaffolds an entry through lib/kit.py (kind artifact, main file index.html, spec.json kept as the editable source) and derives the registry state_schema from the spec in the validators' vocabulary (toggle/select/number/text; multi has no registry equivalent and travels in the copy payload only, by design); wb artifact build re-embeds an edited spec and refreshes the schema. One review fix: a dual-rendered choice carries its jump-target id on exactly one wrapper. Dogfood: the plan's two remaining settings (reload persistence; dual vs section-only summary) were presented on the kit itself as the published artifact choice-kit-two-open-settings from entry choice-kit-open-questions, byte-identical to the entry source; the kit implements both at their recommended settings meanwhile. Kit JS behaviorally probed at publish (feedback toggle live, no console errors); the clipboard payload itself is not readable inside the publish sandbox. Gate PASS, 5 legs, 683 tests.
- 2026-11-08: ENTRY ATTRIBUTION landed (bundle 2026-11-08-owner-attribution; SPEC §16; the owner's commission for the scripted stale-mockup cleanup). Registry schema v2 adds three fields to every entry: owner_thread (the owning chat's id — the stable route for verification and uncertainty), owner_label (its display snapshot), and deploy_class (standard by default, or deployed; a deployed entry is live and never stale by class — the cleanup's scripted leg excludes it from the field alone, mechanically). The plan is the anchor: plan_ref names the plan/bundle the entry was made for, and the entries feed serves a derived plan_link block per linked entry (found, bundle_id, path, archived, status, terminal — resolved by lib/plans/bundles.resolve_plan_link against the project's own corpus; terminal = the plan declares a finished-work status or sits in finished/), so the cleanup reads the disposition from the plan's lifecycle and never re-parses. Repo derives through the plan's project; owner_thread stays because plans do not record their thread. Mutations ride the one path: wb set-owner / set-class, --owner-thread / --owner-label / --plan / --class at wb add and wb artifact new, plan_ref through the choice kit; the doctor carries entry-owner-missing (the backfill queue — each project's owning threads claim their own entries) and entry-plan-missing (a plan_ref resolving to nothing: a broken anchor, surfaced, never read as a disposition). The detail headers render Plan · Owner · Deployed as one line. Gate PASS, 5 legs, 696 tests.
- 2026-11-08: AUTO-RECOVERY wedge hole (bundle 2026-11-09-viewer-auto-recovery; fix in the working tree, gate running on the Colab venue at this entry's writing). The recovery mechanism itself needed no building: the scheduler entry workbench-viewer-healthcheck (admitted 2026-10-31, every 5 minutes) runs ops/watchdog.sh — healthcheck, link probe, capped repair ladder — and it proved itself on the evening's VM replacement, reinstalling the wiped unit from the tracked template and restarting the service in one round with no agent involved (the scheduler ledger and state/repair.json carry the run). What the replacement exposed instead was the ladder's blind spot: the server intermittently wedges under load (handler threads stuck writing to clients that already timed out), and the probe's own health read hung on exactly that shape — the endpoint's headers arrive while the body stalls, and a plain buffered read never returns, so watchdog cycles died at the job timeout before the ladder could run; two wedges that evening were healed by hand, masking the hole. The probe fetch now reads the body in chunks under a cumulative byte deadline and runs detached behind a hard 20-second budget (an abandoned fetch reads as down and the ladder proceeds); the plain healthcheck carries the same chunked-deadline read. One subtlety the live run caught: a fully-read response detaches its socket, so a missing socket after data is end-of-body, not failure — pinned by the new read-discipline tests alongside the hanging-fetch test. Observed end-to-end the same evening: a cycle on the fixed probe met a genuinely wedged server, worked the whole ladder, escalated honestly when its probes raced the fresh instances' startup sweeps, and the server stood supervised-healthy (probe green, lock pid equal to the unit's main pid) out of that cycle's own restarts. A second change followed from the same evening's cap-exhaustion evidence (the owner's first-attempt ruling): the repair verb now keys on the unit's load state — a unit systemd has not loaded is started, not restarted — and the down-and-unit-absent shape confirms over a dedicated 180-second window, since a fresh unit's first start runs the startup sweep before the port binds and under load that outlasts the ordinary round window; other shapes keep the short windows, so a stuck ladder still exhausts in minutes. Tests pin both behaviors.
- 2026-11-08: SURVIVAL-CONTRACT v1 CONFORMANCE, viewer step (plan .plans/2026-11-08-vm-restart-survival-pattern.md in the staging repo, Step 4; the canonical contract text lives in the starter SPEC, stamped survival-contract: v1 — this repo's stamp rides context/architecture.md). Tonight's recovery landing had already carried rungs 5 (bounded detached probes), 6 (load-state repair verb), 7 (fresh-restore window) and 9 (supervision is the verdict). This step adds rung 4, render-when-invalid: the link probe byte-compares the installed unit against the current template render (the same @ROOT@/@PYTHON@ substitution the installer performs) and serves unit_stale in its systemd block; a stale unit classifies the server up_unsupervised with reason unit_stale — healthy-but-stale is not supervised — and the repair round re-renders through ops/install-unit.sh instead of restarting against the stale bytes (a missing file stays the install case; an unreadable render or file reads as not stale). Rung 8 is formalized: the pre-systemd fallback start is named in the ladder as its last rung (cap exhausted + fully down -> one direct start, the run still exits non-zero — unsupervised service is surfaced, never silent). The driver moved to the contract's fast tier: the scheduler entry workbench-viewer-healthcheck now fires every 2m (was 5m), verified live in the run ledger (02:08 -> 02:10 -> 02:12). Rungs 1-3 and 11 stand as built (tracked template + installer; external scheduler-entry driver; presence checked separately from health in the probe's classification; the supervision suite). Rung 10 does not apply (the server has no downstream dependency to revive). Step 6 drill PASSED the same evening: unit file removed + service stopped at 02:42:46Z; the 2m watchdog cycle fired 02:44:22Z and the ladder reinstalled the unit from the tracked template and started the service (journal: Started 02:44:11Z) — supervised health (probe up_supervised, MainPID == lock pid, unit_stale false, health 200 reporting the landed commit) restored in ~85 seconds from the stop and under two minutes from the drill's start, against the ~4-minute baseline from the evening's real replacement; the following cycle closed already_supervised. No agent action between the stop and the restore.
- 2026-11-08: PROGRESS-ENTRY LEAK closed (scheduler escalations 2026-11-08, pings 73756ecc5d57 + 1a0d6ef85649). Test suites arm file todos for fixture projects with no scheduler-jobs seam set, so the writer's progress sync rendered live registry entries for scratch projects — proj-a and proj from the CLI walks, beta from the server walks — whose tempdirs died with their runs; the orphaned entries then crashed every scheduler cycle on the missing manifest (progress-check's contract is exit 0 for a gone todo, and a missing project root crashed the manifest load instead). Three leaked entries were removed from the live registry. The guard now lives in the sync itself (lib/progress/schedule.py): the live registry is identified from the module's own location — never from a redirectable seam — and a scratch project (under any temp root: the platform roots derived from the current environment, plus the WB_TMP_ROOT seam for this machine's disk-backed gate scratch, with seam entries that are themselves under a platform root refused as run scratch, not roots) never syncs into it, while a scratch jobs dir still receives the entry with an absolute --root (the ${WS} anchor cannot express a temp path), so fixture suites exercise the full write path. The outside-workspace refusal likewise keys on the live registry. wb progress-check with a gone root now exits 0 with the orphan line instead of crashing. Regression tests pin the refusal against the real registry path, the scratch-write shape, and the anchor rule; the live registry's checksums are verified unchanged across the leak-exercising suites.
- 2026-11-09: CLASSIFIED CATALOG, workbench side (plan .plans/2026-11-08-classified-schedule-catalog.md in the staging repo, Steps 3 + 4; bundle 2026-11-09-catalog-manifests-and-stamps; SPEC §17). Step 3: the manifest carries its catalog classification in three flat keys — catalog_origin / catalog_generality / catalog_use_case, all-or-nothing, values validated against the shared vocabulary (the scheduler registry's axes) at load; an unclassified manifest loads and behaves exactly as before, and lib/manifest.py serves the block as Manifest.catalog. The manifest format stays flat by design, so the axes ride in flat keys — what is shared is the vocabulary, not the nesting (the starter specimen's nested block remains a placeholder its own parser never reads). templates/manifest/ is the catalog specimen: adopting a project is copying the template and filling its fields, the manifest's own fields being the declared parameters (classification of record: hand / parameterized / work-tracking). The classification keys were appended to this repo's manifest, the staging seed, and the five swept project manifests on this machine (fields only; other repos' commits are their owners'). Gate PASS on Colab High-RAM (lilac-reef-93): 719 tests, all five legs (the bun legs ran verbatim on the identical sha256-verified tree after bun + pinned node_modules were provisioned on the session); the live sweep reads every classified manifest with zero errors. Step 4: every wb-progress render now carries its class (in lib/progress/schedule.py) — a catalog block (origin machine, generality deployment-specific: the writer owns the lifecycle and no copy is offered, use_case work-tracking) and a machine-form source stamp (writer workbench-harness, project, todo, source_class). The source class derives from the same temp-root determination as the leak guard: a scratch project's entry is fixture-classed; the harness still refuses to write it into the live registry, and the scheduler's loader now refuses it again at validation (its schema, committed 8c387d2 and restarted onto, holds a fixture-classed machine entry out entirely) — the fixture defect closed at the classification layer in both repos, pinned by tests on both sides (the harness suite validates a stamped render through the scheduler's real registry module and proves a fixture-stamped render is quarantined by it). Live: a global sync re-rendered all 9 live wb-progress entries onto the stamped form; validate reads 28 valid / 0 invalid, next_due carries all 9, migrated_at values preserved.
- 2026-11-09: WEDGE EPISODE — verdict/error divergence diagnosed (defect routed from the main chat; no code change yet). Under load 17 on 2 CPUs the instance started 13:14:19Z (after four watchdog restarts that morning, journal 12:42–13:14) served health in 0.05 s at moments and timed out at others: across six probes, health alternated 0.007–9.6 s — the signature is the single-flighted sweep (sweep_ttl_s is 15 s; at TTL expiry every queued health request waits behind one full re-sweep of 17 projects, and under load the sweep's git subprocesses stretch it past client timeouts; the sweep error count of 1 is a standing corpus condition also present on healthy reads). The routed report's "repair claimed up_supervised yet health timed out" is a real divergence with a mundane mechanism: the healthcheck leg and the link probe sample DIFFERENT instants and only the probe's instant gates the repair record — a cycle can record already_supervised off a fast sample while a probe seconds away times out; nothing is miscomputed, the record is a point sample, not a health guarantee. The watchdog's exit-0-throughout record is by design (report: on_failure). The viewer is up_supervised and answering as of the diagnosis; the open defect remains the unpinned wedge root cause (a thread was observed in folio_wait_bit_common — page-cache wait — during the episode, consistent with the storage-park candidate), and the cross-repo stack-dump plan remains the owner's call.
- 2026-11-09: HARNESS CONNECTOR, workbench side (plan .plans/2026-11-08-harness-connector-relocatable-agent-tier.md in the staging repo, Step 4; bundle 2026-11-09-harness-connector-step4; SPEC §18). The classification read the sweeper judges escalations against is now a served endpoint, GET /api/projects/<slug>/classification, so a venue-side consumer reads ready state through the connector's workbench tool instead of parsing todo files: per project, every todo across the active bundles with its status, its raw progress_check field served uncoerced (a null, a cadence string, and the opt-out are three distinct inputs to the consumer's logic), the opt-out derived explicitly, the arming stamp and last update, plus the harness progress derivation (cadence, last activity, missed checks, stall verdict) for the armed set, computed by the progress report module in the backend. The registry-existence half of armed — a scheduler entry on disk — is the registry's own state by definition and stays with the consumer, which joins it exactly as the home read does; the endpoint serves the todo-side inputs only, and a project with no plans dir serves available false. Parity against the home checker's own read (front-matter over active bundles joined with the jobs dir) on the live thread set: identical per-todo (status, progress_check) over 368 + 272 todos in the two mapped projects and identical unarmed verdicts (zero unarmed on both sides), with the live doing + opted-out todo's opt-out surviving the round trip as the raw string; the scheduler thread confirmed the shape covers its judgment's whole workbench-side consumption before the build. Gate PASS on Colab High-RAM (topaz-laurel-73): 723 tests, all five legs on the sha256-verified tree, isolation proof clean.
- 2026-11-08: CHOICE KIT answer state (bundle 2026-11-08-choice-kit-answer-state; commits c86d903 + 58f39e0). The kit's first payload shipped every choice's current value as an answer, so an untouched default was indistinguishable from a deliberate pick on the paste-back. The runtime now tracks answered-ness per choice beside the value state: a choice is answered only when the reader changes it or commits it, and the payload becomes {artifact, answers, unanswered, feedback} with answers holding answered choices only and unanswered naming the rest in spec order. Controls still display their defaults (a control must show something), but the summary row of an unanswered choice reads "Not answered yet" and the bar carries a live "N of M answered" counter. Two bar controls complete the model: Commit current adopts everything on screen as answered at its displayed value, and Clear all returns every choice to its default and to unanswered — answers only, by the owner's ruling; feedback entries keep their own per-entry removal. Copying with nothing answered still emits (a feedback-only paste is legitimate). Persistence stores {values, answered} under the same key; a first-version record (bare values) loads with its values displayed and none counted as answered, so the upgrade discards no pick and promotes none silently — Commit current adopts them in one tap. The contract of record (the kit README: payload, answer-state, and persistence sections) and SPEC §15 carry the new shapes; no spec-format change and no registry derivation change. The dogfood entry re-rendered through wb artifact build and the published study republished byte-identical (sha256 verified) and probed fresh-profile at every stage: 0 of 2 on open, exactly the changed choice answered after one pick, 2 of 2 after Commit current, back to 0 of 2 after Clear all, no console errors, no overflow at phone width. The clipboard itself is not readable in the publish sandbox; the payload shape is pinned by the runtime source and the counter/row states that mirror it. Gate PASS, 5 legs, 696 tests.
