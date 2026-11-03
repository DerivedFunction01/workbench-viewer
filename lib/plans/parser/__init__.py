"""The house plan parser: plan markdown → structured document.

Design rule (founding plan): the parser NEVER drops content.
The document is built by partitioning the source lines into a
header block and sections — every line lands in exactly one
of them, in order — and the structured views (fields, steps,
blocks) are derived from that partition. A plan that does not
match the house format is flagged `conforming: False` and
still returns its whole text (the viewer renders it as
formatted markdown); nothing is silently structured away.

House format (from the real corpus — the founding plan, v2's
subplans, the 2026-10-23 PowerBI plans, the 2026-10-22
bootstrap plan):
  - `# Title`, then header fields `Key: value` (values wrap),
    notably Status / Created / Parent.
  - `## Rulings`, `## Steps`, ... sections. The plan syntax
    standard's semantic sections are read structurally:
    `## Open questions` task-list items (with checked state),
    the `## Subplans` declared-path list, and the
    `## Critical files` path list join the payload;
    their absence is empty, never an error.
  - Steps, two shapes: `N. **Title.**` items with `files:` /
    `verify:` / `done when:` labels, or `### Step N — Title`
    headings — both under a steps-ish heading (`## Steps`,
    `## Implementation steps`) or after a bare `Steps:` line.
Numbered lists elsewhere (goals, open questions) are NOT
steps: steps are only read inside a steps region.
  - Resolvable questions (plan syntax standard): an item in
    an open-questions section may carry a `wb-question`
    sentinel comment with its structured form; well-formed
    sentinels join the payload as `questions` records and
    malformed ones are reported in `sentinel_errors` — the
    question itself still renders as plain markdown, and
    sentinel lines never fold into an item's text.

The module is a package now (800-line cap split): the
grammar, the document model, the sentinel questions,
and the plan parsing live in the submodules; this
__init__ re-exports the existing public surface so
`import lib.plans.parser` and every current importer
keep working unchanged.
"""

from .grammar import declared_status, status_bucket
from .plans import (apply_answers, list_plans, load_plan,
                    parse_plan, reconstruct)
