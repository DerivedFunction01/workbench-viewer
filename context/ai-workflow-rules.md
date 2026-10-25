# AI Workflow Rules

## Approach

Build incrementally against the founding plan
(`2026-10-25-workbench-viewer-repo.md`) and
these context files. One plan step at a time; each step's
verify list is its gate — run it, keep the evidence, and only
then move on. Implement against the specs in `architecture.md`
and subplan 09 Part B; do not invent behavior the specs do not
define — resolve gaps in the context file (or as an open
question in `progress-tracker.md`) first.

## Scoping Rules

- Work on one feature unit (one plan step) at a time.
- Prefer small, verifiable increments over large speculative
  changes.
- Do not combine unrelated system boundaries in a single
  step: lib/ changes, server changes, and artifact changes
  land as separate commits even inside one plan step when
  they are independently verifiable.

## When to Split Work

Split a step if it combines:

- A lib/ mutation change and a viewer UI change that can each
  be verified without the other
- Multiple unrelated API routes
- Behavior not clearly defined in the context files

If a change cannot be verified end to end quickly, the scope
is too broad — split it.

## Handling Missing Requirements

- Do not invent product behavior not defined in the context
  files or the founding plan.
- If a requirement is ambiguous, resolve it in the relevant
  context file before implementing.
- If a requirement is missing, add it as an open question in
  `progress-tracker.md` before continuing.

## Protected Files

Do not modify unless explicitly instructed:

- Any project's `registry.db` / `registry.json` by hand —
  data changes go through `wb` or the viewer's lib/ mutations
  only.
- The `example-project` repo's `SPEC.md` and its
  `.plans/spec-extraction/` (another effort owns those).
- The `example-project-legacy` repo (prototype — read-only
  reference) and the `another-project` repo (excluded by design).
- In example-project, the ONLY file this harness's work
  may add is `workbench.yaml` (its adoption manifest); v2
  commits are the owner's separately.

## Gates and Git

- Tests run under the repo venv:
  `.venv/bin/python -m unittest discover -s tests`.
- One local commit per completed plan step, author `DL <>`
  via per-command `-c` flags. No pushes, no remotes.
- Publishing the artifact and enabling the systemd unit are
  platform steps: they happen on the owner's word (the founding
  plan's implement instruction covers the first publish).

## Keeping Docs in Sync

Update the relevant context file whenever implementation
changes: system architecture or boundaries, storage model
decisions, code conventions, feature scope. Update
`progress-tracker.md` after each meaningful change.

## Before Moving to the Next Unit

1. The current unit works end to end within its defined scope.
2. No invariant in `architecture.md` was violated.
3. `progress-tracker.md` reflects the completed work.
4. The test suite passes under the repo venv.
