# UI Context

The viewer's design fundamentals, as approved by the owner
(2026-10-25, with amendments). Normative sources: SPEC §11
(the fundamentals as spec) and the design record
`2026-10-25-workbench-viewer-fundamentals.md`
(full token tables, contrast ratios, rationale). Every value
below traces to one of those two. Component contracts
(props / variants / states per component) land in build
Subplan 04; this file is the styling reference a fresh
session styles a component from.

## Theme system — modes × palettes

Two independent axes, both persisted UI preferences:

- **Modes:** dark (design-led) + light (full peer), both
  descended from the dashboard classic token sets — dark
  surfaces `#171912 / #21241b / #2a2e21`; light `#edeee3 /
  #f7f7ee / #e4e5d3`. Default follows the OS; an in-app
  Auto / Dark / Light toggle overrides it. Mockup preview
  wells carry their own light/dark toggle per frame — a
  mock is judged in the mode it was designed in.
- **Palettes:** a palette is a selectable token-set variant
  over the same semantic roles (below) — it changes the
  accent and surface family as one coherent set. **Olive
  is the DEFAULT palette** (`--wb-accent` `#4b5320` light /
  `#9db45c` dark), not the only one. **Palette #2 is TEAL**
  (SPEC §13, resolution 4), descended from the git viewer's
  shipped, verified teal token set — values adapted and
  contrast-verified in build Subplan 02, not invented
  fresh. Further palettes are added as theme files under
  the same contract.

What never varies by palette:

- The status system — Okabe–Ito hues, one per ruled status,
  always dot + glyph + word (see Status system below).
- The ruled = filled-chip vs derived = outline-badge shape
  split.
- The contrast discipline: every palette must pass the
  same contrast verification in both modes before it ships
  (strong-tone chip text on a 14% hue tint; raw bright hues
  only for dot/glyph/border, never small text in light).
- Danger red is reserved for errors and destructive
  actions in all palettes — never a status chip.

## Tokens

- Names are `--wb-<category>-<role>` CSS custom properties
  in three tiers with one-way references:
  - **Tier 1 — primitives:** raw ramps (`--wb-olive-500`,
    `--wb-okabe-blue`, `--wb-space-16`). Never referenced
    by components.
  - **Tier 2 — semantic:** the roles components use
    (`--wb-surface-1`, `--wb-content-secondary`,
    `--wb-status-canonical`). A theme = a re-pointing of
    Tier 2.
  - **Tier 3 — component:** scoped aliases where a
    component needs its own knob (`--wb-chip-radius`,
    `--wb-lane-bg`). Kept few.
- **Source of truth: `tokens/tokens.json`** in DTCG format
  (`$value`/`$type`, alias references). Style Dictionary
  is NOT adopted — a small generator in the build produces
  the CSS from it. All components use tokens; no hardcoded
  values anywhere.

### Semantic color tokens (Tier 2, olive palette)

| Token | Light | Dark | Role |
|---|---|---|---|
| `--wb-surface-canvas` | `#edeee3` | `#101208` | App floor |
| `--wb-surface-1` | `#f7f7ee` | `#171912` | Panels, rail, lane bodies |
| `--wb-surface-2` | `#ffffff` | `#21241b` | Cards, frames, rows |
| `--wb-surface-3` | `#ffffff` | `#2a2e21` | Overlays, menus, sheets (light adds shadow) |
| `--wb-surface-sunken` | `#e4e5d3` | `#12140c` | Preview wells, lane recess, code blocks |
| `--wb-content-primary` | `#22251a` | `#eceeda` | Body text (14.5:1 / 14.2:1 on surface-1) |
| `--wb-content-secondary` | `#5c604e` | `#a9ad97` | Meta, labels (6.0:1 / 7.3:1) |
| `--wb-content-muted` | `#83876f` | `#82856f` | Timestamps, hints — meta only, never essential content alone (3.4:1 / 4.4:1) |
| `--wb-border-default` | `#c9cbb4` | `#3a3e2e` | Hairlines, card borders |
| `--wb-border-strong` | `#a9ac8f` | `#4c5138` | Hover borders, dividers that must read |
| `--wb-accent` | `#4b5320` | `#9db45c` | Interactive accent: links, selected, primary buttons |
| `--wb-accent-hover` | `#40491b` | `#aabd72` | |
| `--wb-on-accent` | `#ffffff` | `#15170f` | Text on accent (8.2:1 / 7.9:1) |
| `--wb-focus-ring` | = accent | = accent | The one focus ring (2px, offset 1px) |
| `--wb-danger` | `#b03a22` | `#e07a5f` | Form errors + destructive actions ONLY |
| `--wb-unknown` | `#5b6b7a` | `#93a7ba` | "Unknown" scan states |

### Status system (constant across palettes)

Ruled statuses take Okabe–Ito hues — no two confusable
under protanopia, deuteranopia, or tritanopia. Every status
renders **hue + glyph + word**; color is never the only
signal. Ruled statuses are **filled chips** (14% hue tint,
strong-tone text); derived and review states are **outline
badges** (transparent fill, hue border, strong-tone text) —
the ruled/derived split is visible in the shape before a
word is read.

| Ruled status | Hue (dot/glyph) | Chip text light | Chip text dark | Glyph |
|---|---|---|---|---|
| `canonical` | `#0072B2` blue | `#005f94` (5.2:1) | `#56B4E9` (5.6:1) | ◆ diamond |
| `implemented` | `#009E73` bluish green | `#006e52` | `#45c493` (6.4:1) | ✓ check |
| `deferred` | neutral (= content-secondary) | `#5c604e` | `#a9ad97` | ❚❚ pause |
| `unexplored` | `#CC79A7` reddish purple | `#9c4580` (4.8:1) | `#d79bc0` (6.1:1) | ? in circle |
| `hard-gate` | `#D55E00` vermilion | `#a63f00` (5.0:1) | `#f0854c` (5.6:1) | ⬢ octagon + gate name |
| `abandoned` | `#6f7263` gray-olive | `#5f6252` (4.9:1) | `#9a9d8c` (5.2:1) | ✕ cross; dashed chip border, dimmed |

Derived + review states (outline badges):

| State | Tone | Glyph | Rendering rule |
|---|---|---|---|
| Stale (derived) | orange `#E69F00`; text `#7d5200` light / `#e8a33d` dark | clock | Badge text carries reason + magnitude: "Stale · 23d unverified" or "Stale · drift". Never a bare dot. |
| Approval not covered (derived) | vermilion family (hard-gate tones) | ⚠ triangle | "Approval doesn't cover current state" — appears the moment state changes after approval. |
| Needs changes (review) | orange `#D97706`; text `#96500a` / `#f5a623` | ↩ return arrow | Word + open-comment count: "Needs changes · 2 open". Different glyph/word from Stale. |
| Approved for state (review) | implemented green (filled chip) | ✓ | Followed by the state hash in mono: "Approved · state a3f9c1". |
| In triage (review queue) | canonical blue tones, outline form | inbox tray | Marks entries awaiting a first disposition. |

Chart/diagram series (Mermaid): Okabe–Ito in canonical
order — `#0072B2, #E69F00, #009E73, #D55E00, #56B4E9,
#CC79A7, #F0E442` (yellow fills only, never text).

## Themes-folder organization

The generated CSS ships as a `themes/` folder under
`viewer/client/src/`: an entry CSS file that `@import`s
one file per palette theme, each scoped to its root
selector (e.g. `[data-palette="olive"]`) with mode variants
inside. The files are generated from `tokens/tokens.json`
and checked in; the generator is part of the build. This
works on this workspace's artifact stack (proven by the
git viewer's `theme.css` on the same Tailwind v4 build):
local `@import`s are inlined at BUILD time into the single
output stylesheet, so the bundle stays self-contained;
`@import`s sit at the top of the entry file; fonts are
bundled woff2 via local `@font-face`, never a URL import;
theme switching is selector switching over the one shipped
bundle — never a runtime stylesheet swap or fetch.

**Fallback:** if the build proof ever shows imports not
inlined (or import order breaking the Tailwind cascade),
the organization reverts to one generated `theme.css` —
same tokens, same multi-palette provision.

## Typography

- **UI font: Inter** (variable, weights 400–700, bundled
  woff2, SIL OFL 1.1) — `tnum` tabular figures for data,
  `zero` slashed zero in code contexts. Fallback stack:
  `Inter, system-ui, -apple-system, "Segoe UI", Roboto,
  sans-serif`.
- **Mono font: IBM Plex Mono** (400/500/600, bundled woff2,
  SIL OFL 1.1) — codes, slugs, hashes, paths, timestamps
  only; never friendly names or sentences.
- **Type scale** (house scale): 12/16, 14/20, 16/24, 18/28,
  20/28, 24/32 (px size/leading). View title 20 semibold,
  tracking −0.011em; section heads 12 semibold uppercase,
  letter-spacing 0.06em, content-secondary; body 14; plan
  reading body 16/28 at a 68ch measure; meta 12 muted; card
  titles 14 semibold; big numbers 20–24 semibold with
  `tnum`.
- Every aligned number renders with
  `font-feature-settings: "tnum"` via the `.num` utility.
  Dates render `Mon D, YYYY` absolute; relative phrasing
  only alongside.

## Spacing, radius, density, elevation, motion

- **Spacing:** `{4, 8, 12, 16, 24, 32}`
  (`--wb-space-4/8/12/16/24/32`). Card padding 16; panel
  padding 24; section gaps 24; page padding 24.
- **Radius:** `--wb-radius-sm: 6px` (controls — buttons,
  inputs, tooltips), `--wb-radius-md: 10px` (cards,
  storyboard frames), `--wb-radius-lg: 12px` (panels,
  lanes, sheets), `--wb-radius-pill: 9999px` (chips; dots
  are round, 8px).
- **Density:** two densities, one toggle. Comfortable
  (default): list rows 40px. Compact: data rows 32px,
  tighter card padding (12). Interactive targets NEVER
  shrink: ≥38px, ≥44px on coarse pointers, in both
  densities.
- **Canvas:** max width 1600px; the Board is the one
  surface allowed to exceed it (lanes scroll internally).
- **Elevation:** surface ladder + 1px border, not shadow.
  Only shadows: light-theme overlay `0 8px 24px
  rgb(34 37 26 / 0.14)` and its dark peer `0 8px 24px
  rgb(0 0 0 / 0.45)`, on surface-3 menus/sheets.
- **Motion:** pop 160ms, sheet 200ms, panel 160ms,
  ease-out; nothing else animates;
  `prefers-reduced-motion` disables all of it.
- **Scrollbars:** one thin global rule in the themes CSS
  (`scrollbar-color: border transparent`, 8px) — never
  styled per-component.

## Layout — shell + the four views

**Shell (all views):** rail + top-bar on a 1600px canvas.
Left rail 232px on surface-1 — project switcher at top
(sweep list, per-project status dot: ok / degraded /
manifest-only), section nav with live count badges (Triage
count on Mockups, Doing count on Board), server health dot
+ "editing on/off" at the rail foot. Top bar 48px:
breadcrumb (Project / Section / Item), global search,
density toggle, theme toggle (mode + palette). Content max
1600px, padding 24. Below ~900px the rail collapses to a
top strip (sections as pills) — desktop-first, never broken
on a phone. Deep links are routes (`#/p/<project>/mockups/
<slug>`, `#/p/<project>/plans/<file>`, `#/board`); unknown
routes land on the default view, never a blank.

### Mockups

- **Storyboard grid:** frames at a minimum 300px width,
  `auto-fill` grid, gap 16, + **contact-sheet mode** (a grid
  toggle expands an entry into all featured states as
  mini-frames side by side; variants are states, never
  duplicate entries). Toolbar: ruled-status filter chips
  (multi-toggle), Triage-only toggle, Archive toggle (off
  by default), sort (recently changed / oldest unverified).
  Frame anatomy: sunken preview well rendering the mock in
  ITS OWN theme tokens at a labeled viewport; variant strip
  of chips under the well; footer = ruled status chip +
  derived badges + review badge. Archived frames render at
  60% saturation with their ruled chip intact.
- **Drill-in:** two columns — preview well (7fr, sticky)
  with the per-frame light/dark toggle and viewport label;
  right rail (5fr): metadata table, State panel (schema
  controls), Approval panel (approved state as a frozen
  snapshot: values table + state hash in mono + who/when),
  Disposition bar (always in the same place, under the
  preview), Review log, History.
- Review flow: Board Review lane / Mockups Triage toggle →
  open entry → set state in the State panel → preview
  re-renders live → Approve (confirm sheet shows the state
  snapshot: values + hash → ruling note → saved) /
  Needs changes (comment required) / Mark stale (optional
  comment). The entry leaves the triage queue only when no
  unaddressed needs-changes comment remains.

### Plans

Reading view. Left list rail (280px, surface-1): plans
grouped by header Status (In progress / Draft / Finished
collapsed); each row = title + status chip + step count.
Non-conforming plans carry a "source format" tag in the
list. Reading pane (surface-2 card, 68ch measure):
structured header card (Status / Created / Parent /
Rulings as a field table), then the body as structured
blocks — steps as numbered blocks with labeled files /
verify / done-when sub-blocks (mono for file lists),
rulings as a bordered blockquote band. Mermaid fences
render as diagrams in a sunken frame; a broken diagram
renders its source in a code block with a one-line note.
A "Raw" toggle swaps the pane to the source view
(highlight.js, token theme). Non-conforming plans render
whole as formatted markdown under a slim "source format"
banner — content is never dropped.

### Todos

A list, not cards: rows (checkbox with 38px target, title,
project tag chip, link chips to plan/mockup, status word).
Segmented control: This project / All projects. Inline add
row at the top (title + Enter); completed group collapsed
at the foot with a count.

### Board

Lanes left→right: **Review queue** (first, fixed, accent
left edge), **To do**, **Doing**, **Done** (collapsed to a
count strip when > 12 cards, expand on click). Lane
headers carry counts; Doing shows a soft warning tone on
its count above 7 (display only). Cards 264px wide,
surface-2, radius-md: top row = source glyph (todo ✓-box /
plan ❑ / review inbox) + project tag; title (2-line clamp);
footer = the source's own meta (todo: due/link icons; plan:
step count "3/8 steps"; review: status chip + stale badge).
ONLY todo cards show a drag handle and drag — a drag is
one todo-status mutation via lib/. Plan and review cards
are derived/read-only: no handle, a small "derived" tag,
click opens the source. The board scrolls horizontally
INSIDE its surface; the page never scrolls sideways.

## Component conventions

The kit is hand-built from tokens — one component per
concept and file; no component library, no CSS-in-JS.
Component libraries and Storybook are NOT adopted
(Storybook's stories/Controls patterns are). Full
contracts — typed props, variants × states appearance
tables — are written in build Subplan 04 before any
component is coded; the standing rules here bind that work:

- **Design fundamentals first:** every component's
  appearance is specified per variant × per state (in
  tokens) before it is coded. Button is the canonical
  example: variants (primary / secondary / danger / ghost)
  × states (default / hover / active / focus-visible /
  disabled). A button state invented during coding is a
  defect.
- **Props contracts:** typed props; data in via props,
  events out; components never fetch. Sections compose the
  kit and own no private chrome.
- **Buttons from ONE shared kit;** sections never hand-roll
  one. 6px radius, ≥38px target. Primary = accent fill +
  on-accent text; secondary = surface-2 + border-strong.
  Icon-only at rest (with tooltip + aria-label) for row
  actions; destructive and disposition actions ALWAYS carry
  full text — a ruling action is consequential.
- **Chips (ruled status):** pill, 24px tall, 8px dot +
  glyph + one word, filled tint. Truncate, never wrap.
  Filter chips are toggle buttons with `aria-pressed`.
- **Badges (derived/review):** pill, outline form, glyph +
  word + magnitude. A badge without its word is a defect.
- **Cards:** surface-2, radius-md, 1px border-default,
  padding 16. No shadow in dark; light cards sit on
  surface-1 panels so the ladder reads.
- **Lanes:** surface-1 body with sunken inner well,
  radius-lg; header = 12px uppercase section head + count
  chip.
- **Tables/lists:** columns in field order, friendly
  headers (label map, humanize fallback, never raw
  snake_case); row hover = surface-1; selected row =
  accent left bar 2px.
- **State controls:** rendered FROM the entry's declared
  state schema — one row per state key: label, control
  (switch for booleans, segmented for enums, slider/stepper
  for numbers), current value. Switch = pill track, accent
  when on. Controls live in a labeled panel, never
  scattered over the preview. A key whose spec declares a
  question renders as a decision block instead: eyebrow
  label, prompt, and — for a select — full-width option
  rows carrying the recommended badge and the option's
  explanation inside the row, each fact stated once
  (contract: docs/component-contracts.md#statecontrols).
- **Empty states:** empty is a state, not an error — a
  sunken well, one line ("No mockups match these filters",
  "Nothing awaiting review"), styled as content. Error
  states name the section + the recovery in one sentence,
  once.
- **Tooltips:** the `data-tip` mechanism (kit, delayed,
  token-styled) — no native `title`, no second system.
- **Skeletons:** surface-2 blocks at the content's real
  shape, shown while a project's feed loads — one project's
  skeleton never blocks another's content.

**React discipline:** React 19 + Tailwind CSS v4;
`marked` + DOMPurify (degraded-plan rendering only);
`mermaid` ^11, lazy chunk, `securityLevel: 'strict'`,
token-themed; `highlight.js` lazy for source view, styled
from tokens only. Dependencies are bundled at build time
(see the standing constraints).

## Standing constraints (functional, not design)

These bind whatever is built on the fundamentals above:

- **Status distinctness:** the status vocabulary is fixed
  (canonical / implemented / deferred / unexplored /
  hard-gate / abandoned); each ruled status renders
  DISTINCTLY (its own Okabe–Ito hue + glyph + word, filled
  chip), and derived staleness renders as a badge beside
  the status — never as a status.
- **Self-contained artifact:** the artifact is fully
  self-contained — everything it needs ships with its
  build; nothing is fetched from a CDN at runtime. Fonts
  are files in the bundle, not links; mermaid and
  highlight.js are chunks in the bundle; the only network
  the page ever touches is its own server socket (the
  privileged raw-socket bridge — see architecture.md).
