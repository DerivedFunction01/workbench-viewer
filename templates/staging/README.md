# Staging

The designated pre-home for workbench items that do not have a proper
home yet: plans, bundles, mocks, and artifacts whose canonical project
does not exist yet — above all, a plan whose work creates a new repo,
which needs somewhere legitimate to live until that repo exists.

Staging is an ordinary workbench project: same manifest, same registry
model, same plan syntax. Staged items are visible in the workbench
viewer from day one and carry the same hygiene as any project's work.

## Graduating an item

Graduation is a deliberate act with a record, never a silent
relocation. The procedure per item kind is written out in full below
(Step 4 of the founding plan), and every graduation appends one line
to `GRADUATIONS.md` (date, item, from, to).

### Plan or bundle

1. Move the plan file (or the bundle directory) into the target
   project's `.plans/`.
2. Add a `Graduated:` header line to the plan file naming the target
   project and the date.
3. Append the line to `GRADUATIONS.md`.

### Entry with a folder (entry-dir)

1. Register it in the target with `wb add` (same slug, kind, and
   title) — `wb add` creates the target folder itself and refuses
   if one already exists, so registration comes first.
2. Copy the staged entry folder's files over the target folder's
   files.
3. Run `wb verify --accept-drift` in the target, binding the
   entry's fingerprint to the graduated content.
4. Archive the staging entry with `wb archive`.

### Entry without a folder (artifact-slug / external)

1. Register it in the target with `wb add` (same slug, kind,
   `source_kind`, and `source_ref`).
2. Archive the staging entry with `wb archive`.

The record of an entry's graduation is the `GRADUATIONS.md` line
plus the archive event in the staging entry's own history
(`wb archive` carries no note field).

Registry rows are never moved between databases directly: an entry
graduates by being created in the target through `wb add` and archived
in staging in the same pass, so the mutation path stays inside `lib/`
in both projects.
