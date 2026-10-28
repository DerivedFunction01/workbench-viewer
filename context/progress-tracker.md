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
