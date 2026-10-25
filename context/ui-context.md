# UI Context

## STATUS: FUNDAMENTALS PENDING DENNY'S APPROVAL

The viewer's fundamentals — theme, design tokens, fonts,
styling approach, concrete frontend dependencies, and the
`viewer/` internal layout — are being designed separately
and must be approved by the owner before they are set into the
build (the owner, 2026-10-25 steering). Steps 5 and 6 of the
founding plan (both viewer builds) are HELD until the
approved fundamentals are handed over.

Nothing in this file is a design decision yet. When the
approved fundamentals arrive, this file is rewritten with
them, in the Six-File shape:

- **Theme** — the visual language (to be approved).
- **Colors** — token table as CSS custom properties; all
  components use tokens, no hardcoded values. (Token values
  to be approved.)
- **Typography** — UI and mono fonts. (To be approved.)
- **Border radius / spacing scales** — (to be approved).
- **Layout patterns** — app frame, section layouts. (To be
  approved.)
- **Component conventions** — (to be approved).

Two constraints from the founding plan bind whatever is
approved (they are functional, not design, decisions):

- The status vocabulary is fixed (canonical / implemented /
  deferred / unexplored / hard-gate / abandoned); each ruled
  status must render DISTINCTLY, and derived staleness must
  render as a badge beside the status — never as a status.
- The artifact is fully self-contained: everything it needs
  ships with its build; nothing is fetched from a CDN at
  runtime. (Which concrete dependencies achieve that is part
  of the pending fundamentals decision.)
