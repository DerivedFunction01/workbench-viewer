# Manifest template — the adoption specimen

The workbench manifest (`workbench.yaml` at a project
root) is this system's adoption unit, classified under
the shared catalog axes like a scheduler catalog entry:
adopting a project is copying the template and filling
its declared parameters — the manifest's own fields.

- `workbench.yaml` in this directory is the specimen:
  copy it to the adopting repo's root and fill every
  field. Required: `name`, `registry`, `plans`.
  Optional: `slug` (defaults to the directory name),
  `mockups` / `archive` (default to siblings of the
  registry file), `registration` (`as-is` records a
  corpus registered as found, pre-standard).
- The classification of record rides in the template:
  `catalog_origin: hand`, `catalog_generality:
  parameterized`, `catalog_use_case: work-tracking`.
  The manifest format is flat by design, so the axes
  ride in flat keys; the vocabulary — the axes and
  their value words — is the scheduler catalog's.
  Classification is descriptive, not activating: a
  classified manifest admits nothing anywhere; the
  sweep discovers a project by the manifest's presence,
  classified or not.
- The seeded staging manifest under `templates/staging/`
  is a filled instance of this template, kept with its
  own bootstrap procedure.
