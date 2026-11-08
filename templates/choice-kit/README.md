# Choice kit — the starter artifact for choice studies

One self-contained static page (`kit.html`) that renders a study
from a JSON **spec**: content sections plus a set of choices
(toggles, picks, sliders, inputs), one Copy button that returns
the answers as JSON, and a feedback mode for annotating the
content itself. Authors write only the spec; the controls, the
copy payload, and the feedback machinery come with the kit.

Files:

- `kit.html` — the runtime. Inline CSS + vanilla JS, no external
  dependencies, no build step. It reads its spec from the
  `<script type="application/json" id="ck-spec">` block embedded
  in the file; as shipped, that block holds the demo spec.
- `spec.demo.json` — the demo spec, identical to the one
  embedded in `kit.html`: one choice of every type, an inline
  linked control, a `place: "section"` choice, and a feedback-
  labelled section, all in a fictional settings study. Copy it
  as a starting point and replace the content.
- `README.md` — this contract.

## The spec

```json
{
  "id": "reading-app-settings-study",
  "title": "Reading App Settings — Study",
  "intro": "Markdown-lite text shown under the title.",
  "sections": [ … ],
  "choices": [ … ]
}
```

- `id` (required) — the artifact slug. It keys the saved state
  (see Persistence) and is the `artifact` field of the Copy
  payload.
- `title` — shown in the sticky bar and the page title area.
- `intro` — optional markdown-lite text under the bar.
- `sections` — content blocks, rendered in order.
- `choices` — every choice, declared **once** (see Linking).

### Sections

```json
{
  "id": "appearance",
  "heading": "Appearance",
  "body": "Markdown-lite text.",
  "image": { "src": "…", "alt": "…" },
  "fb": "Appearance section",
  "controls": ["dark-mode", "layout"]
}
```

- `id`, `heading`, `body` — the block's anchor, title, and
  text. Body text is markdown-lite: HTML is escaped first, then
  `**bold**`, `` `code` ``, paragraphs split on blank lines,
  and blocks of `- ` lines become bullet lists. Nothing else is
  interpreted — no links, no raw HTML.
- `image` — optional; `src` may be a URL or a `data:` URI,
  `alt` is its accessible text (and its feedback snippet).
- `fb` — optional feedback label for the whole block (see
  Feedback labels).
- `controls` — optional list of choice ids rendered inline at
  the end of the section, next to the content they govern.

### Choices

```json
{ "id": "layout", "label": "Layout density", "type": "single",
  "help": "How much content fits on one screen.",
  "options": [
    { "value": "comfortable", "label": "Comfortable" },
    { "value": "compact", "label": "Compact", "recommended": true }
  ] }
```

Common fields:

- `id` (required, unique) — the answer key in the Copy payload
  and in the saved state.
- `label` (required) — the question as the reader sees it.
- `type` (required) — one of the six types below.
- `help` — optional explanation under the label.
- `default` — optional starting value; per-type fallbacks are
  listed below.
- `place` — optional; `"section"` means the control exists only
  inline in its section (see Linking).

Types:

| type | value in payload | extra fields | default fallback |
| --- | --- | --- | --- |
| `toggle` | boolean | — | `false` |
| `single` | the picked option's `value` (string) | `options` | the `recommended` option, else the first |
| `multi` | array of picked `value`s, in option order | `options` | `[]` |
| `slider` | number | `min`, `max`, `step`, `unit` | `min` (else `0`) |
| `input-text` | string | — | `""` |
| `input-number` | number, or `""` while empty | — | `""` |

`options[]` entries are `{value, label, recommended?}`; a
`recommended: true` option is badged **Recommended** wherever
the choice renders. A slider's readout shows the live value
plus its `unit`.

## Linking

A choice is declared once in `choices[]`. It can be *viewed*
in up to two places, both bound to the same value — there is
one state object, so the views cannot drift:

- **Inline** — a section lists the choice id in `controls[]`
  and the control renders inside that section.
- **Summary** — the closing "All choices" panel lists every
  choice as a row: label, current value, and the control
  itself.

Exceptions and aids:

- `place: "section"` — the summary row shows the label, the
  current value, and a jump link, but **no second control**;
  the only control is the inline one. Use it when a duplicate
  would confuse (a pick that only makes sense beside its
  content).
- **Jump link** — any choice hosted in a section gets a
  "jump to section" link in its summary row; it scrolls to the
  inline control and flashes it.
- Choices in no section's `controls[]` exist only in the
  summary panel.

Every rendered control sits in a wrapper carrying
`data-fb="Choice: <label>"`. Exactly one wrapper per choice —
the inline one when the choice is hosted in a section, the
summary one otherwise — also carries
`id="ck-choice-<choice id>"`, the jump target.

## The Copy payload

The bar holds exactly **one** Copy button. It writes one JSON
payload to the clipboard:

```json
{
  "artifact": "reading-app-settings-study",
  "answers": { "dark-mode": true, "layout": "compact" },
  "feedback": [
    { "target": "Reading comfort section",
      "text": "Long-form text stays readable when the type size…",
      "comment": "This paragraph is the part I mean." }
  ]
}
```

- `artifact` — the spec `id`.
- `answers` — **every** choice id mapped to its current value,
  answered or not (unanswered choices carry their default).
- `feedback` — the feedback entries in the order they were
  added; `[]` when there are none.

The paste is the transport: the reader copies it into the
thread (or sends it through the viewer's messages) and the
receiving agent parses it. There is no YAML or text variant
and no per-part button — one format, one payload.

## Persistence

Answers persist in the page's `localStorage` under the key
`ck:<spec id>`, saved on every change and reloaded on open, so
a reload or a revisit never loses picks. Stored values are
checked against the spec (unknown ids dropped, wrong shapes
ignored) before they override the defaults. Feedback entries
are **not** persisted — they live until copied.

## Feedback mode

The bar's **Feedback mode** button toggles annotation mode:

- A banner appears: "Feedback mode — clicks annotate, nothing
  changes"; the cursor becomes a crosshair outside the kit's
  own chrome.
- While it is on, clicks (and change/input/submit events)
  anywhere outside the kit chrome — the bar, the banner, the
  composer, the feedback panel — are intercepted before they
  can do anything: no control changes state, no link is
  followed. A click instead **selects a target**.
- The selected element is outlined and a composer opens with
  the target's label and a short text snippet; the reader
  types a comment and presses **Add**. The entry joins the
  Feedback panel, where its comment stays editable and the
  entry can be removed. The bar shows the live feedback count.
- Turning the mode off clears any pending selection; the
  entries already added stay, and ride the Copy payload.

### Feedback labels

A click resolves its target by label first:

- The nearest element (the clicked node or an ancestor) with a
  `data-fb="<label>"` attribute wins, and the label becomes
  the entry's `target`.
- A section with an `fb` field renders `data-fb` on the whole
  section block, so any click inside it that is not more
  specifically labelled resolves to the section.
- Every choice control wrapper carries
  `data-fb="Choice: <label>"` automatically — clicking a
  control in feedback mode annotates the choice, by name.
- With no label anywhere up the chain, the fallback target is
  automatic: `<section heading> · <tag name>`, and the entry's
  `text` is the first ~60 characters of the clicked element's
  visible text. (`text` is always that snippet of the labelled
  element, so an entry shows what was pointed at.)

## How `wb artifact new` / `build` consume this

The harness commands (plan steps 3+) stamp the kit into a
project entry:

- `wb artifact new <slug>` copies `kit.html` into the entry
  directory as its `index.html`, writes the entry's `spec.json`
  (the supplied `--spec` file, or `spec.demo.json` as the
  scaffold), embeds that spec into the `index.html` copy's
  `ck-spec` block, and registers the entry (kind `artifact`,
  `state_schema` derived from the spec's choices).
- `spec.json` in the entry stays the **editable source**:
  authors edit the spec, not the generated page.
- `wb artifact build <slug>` re-embeds the entry's current
  `spec.json` into its `index.html`, refreshing the page after
  spec edits.
- Publishing the entry as a static artifact stays a separate
  agent act; the kit files are plain static HTML either way.

## Limits

- One page, no routing, no server: state is the reader's own
  browser storage, and answers travel only by the Copy paste.
- Markdown-lite is deliberately small (bold, code, lists,
  paragraphs). Anything richer belongs in the study's own
  page, not in the kit.
- Specs are trusted input — the kit validates shapes lightly
  (state coercion) but does not schema-check the spec itself;
  `wb artifact new` is the place that refuses a bad spec.
