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

## Live work tracking

Determined in `.plans/2026-10-25-live-work-tracking-spec.md`;
the bundle is the unit of work.

- Work lives in a bundle under `.plans/<date>-<slug>/`. Its
  progress is tracked in todo files — one file per todo under
  the bundle's `todos/`, front-matter `id` / `title` /
  `status` / `feature` / `plan` / `plan_step` / `worktree` —
  created and moved only through the harness (`wb bundle
  new`, `wb todo new`, `wb todo set`). File todos supersede
  the registry DB's todo table; new todos are files only.
- Create the bundle's todos before starting, one per plan
  step or work item, and move each status at the transition
  (`todo` → `doing` → `done` / `blocked`) — not in a batch
  at the end. A blocked todo carries its reason in its body
  the moment it blocks.
- Ships happen at checkpoints (a step's done-when,
  gate-green), and the deploy is recorded in the relevant
  todo — what shipped and when — so the board shows what is
  live, not just what is coded.
- A plan that completes is frozen (`Status: complete`) and
  never edited again; the bundle archives whole to
  `.plans/finished/` when its todos all close. Work beyond
  a completed plan's scope goes into a followup plan or
  bundle carrying only the remainder, and the older plan is
  archived in the same pass, its Status line naming the
  followup.

## Progress schedules for long work

Long work never waits on the owner to ping for status: a
schedule pings the work instead. Long = multi-step,
delegated, detached, or expected to run past roughly an
hour. The harness records the intent and the derivations
— and, since the owner's 2026-10-31 auto-create
commission, it also creates the schedule: arming a todo
writes its scheduler-registry entry in the same call
(`lib/progress_schedule.py`; one scripted entry per todo,
running `wb progress-check <id>` at the todo's cadence,
a stall exiting non-zero so the scheduler's failure
report pings), and disarming deletes it. No hand-made
schedule is needed or wanted; `wb progress
--sync-entries` reconciles the registry against the
armed set, and the doctor flags drift three ways
(`todo-progress-entry-missing`,
`todo-progress-entry-unscheduled`,
`todo-progress-entry-orphan`). Entry existence is not
scheduling: the scheduler engine fires only entries
admitted through its own admission flow (`migrated:
true`, flipped after validate + a server-context
proof run), the harness render is born unadmitted,
and a re-sync never resets an admitted entry's flip.
The doctor's unscheduled check reads the entry's
migrated flag and the server's next-due table, so an
armed-but-unadmitted entry is loud, not silent. The per-bundle driver
template below remains the pattern for agent-driven
follow-up where a thread runs one.

- **Arming is automatic at the `doing` transition**:
  `.venv/bin/python wb todo set <id> doing` arms the
  schedule at the default `15m` cadence in the same
  write whenever the todo declares neither a cadence
  nor the opt-out — no flag to remember (15m is the
  default because it catches dead or erroring work a
  lot earlier). Pass `--progress <cadence>` to
  override (or at creation via
  `wb todo new <bundle> "<title>" --progress 30m`), and
  `--no-progress` only for a todo that genuinely should
  never be monitored (it records `progress_check: off`).
  Arming writes `progress_check` / `progress_armed`
  onto the todo through lib/ — the only write path;
  never hand-edit the fields. The registry entry rides
  the same write — its outcome shows in the command's
  JSON as `progress_entry`.
- **Checkpoints are todo-body lines**, appended through
  `wb todo set <id> doing --note "progress-checkpoint:
  <ISO-8601 UTC> — <what moved>"`. The todo file stays
  the progress record; chat is never the record. Whoever
  does the work checkpoints at meaningful progress; a
  driver run checkpoints what it observes.
- **Disarm is automatic**: a move to `done` or `blocked`
  clears both progress fields in the same write, and the
  same writer call deletes the todo's registry entry.
  The doctor backs the discipline both ways:
  `todo-progress-unarmed` flags planned `doing` work with
  no schedule, `todo-progress-orphan` flags arming that
  outlived its work.
- **The driver reads one thing**: `.venv/bin/python wb
  progress` (JSON: per project, the armed todos with
  last checkpoint, missed checks, and the stall verdict —
  stalled at 2 missed checks). Acting on the verdict is
  the driver's business.
- **Scope guard**: a driver run nudges or resumes only
  inside the work's existing scope, never blind-retries
  irreversible or login-limited actions, and reports to
  the owner only milestones, stalls, blockers, and
  completion — never heartbeats. Work already covered by
  a completion handoff (delegated agents, browser tasks)
  gets no duplicate monitor.

Platform schedule template — the agent instantiates one
per bundle at arm time, owned by the work's goal,
delivering to the originating chat:

```text
Progress driver for bundle <bundle-id> (this repo).

Each run:
1. Run `.venv/bin/python wb progress` from the repo
   root; take the armed todos in bundle <bundle-id>.
2. If none remain, delete this schedule and stop.
3. For each armed todo: if the work moved since the
   last checkpoint (its own records show it), append
   the checkpoint:
   wb todo set <id> doing --note "progress-checkpoint:
   <now, ISO-8601 UTC> — <what moved>"
4. If a todo reads stalled, diagnose from its body and
   the work's run records; nudge or resume the work
   inside its existing scope, and note the diagnosis
   in the todo.
5. If a todo is blocked or needs the owner's decision:
   wb todo set <id> blocked --note "<the reason>" and
   report it once to the originating chat.
6. Report milestones and completion only. No heartbeat
   messages.
```

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
  reference) and the `another-project` repo (registered by owner's ruling,
  2026-10-26; untracked adoption footprint only).
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
