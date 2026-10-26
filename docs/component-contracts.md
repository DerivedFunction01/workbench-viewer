# Component Contracts — the kit (Subplan 04)

Status: contracts BEFORE code (Subplan 04, Step 1). Every
component the sections (Subplans 06–07) and the shell
(Subplan 05) may use is specified here first: purpose,
typed props, variants, states, and an appearance matrix —
variant × state, every cell named in generated token names
(`--wb-*`, from `tokens/tokens.json` via the generated
themes CSS: `viewer/client/src/themes/index.css` +
`<palette>.css`). If a component needs a token that does
not exist, that is a blocker reported against this doc —
components never invent values.

Path note: the parent task for Subplan 04 froze this doc
at `docs/component-contracts.md`; it supersedes the
`viewer/COMPONENTS.md` placeholder path named in the
frozen layout sketch.

## Cross-cutting rules (decided once, binding on all)

- **Props in, events out.** Components are pure: typed
  props only, callbacks for events, NEVER a fetch, never
  an import of a section or the shell. Composition flows
  downward only: shell → sections → kit.
- **Token-only styling.** Tailwind utilities +
  `var(--wb-*)` references only. No hex/rgb literals, no
  component CSS files, no CSS-in-JS. Tailwind spacing
  utilities are used ONLY where they equal a `--wb-space-*`
  step 1:1 (`p-1`=4, `p-2`=8, `p-3`=12, `p-4`=16, `p-6`=24,
  `p-8`=32); every color, radius, shadow, and token-scoped
  size is a `var(--wb-*)` arbitrary value.
- **Focus ring (one treatment, everywhere):** 2px solid
  `var(--wb-focus-ring)`, offset 1px, on `:focus-visible`
  only. No component invents a second ring.
- **Disabled treatment (one treatment):** native
  `disabled` (buttons/inputs) or `aria-disabled` +
  non-interactive rendering; visual = `opacity: 0.55`,
  no hover/active change, `cursor: not-allowed` where a
  cursor applies.
- **Targets:** interactive elements are ≥38px tall in
  BOTH densities (≥44px on coarse pointers,
  `@media (pointer: coarse)`); density changes
  `--wb-row-height` and paddings, never target floors.
  The 38px/44px floors are SPEC §11 / ui-context values;
  no `--wb-*` token exists for them, so they appear as
  `min-h-[38px]` / coarse `min-h-[44px]` utilities —
  the only non-token size literals allowed in the kit.
- **Scrollbars:** the ONE thin global rule already lives
  in the generated themes CSS (`scrollbar-color` /
  `scrollbar-width` on `:root`). NO component styles a
  scrollbar, ever (grep proof in Step 4).
- **Motion:** transitions use `--wb-motion-duration-pop`
  (160ms) / `-sheet` (200ms) / `-panel` (160ms) with
  `--wb-motion-ease`; the global `prefers-reduced-motion`
  rule in the themes CSS disables them.
- **Color is never the only signal:** statuses and badge
  kinds always render dot/glyph + word.
- **Buttons come from this kit only** (`Button`, plus the
  kit's own segmented/switch controls). Sections never
  hand-roll a button.
- **Density:** components read density only through the
  tokens that already scope on `[data-density]`
  (`--wb-row-height`, `--wb-card-padding`,
  `--wb-panel-padding`, layout gaps). No component takes
  a density prop.
- **Anchorability (SPEC §14):** the MAJOR components
  (Card, Frame, Lane, Sheet, DataTable, StateControls)
  take an optional `anchor?: string` prop. When provided,
  the component's root element renders
  `data-anchor={anchor}`; when absent, the attribute is
  omitted entirely. No other behavior or appearance
  changes. The anchor id's shape is
  `<section-or-exhibit>/<component>` in kebab slugs
  (e.g. `shell/project-rail`, `summary/bars-by-year`).
  Ids are DETERMINISTIC: minted from the component's
  spec name at build time — never random, never
  positional counters — so a rebuild reproduces the
  same ids. An id is never reused for a different
  component, and renaming a component = a new anchor
  (the old one's annotations degrade via the §12 orphan
  flow). Granularity stops at major components:
  TriageRow rows, Buttons, Chips, and Badges carry no
  `anchor` prop in v1 (§14.1).

Token vocabulary used below (all exist in the generated
themes): surfaces `--wb-surface-canvas/-1/-2/-3/-sunken`;
content `--wb-content-primary/-secondary/-muted`; borders
`--wb-border-default/-strong`; `--wb-accent`,
`--wb-accent-hover`, `--wb-on-accent`, `--wb-focus-ring`,
`--wb-danger`, `--wb-unknown`, `--wb-shadow-overlay`;
status `--wb-status-<status>` + `--wb-status-<status>-text`
for `canonical, implemented, deferred, unexplored,
hard-gate, abandoned, stale, needs-changes, not-covered,
approved, in-triage`; component tokens `--wb-chip-radius`,
`--wb-button-radius`, `--wb-card-bg`, `--wb-card-radius`,
`--wb-card-padding`, `--wb-frame-radius`,
`--wb-lane-bg`, `--wb-lane-well`, `--wb-lane-radius`,
`--wb-panel-radius`, `--wb-panel-padding`,
`--wb-row-height`; primitives `--wb-space-*`,
`--wb-radius-sm/-md/-lg/-pill`, `--wb-font-ui/-mono`,
`--wb-font-size-*` (via the Tailwind text scale the themes
entry defines), `--wb-motion-*`.

**On-fill text for danger:** no `--wb-on-danger` token
exists. Danger fills take `--wb-on-accent` (the kit's one
on-saturated-fill text token: `#ffffff` light / `#15170f`
dark) — recorded here as a deliberate alias, not an
invention; if a dedicated token is ever generated, this
doc and `Button` change together.

**Derived mixes:** a filled tint = the hue token at 14%
over transparent, `color-mix(in srgb, <token> 14%,
transparent)` (ui-context's chip rule); a pressed fill =
the fill token mixed 88% toward black,
`color-mix(in srgb, <token> 88%, black)`. These are
formulas over tokens, never literals.

---

## Chip — ruled status (filled)

Purpose: the ONE rendering of a ruled status (SPEC §5.1).
Filled pill: 8px dot + glyph + one word, always all three.
24px tall, `--wb-chip-radius`, truncate never wrap.

Props:

```ts
type RuledStatus = "canonical" | "implemented" | "deferred"
  | "unexplored" | "hard-gate" | "abandoned";
type ChipProps = {
  status: RuledStatus;
  gate?: string;        // hard-gate only: appended "· <gate>"
  pressed?: boolean;    // filter-chip form (requires onPress)
  onPress?: () => void; // present ⇒ renders <button aria-pressed>
  className?: string;
};
```

Words (fixed): Canonical, Implemented, Deferred,
Unexplored, Hard gate, Abandoned. Glyphs (fixed):
canonical ◆, implemented ✓, deferred ❚❚, unexplored ?,
hard-gate ⬢, abandoned ✕.

Appearance matrix (per status S; tint =
`color-mix(--wb-status-S 14%, transparent)`):

| State | Fill | Border | Text | Dot/glyph |
|---|---|---|---|---|
| default | tint of `--wb-status-S` | none (abandoned: 1px dashed `--wb-status-abandoned`) | `--wb-status-S-text` | `--wb-status-S` |
| hover (pressable only) | tint, border fades in | 1px solid `--wb-status-S` | `--wb-status-S-text` | `--wb-status-S` |
| active / pressed=true | tint at 22% mix | 1px solid `--wb-status-S` | `--wb-status-S-text` | `--wb-status-S` |
| focus-visible (pressable) | as default | ring: `--wb-focus-ring` | `--wb-status-S-text` | `--wb-status-S` |
| disabled (pressable) | tint | none | `--wb-status-S-text`, opacity 0.55 overall | `--wb-status-S` |

Never: a status as bare color/dot without the word; a
status rendered as an outline badge (that shape is
Badge's); wrapping to two lines; danger tokens (danger is
never a status).

## Badge — derived / review state (outline)

Purpose: derived staleness + review states ONLY (never a
ruled status). Outline pill: glyph + word + magnitude —
the caller-supplied `text` IS the word+magnitude
("Stale · 23d unverified"); a badge without its word is a
defect, so `text` is required and non-optional.

Props:

```ts
type BadgeKind = "stale" | "not-covered" | "needs-changes"
  | "approved" | "in-triage";
type BadgeProps = {
  kind: BadgeKind;
  text: string;         // word + magnitude, required
  stateHash?: string;   // approved only: rendered mono after "· state "
  className?: string;
};
```

Glyphs: stale 🕐 (clock, text glyph "◷"), not-covered ⚠,
needs-changes ↩, approved ✓, in-triage ▤ (inbox, text
glyph "▤"). Tone token per kind K = `--wb-status-K` /
`--wb-status-K-text` (approved → `--wb-status-approved*`,
which alias implemented).

Appearance matrix:

| Kind group | State | Fill | Border | Text | Glyph |
|---|---|---|---|---|---|
| stale / not-covered / needs-changes / in-triage | default (only state; badges are inert) | transparent | 1px solid `--wb-status-K` | `--wb-status-K-text` | `--wb-status-K` |
| approved | default | tint of `--wb-status-approved` at 14% | none | `--wb-status-approved-text` (+ hash in `--wb-font-mono`) | `--wb-status-approved` |

Approved is the ONE filled badge (ui-context: it reads as
the implemented chip's review form). Badges have no
hover/active/focus/disabled states — they are not
interactive; making one clickable is a defect (wrap it in
a Button/link at the section level instead).

Never: a ruled status in a Badge; a bare dot; text in the
raw bright hue (always the `-text` strong tone).

## AnnotationBadge — message lifecycle (outline)

Purpose: the annotation/message lifecycle ONLY (spec
§12) — a message's state is neither a registry ruling
nor a review derivation, so it is its own badge family,
in the Badge's outline form. Display only: `state` in,
nothing out; never interactive.

Props:

```ts
type AnnotationState = "draft" | "sent" | "acknowledged"
  | "done" | "archived";
type AnnotationBadgeProps = { state: AnnotationState };
```

Glyphs + words are fixed by the component (ratified
with the annotation mockup): sent → "Sent", acknowledged
◐ "Acknowledged", done ✓ "Done" — tone tokens
`--wb-status-sent` / `-acknowledged` / `-done` (+ their
`-text` variants), the Okabe–Ito lifecycle hues, constant
across palettes. Draft and archived render NO badge: the
state word alone in `--wb-content-muted` (the mockup
shows no badge for them).

Appearance matrix:

| State | Fill | Border | Text | Glyph |
|---|---|---|---|---|
| sent / acknowledged / done | transparent | 1px solid `--wb-status-K` | `--wb-status-K-text` | `--wb-status-K` |
| draft / archived | none | none | `--wb-content-muted` | none |

The component also owns the two annotation mark styles
(`selectionMarkStyle` / `annotationMarkStyle`, exported
for the sections' `<mark>` rendering): radius 3, padding
1px 2px, inset bottom bar; fills/bars are the
`--wb-highlight-*` tokens (live selection = the active
palette's accent derivation; saved annotation = Okabe
orange, palette-constant).

## Button

Purpose: the kit's only button. Variants primary /
secondary / danger / ghost × states default / hover /
active / focus-visible / disabled (SPEC §11.4's canonical
matrix). Radius `--wb-button-radius`, min-height 38px
(44px coarse), padding `--wb-space-8` × `--wb-space-16`,
font 14px medium. Destructive/disposition actions always
carry full text; icon-only is for row actions and REQUIRES
`aria-label` (enforced by the type: `iconOnly` demands
`ariaLabel`).

Props:

```ts
type ButtonProps = {
  variant?: "primary" | "secondary" | "danger" | "ghost"; // default primary
  iconOnly?: boolean;
  ariaLabel?: string;   // required when iconOnly
  type?: "button" | "submit" | "reset";                   // default "button"
  disabled?: boolean;
  onClick?: () => void;
  title?: string;       // pair with Tooltip at call site if needed
  className?: string;
  children?: ReactNode; // text (or glyph when iconOnly)
};
```

Appearance matrix:

| Variant | State | Fill | Border | Text |
|---|---|---|---|---|
| primary | default | `--wb-accent` | none | `--wb-on-accent` |
| primary | hover | `--wb-accent-hover` | none | `--wb-on-accent` |
| primary | active | mix(`--wb-accent` 88%, black) | none | `--wb-on-accent` |
| primary | focus-visible | `--wb-accent` + ring `--wb-focus-ring` | none | `--wb-on-accent` |
| primary | disabled | `--wb-accent`, opacity 0.55 | none | `--wb-on-accent` |
| secondary | default | `--wb-surface-2` | 1px `--wb-border-strong` | `--wb-content-primary` |
| secondary | hover | `--wb-surface-1` | 1px `--wb-border-strong` | `--wb-content-primary` |
| secondary | active | `--wb-surface-sunken` | 1px `--wb-border-strong` | `--wb-content-primary` |
| secondary | focus-visible | `--wb-surface-2` + ring | 1px `--wb-border-strong` | `--wb-content-primary` |
| secondary | disabled | `--wb-surface-2`, opacity 0.55 | 1px `--wb-border-strong` | `--wb-content-primary` |
| danger | default | `--wb-danger` | none | `--wb-on-accent` (alias, see header) |
| danger | hover | mix(`--wb-danger` 88%, black) | none | `--wb-on-accent` |
| danger | active | mix(`--wb-danger` 78%, black) | none | `--wb-on-accent` |
| danger | focus-visible | `--wb-danger` + ring `--wb-focus-ring` | none | `--wb-on-accent` |
| danger | disabled | `--wb-danger`, opacity 0.55 | none | `--wb-on-accent` |
| ghost | default | transparent | none | `--wb-content-secondary` |
| ghost | hover | `--wb-surface-1` | none | `--wb-content-primary` |
| ghost | active | `--wb-surface-sunken` | none | `--wb-content-primary` |
| ghost | focus-visible | transparent + ring | none | `--wb-content-secondary` |
| ghost | disabled | transparent, opacity 0.55 | none | `--wb-content-secondary` |

Never: a section-local button style; an icon-only
destructive/disposition button; a link styled as a Button
(use an anchor with Button classes only via this component
— v1 has no link variant, by design).

## Toggle — boolean switch

Purpose: one boolean. Renders `<button role="switch"
aria-checked>`, so Space/Enter toggle natively; the
visible label sits beside the track (clicking the label
text toggles too — it is inside the button).

Props:

```ts
type ToggleProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
};
```

Appearance matrix (track 40×24px, radius `--wb-radius-pill`;
knob 18px circle; sizes are layout literals of the switch
geometry, colors all tokens):

| State | Track fill | Track border | Knob | Label text |
|---|---|---|---|---|
| off / default | `--wb-surface-sunken` | 1px `--wb-border-strong` | `--wb-surface-2` | `--wb-content-primary` |
| off / hover | `--wb-surface-sunken` | 1px `--wb-accent` | `--wb-surface-2` | `--wb-content-primary` |
| on / default | `--wb-accent` | none | `--wb-on-accent` | `--wb-content-primary` |
| on / hover | `--wb-accent-hover` | none | `--wb-on-accent` | `--wb-content-primary` |
| focus-visible | as state + ring `--wb-focus-ring` on track | as state | as state | `--wb-content-primary` |
| disabled | as state, opacity 0.55, no change events | as state | as state | `--wb-content-secondary` |

Knob travel animates at `--wb-motion-duration-pop` /
`--wb-motion-ease`. Never: a checkbox/radio restyled to
look like this; text inside the track.

## SegmentedControl — the segmented primitive

Purpose: one choice from a small enum, rendered as a
segmented track. The shared primitive under ModeControl,
PaletteSelect (few-option form), DensityToggle, filter
segmenteds, and StateControls non-question `select`
fields (a `select` field that declares a `question`
renders option rows instead — see #statecontrols).
Semantics: NATIVE radio inputs (visually hidden, labels
styled as segments) in a `<fieldset>` whose `<legend>`
is the control's label — the
radio group gives the WAI-APG pattern natively: one Tab
stop per group, ←/→ move + select, the checked segment
carries the segment styling via `peer-checked`, and the
focus ring renders on the segment via
`peer-focus-visible`.

Wrap guarantee: a segment's label wraps INSIDE its pill
— there is no `nowrap` anywhere in this control — and a
pill never exceeds the fieldset's width (the label and
the segment carry `min-width: 0`, the label also
`max-width: 100%`). A too-long label grows its pill
taller, never wider than the track. Short labels are
unaffected: they render single-line exactly as before.

Props:

```ts
type SegmentedOption<V extends string> = { value: V; label: string };
type SegmentedControlProps<V extends string> = {
  options: SegmentedOption<V>[];
  value: V;
  onChange: (value: V) => void;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
};
```

Appearance matrix (track: `--wb-surface-sunken` fill,
`--wb-radius-sm`, padding `--wb-space-4`; segment
min-height 30px inside a ≥38px control row, padding
`--wb-space-4` × `--wb-space-12`, font 14px):

| Segment state | Fill | Border | Text |
|---|---|---|---|
| unselected / default | transparent | none | `--wb-content-secondary` |
| unselected / hover | transparent | none | `--wb-content-primary` |
| unselected / focus-visible | transparent + ring `--wb-focus-ring` | none | `--wb-content-secondary` |
| selected | `--wb-surface-2` | 1px `--wb-border-default` | `--wb-content-primary` (semibold) |
| selected / hover | `--wb-surface-2` | 1px `--wb-border-default` | `--wb-content-primary` |
| any / disabled (whole control) | track as default, opacity 0.55 | none | as state |

Never: more than 5 options (use a select — see
PaletteSelect); icons without text labels; multi-select
(that is Chip's pressable form or checkboxes, not this);
a segment label forced onto one line (`nowrap`) — see
the wrap guarantee above.

## ModeControl — appearance setting (shell contract)

EXACT contract (the owner ruling 2026-10-25 16:53 EDT;
Subplan 05 codes `#/settings` against this signature —
do not deviate):

```ts
type ModeControlProps = {
  value: "system" | "light" | "dark";
  onChange: (v: "system" | "light" | "dark") => void;
};
```

A SegmentedControl with options System / Light / Dark,
`ariaLabel="Color mode"`. Appearance = the
SegmentedControl matrix, every cell. Pure: the shell
applies + persists; this component only reports.

## PaletteSelect — appearance setting (shell contract)

EXACT contract (same ruling):

```ts
type PaletteSelectProps = {
  value: string;
  options: { id: string; label: string }[];
  onChange: (id: string) => void;
};
```

Palette ids arrive via props — NEVER hardcoded inside.
Form: SegmentedControl when `options.length ≤ 4`;
a native `<select>` when more (a palette list can grow;
a select stays usable). Appearance: segmented form = the
SegmentedControl matrix; select form = the select row of
the StateControls matrix (surface-2 fill, border-default,
button radius, focus ring). `aria-label="Palette"`.

## DensityToggle — appearance setting (shell contract)

EXACT contract (same ruling):

```ts
type DensityToggleProps = {
  value: "comfortable" | "compact";
  onChange: (v: "comfortable" | "compact") => void;
};
```

A SegmentedControl with options Comfortable / Compact,
`ariaLabel="Density"`. Appearance = the SegmentedControl
matrix, every cell. Pure, like ModeControl.

## Card

Purpose: the static content card (storyboard tiles'
chrome, panels of data). `--wb-card-bg` fill,
`--wb-card-radius`, 1px `--wb-border-default`,
padding `--wb-card-padding` (density-scoped token).

Props:

```ts
type CardProps = {
  title?: ReactNode;    // renders the card-title row (14px semibold)
  actions?: ReactNode;  // right end of the title row (kit buttons)
  anchor?: string;      // §14 anchor id — data-anchor on the root, omitted when absent
  className?: string;
  children?: ReactNode;
};
```

Appearance matrix (Card has no interactive states of its
own; interactive children carry their own):

| State | Fill | Border | Title text | Body text |
|---|---|---|---|---|
| default (only) | `--wb-card-bg` | 1px `--wb-border-default` | `--wb-content-primary` | `--wb-content-primary` |

Never: a shadow (elevation is the surface ladder +
border; the only shadow token is for overlays); nested
cards (use a sunken well inside instead).

## Frame — the standard mockup frame (SPEC §9)

Purpose: every mockup renders inside this frame:
header (title + optional per-frame actions, e.g. the
frame's own mode toggle supplied by the section),
a SUNKEN preview well holding the mock, an optional
footer row (the section puts Chip + Badges there).
Radius `--wb-frame-radius`, fill `--wb-surface-2`,
1px `--wb-border-default`; well = `--wb-surface-sunken`
with the viewport label in mono 12px `--wb-content-muted`.

Props:

```ts
type FrameProps = {
  title: string;
  viewportLabel?: string;   // e.g. "1440 × 900 · dark" — mono, in the well's corner
  headerActions?: ReactNode;
  footer?: ReactNode;
  archived?: boolean;       // archived ⇒ whole frame at 60% saturation, chip intact
  anchor?: string;          // §14 anchor id — data-anchor on the root, omitted when absent
  className?: string;
  children?: ReactNode;     // the mock, inside the well
};
```

Appearance matrix:

| State | Frame fill | Border | Well fill | Title | Saturation |
|---|---|---|---|---|---|
| default | `--wb-surface-2` | 1px `--wb-border-default` | `--wb-surface-sunken` | `--wb-content-primary` | 100% |
| archived | `--wb-surface-2` | 1px `--wb-border-default` | `--wb-surface-sunken` | `--wb-content-primary` | 60% (`saturate-[0.6]` — the ui-context archived rule; a filter value, not a color) |

Never: mock content outside the well; a second frame
style; explanatory prose inside the frame (SPEC §9 —
titles/labels/data only).

## Lane — board lane

Purpose: one board column. Body `--wb-lane-bg`,
radius `--wb-lane-radius`; header = 12px uppercase
section head (`--wb-content-secondary`, letter-spacing
0.06em) + a count chip; body well = `--wb-lane-well`
sunken inner area holding the cards.

Props:

```ts
type LaneProps = {
  title: string;
  count: number;
  accent?: boolean;        // Review lane: 2px accent left edge
  countWarning?: boolean;  // Doing > 7: soft warning tone on the count
  anchor?: string;         // §14 anchor id — data-anchor on the root, omitted when absent
  className?: string;
  children?: ReactNode;    // cards, inside the sunken well
};
```

Appearance matrix:

| Element / state | Fill | Border / edge | Text |
|---|---|---|---|
| lane body | `--wb-lane-bg` | 1px `--wb-border-default` (accent: + 2px left `--wb-accent`) | — |
| header title | — | — | `--wb-content-secondary`, 12px uppercase |
| count chip / default | `--wb-surface-sunken` | none | `--wb-content-secondary` |
| count chip / warning | tint of `--wb-status-stale` 14% | none | `--wb-status-stale-text` |
| inner well | `--wb-lane-well` | none | `--wb-content-primary` |

Lanes are not themselves interactive; a collapsed Done
strip is a section composition (Button + count), not a
Lane variant. Never: horizontal page scroll caused by a
lane (lanes scroll internally — the section's container
owns overflow; Lane never sets `overflow` on itself
beyond its well's internal scroll, and never styles the
scrollbar).

## Sheet — modal panel / confirm sheet

Purpose: drill-in confirm + short panels (the approve
confirm sheet is the canonical use: state snapshot →
ruling note → save). Modal: `role="dialog"`,
`aria-modal="true"`, labelled by its title; Escape and
backdrop click call `onClose`; focus moves to the panel
on open and the panel is the tab container's start
(sections keep sheet content short; full focus-trap
machinery is a section concern if a sheet ever grows
form-length). Panel: `--wb-surface-3` fill,
`--wb-panel-radius`, `--wb-shadow-overlay` (the kit's
only shadow), padding `--wb-panel-padding`; backdrop =
`color-mix(in srgb, --wb-content-primary 45%, transparent)`.

Props:

```ts
type SheetProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  anchor?: string;       // §14 anchor id — data-anchor on the root, omitted when absent
  className?: string;
  children?: ReactNode;  // body; disposition Buttons go in footer
  footer?: ReactNode;
};
```

Appearance matrix:

| State | Backdrop | Panel fill | Panel border | Title |
|---|---|---|---|---|
| open | mix(`--wb-content-primary` 45%, transparent) | `--wb-surface-3` | 1px `--wb-border-default` | `--wb-content-primary`, 18px semibold |
| closed | — (renders nothing) | — | — | — |

Entrance transition: `--wb-motion-duration-sheet` /
`--wb-motion-ease` on opacity. Never: a second modal
system; sheet content that fetches; a sheet without a
visible title (the title is the accessible name).

## Tooltip — the data-tip mechanism

Purpose: the ONE tooltip system (ui-context): no native
`title`, no second system. Wraps a focusable child;
the tip appears on hover AND on focus-within after a
300ms delay. The wrapper carries `data-tip="<text>"`
(the mechanism's namesake attribute) and renders the tip
as a styled pseudo-element — token-styled: fill
`--wb-content-primary`, text `--wb-surface-1`,
radius `--wb-radius-sm`, 12px, padding `--wb-space-4` ×
`--wb-space-8`, shadow `--wb-shadow-overlay`,
`--wb-motion-duration-pop` fade.

Props:

```ts
type TooltipProps = {
  text: string;
  className?: string;
  children: ReactNode;  // normally one focusable element (icon Button)
};
```

Appearance matrix:

| State | Tip fill | Tip text | Visibility |
|---|---|---|---|
| rest | `--wb-content-primary` | `--wb-surface-1` | hidden (opacity 0) |
| hover / focus-within (after 300ms delay) | `--wb-content-primary` | `--wb-surface-1` | visible (opacity 1) |

Never: essential information in a tooltip only (it is a
label aid — icon Buttons still carry `aria-label`);
interactive content inside a tip; a native `title`
attribute anywhere in the kit.

## EmptyState — honest empty

Purpose: empty is a state, not an error (ui-context):
a sunken well, one line, styled as content. Optional
second line + one kit Button action.

Props:

```ts
type EmptyStateProps = {
  message: string;      // the one line, e.g. "No mockups match these filters"
  detail?: string;      // optional second line, muted
  action?: ReactNode;   // a kit Button, if a recovery exists
  className?: string;
};
```

Appearance matrix:

| State | Fill | Border | Message | Detail |
|---|---|---|---|---|
| default (only) | `--wb-surface-sunken` | 1px dashed `--wb-border-default` | `--wb-content-secondary`, 14px | `--wb-content-muted`, 12px |

Never: an error rendered as an EmptyState (errors are
DegradedBanner / section error text); a spinner in an
empty state; more than one action.

## DataTable

Purpose: columns in field order with caller-supplied
friendly headers (the label map lives outside the kit;
raw snake_case never reaches this component). Row hover
and selected per ui-context. Rows are selectable and
activatable from the keyboard: the selected row carries
`aria-selected` (grid-lite: `role="table"` semantics via
native table elements), every row is focusable
(`tabIndex=0`) when `onRowSelect` is present, Enter/Space
select, double-click / Enter-on-selected activates
(`onRowActivate`).

Props:

```ts
type DataTableColumn<T> = {
  key: string;
  header: string;
  mono?: boolean;               // IBM Plex Mono + slashed zero
  numeric?: boolean;            // tnum + right align
  render?: (row: T) => ReactNode; // default: String(row[key])
};
type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  selectedKey?: string;
  onRowSelect?: (key: string) => void;
  onRowActivate?: (key: string) => void;
  empty?: ReactNode;            // rendered in place of rows (an EmptyState)
  ariaLabel: string;
  anchor?: string;              // §14 anchor id — data-anchor on the root, omitted when absent
  className?: string;
};
```

Appearance matrix (row height = `--wb-row-height`,
density-scoped; header = 12px uppercase
`--wb-content-secondary` on `--wb-surface-1`):

| Row state | Fill | Left edge | Text |
|---|---|---|---|
| default | `--wb-surface-2` | none | `--wb-content-primary` |
| hover | `--wb-surface-1` | none | `--wb-content-primary` |
| selected | `--wb-surface-1` | 2px inset bar `--wb-accent` | `--wb-content-primary` |
| focus-visible | as state + ring `--wb-focus-ring` (inset) | as state | `--wb-content-primary` |
| header row | `--wb-surface-1` | bottom 1px `--wb-border-strong` | `--wb-content-secondary` |
| cell separators | — | bottom 1px `--wb-border-default` | — |

Never: sorting/filtering chrome invented here (sections
compose controls above the table); a row taller than
`--wb-row-height` from cell padding (cells truncate);
fetching or pagination logic.

## DegradedBanner

Purpose: per-project degraded state + plan source-format
flags (ui-context: an error names the section + the
recovery in one sentence, once). `role="status"`.

Props:

```ts
type DegradedBannerProps = {
  tone?: "degraded" | "source-format";  // default "degraded"
  message: string;    // section + problem, one sentence
  detail?: string;    // the recovery, one sentence
  className?: string;
};
```

Appearance matrix:

| Tone | Fill | Border | Glyph | Message text |
|---|---|---|---|---|
| degraded | tint of `--wb-status-stale` 14% | 1px `--wb-status-stale` | ⚠ in `--wb-status-stale` | `--wb-content-primary` (detail: `--wb-content-secondary`) |
| source-format | `--wb-surface-1` | 1px `--wb-border-default` | ℹ in `--wb-content-secondary` | `--wb-content-primary` (detail: `--wb-content-secondary`) |

Never: danger tokens (degraded is contained, not
destructive); a banner per row (one per project/section);
auto-dismiss behaviour.

## TriageRow

Purpose: one entry in the triage queue (Mockups triage /
Board review lane list form): the whole row opens the
entry. Composition is by slots so the ruled/derived split
stays visible: Chip + Badges arrive as nodes.

Props:

```ts
type TriageRowProps = {
  title: string;
  meta?: string;          // project / age line, muted
  leading?: ReactNode;    // the entry's Chip
  badges?: ReactNode;     // Badge(s): stale / needs-changes / not-covered
  onOpen: () => void;
  className?: string;
};
```

Appearance matrix (row = one `<button>`, min-height
`--wb-row-height` + `--wb-space-8`, radius
`--wb-radius-md`, padding `--wb-space-12` × `--wb-space-16`):

| State | Fill | Border | Title | Meta |
|---|---|---|---|---|
| default | `--wb-surface-2` | 1px `--wb-border-default` | `--wb-content-primary` | `--wb-content-muted` |
| hover | `--wb-surface-1` | 1px `--wb-border-strong` | `--wb-content-primary` | `--wb-content-muted` |
| active | `--wb-surface-sunken` | 1px `--wb-border-strong` | `--wb-content-primary` | `--wb-content-muted` |
| focus-visible | `--wb-surface-2` + ring `--wb-focus-ring` | 1px `--wb-border-default` | `--wb-content-primary` | `--wb-content-muted` |

Never: interactive children inside the row button (chips
in a row are the inert form; badges are always inert);
a second open affordance (the trailing › is decorative).

## StateControls — generated from a state_schema

Purpose: an entry's internal-state controls, GENERATED
from its declared `state_schema` (SPEC §14.3) — never
hand-built per entry. Schema shape is the lib validator's
(`lib/validators.py::check_state_schema`):

```ts
type StateFieldSpec = {
  type: "toggle" | "select" | "text" | "number";
  options?: string[];   // select only, required non-empty
  default?: unknown;
  label?: string;       // display override; default = humanized key
  min?: number; max?: number; step?: number;  // number only
  question?: string;    // decision prompt — the field renders as a decision block (SPEC §5.1)
  recommended?: unknown; // the recommended value (toggle/select/text/number)
  option_notes?: Record<string, string>; // per-option explanations, select only
};
type StateSchema = Record<string, StateFieldSpec>;
type StateValues = Record<string, boolean | string | number>;
type StateControlsProps = {
  schema: unknown;      // untrusted at the boundary: validated here
  values: StateValues;
  onChange: (key: string, value: boolean | string | number) => void;
  title?: string;       // panel heading, default "State"
  disabled?: boolean;
  anchor?: string;      // §14 anchor id — data-anchor on the container, omitted when absent
  className?: string;
};
```

Control mapping (fields WITHOUT a question: one row per
key, in schema order — label left, control right; on
phone the row stacks: label above, control full width):

| Field type | Control | Notes |
|---|---|---|
| toggle | `Toggle` | value must be boolean |
| select | `SegmentedControl` if ≤4 options, else native `<select>` | value must be one of `options` |
| number | stepper: ghost `Button` − / + around a numeric input | respects `min`/`max`/`step`; typed input commits on change |
| text | text input | commits on change |

Question fields — DECISION BLOCKS. A field whose spec
declares a `question` renders as a decision block, not a
label/control row: the field's short label as a small
muted eyebrow, the question as the prompt, then the
control — there is no side-by-side label column. For a
`select` question the control is a fieldset of
full-width OPTION ROWS (native radios, the
SegmentedControl semantics: one Tab stop per group,
arrows move + select) at ANY option count. Each row
carries, in one unit: the option label (wrapping
freely, never `nowrap`), a "· recommended" badge on the
recommended option, and the option's `option_notes`
text as the row's secondary text; the selected row
takes the checked-segment styling (1px
`--wb-border-default`, `--wb-surface-2`, semibold
label). EACH FACT IS STATED ONCE: the badge lives in
the row and the explanation lives in the row — NO notes
block and NO recommended line render under a select
question. Toggle questions render prompt + `Toggle` +
the Recommended line; text/number questions render
prompt + control + the Recommended line. (For
non-question fields the mapping table above is
unchanged, including the notes block under a select
that declares `option_notes` without a question.)

**Invalid schema ⇒ honest error, never a crash.** The
component validates defensively at render (schema not an
object; a spec not an object; unknown `type`; `select`
without non-empty string `options`; a current value that
does not conform). A wholly invalid schema renders one
error block; a single bad field renders an error row IN
PLACE of that field's control while valid fields still
render. Error appearance = the DegradedBanner degraded
cell set (stale tint/border, ⚠, `--wb-content-primary`
text, problem named in words).

Appearance matrix (panel + controls):

| Element / state | Fill | Border | Text |
|---|---|---|---|
| panel | `--wb-surface-2` | 1px `--wb-border-default`, radius `--wb-panel-radius`, padding `--wb-panel-padding` | — |
| panel heading | — | — | 12px uppercase `--wb-content-secondary` |
| row label | — | — | `--wb-content-primary`, 14px |
| question eyebrow | — | — | 12px uppercase semibold `--wb-content-muted` |
| question option row / unselected | transparent | none | `--wb-content-secondary` |
| question option row / selected | `--wb-surface-2` | 1px `--wb-border-default` | `--wb-content-primary` (semibold label) |
| select (>4) / text / number input / default | `--wb-surface-2` | 1px `--wb-border-default`, radius `--wb-button-radius` | `--wb-content-primary` |
| input / hover | `--wb-surface-2` | 1px `--wb-border-strong` | `--wb-content-primary` |
| input / focus-visible | `--wb-surface-2` + ring `--wb-focus-ring` | 1px `--wb-border-default` | `--wb-content-primary` |
| input / disabled | `--wb-surface-1`, opacity 0.55 | 1px `--wb-border-default` | `--wb-content-secondary` |
| field error row | tint of `--wb-status-stale` 14% | 1px `--wb-status-stale` | `--wb-content-primary` |

Never: a control type outside the four above (a schema
asking for one is an invalid schema — error row, not a
new control); controls scattered outside the panel;
mutating `values` (events out only); stating an option,
its explanation, or "recommended" twice for one field
(e.g. a pill plus a notes block under it); a `nowrap`
option label anywhere in a question block.

## Specimen — the kit specimen harness (not a section component)

`Specimen.tsx` exports `KitSpecimen`: every component
above rendered in its contracted variants with local
fixture state (all six Chips + pressable form, all five
Badges, all four Buttons incl. icon-only + disabled,
Toggle, SegmentedControl, ModeControl, PaletteSelect in
both forms, DensityToggle, Card, Frame incl. archived,
Lane incl. warning count, Sheet behind a Button,
Tooltip on an icon Button, EmptyState, DataTable with a
selected row, DegradedBanner in both tones, TriageRow,
StateControls against a valid fixture schema exercising
all four field types + an invalid fixture schema). One
Card instance carries `anchor="specimen/card"` so the
§14 `data-anchor` emission pattern is visible in the
harness itself.
Sections never import it; it exists so the kit's matrix
is reviewable in one render (Subplan 04 Steps 2–3 verify)
and is justifiable past the ~300-line guideline on
exactly that ground: it is a harness, not a component.

## Size + composition discipline

One component per file; a file past ~300 lines is split
or justified here (only Specimen is, above). Nothing in
`components/` imports a section, the shell, or a data
module; the only imports are React, sibling kit
components (downward composition inside the kit:
settings controls → SegmentedControl; StateControls →
Toggle / SegmentedControl / Button), and type imports.
