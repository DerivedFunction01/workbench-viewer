"""The per-project companion manifest: `workbench.yaml`.

Format (spec'd in context/architecture.md): a RESTRICTED YAML
subset — flat `key: value` lines, `#` comments, blank lines
ignored, plain scalar values. No nesting, no lists, no
anchors: stdlib has no YAML, and the manifest needs nothing
more. Strictness is the feature: unknown keys and malformed
lines are hard errors, so a typo surfaces instead of silently
doing nothing.

The catalog classification rides in flat keys
(catalog_origin / catalog_generality / catalog_use_case)
for the same reason: the shared vocabulary is nested in
the scheduler's entries, but this format cannot nest —
the axes and their value words are what is shared.

All declared paths are relative to the repo root and must not
escape it.
"""

from dataclasses import dataclass, field
from pathlib import Path

KNOWN_KEYS = ("name", "slug", "registry", "plans", "mockups",
              "archive", "registration",
              "catalog_origin", "catalog_generality",
              "catalog_use_case")
PATH_KEYS = ("registry", "plans", "mockups", "archive")

# The catalog classification (classified-schedule-catalog
# plan, Step 3): the manifest is this system's adoption
# unit, classified under the same axes as the scheduler's
# catalog — in flat keys, because this format is flat by
# design. The vocabulary mirrors the scheduler registry's
# (origin / generality words are its ORIGINS /
# GENERALITIES; use_case is its lowercase-hyphenated
# label). An adopting project's manifest is a copy of the
# template specimen with its own fields filled, so the
# classification of record is origin hand, generality
# parameterized (the manifest's own fields are the
# declared parameters), use_case work-tracking. The keys
# are optional as a set (a pre-classification manifest
# loads unchanged) but all-or-nothing: a partial
# classification is a typo-class error, never a default.
CATALOG_KEYS = ("catalog_origin", "catalog_generality",
                "catalog_use_case")
CATALOG_ORIGINS = ("hand", "machine", "per-session")
CATALOG_GENERALITIES = ("generalized", "parameterized",
                        "deployment-specific")

# The registration postures a manifest may declare. Absent
# (the default) is a full adoption: the project's plan
# corpus is held to the plan standard. `as-is` records
# that the project registered its corpus as found — its
# plans predate the standard and are not backfilled — so
# the doctor treats its plan-status findings as
# informational (computed, never in the finding set).
REGISTRATION_AS_IS = "as-is"


class ManifestError(ValueError):
    pass


@dataclass
class Manifest:
    root: Path
    name: str
    slug: str
    registry: Path | None = None   # absolute, resolved
    plans: Path | None = None
    mockups: Path | None = None
    archive: Path | None = None
    declared: dict = field(default_factory=dict)

    @property
    def registered_as_is(self) -> bool:
        """True when the manifest declares
        `registration: as-is` — the project registered
        its plan corpus as found (pre-standard, no
        backfill). Posture is per-project data, read from
        the project's own manifest, never a name in code."""
        return self.declared.get("registration") \
            == REGISTRATION_AS_IS

    @property
    def catalog(self) -> dict | None:
        """The manifest's catalog classification as one
        block ({origin, generality, use_case}), or None
        when the manifest predates classification.
        Validation at load guarantees the block is
        complete and in-vocabulary when present."""
        if "catalog_origin" not in self.declared:
            return None
        return {
            "origin": self.declared["catalog_origin"],
            "generality": self.declared["catalog_generality"],
            "use_case": self.declared["catalog_use_case"],
        }

    @property
    def db_path(self) -> Path | None:
        return self.registry

    @property
    def export_path(self) -> Path | None:
        if self.registry is None:
            return None
        return self.registry.with_name("registry.json")


def _parse_lines(text: str, source: Path) -> dict:
    out = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ManifestError(
                f"{source}:{lineno}: expected 'key: value', "
                f"got {raw!r}")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # An inline comment ends the value (values are plain
        # scalars; a literal # in a path is not supported).
        if " #" in value:
            value = value.split(" #", 1)[0].strip()
        if key not in KNOWN_KEYS:
            raise ManifestError(
                f"{source}:{lineno}: unknown key {key!r} "
                f"(known: {', '.join(KNOWN_KEYS)})")
        if key in out:
            raise ManifestError(
                f"{source}:{lineno}: duplicate key {key!r}")
        if not value:
            raise ManifestError(
                f"{source}:{lineno}: empty value for {key!r}")
        out[key] = value
    return out


def _resolve(root: Path, rel: str, source: Path, key: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        raise ManifestError(
            f"{source}: {key} must be relative to the repo "
            f"root, got {rel!r}")
    resolved = (root / p).resolve()
    if root.resolve() not in resolved.parents and resolved != root.resolve():
        raise ManifestError(
            f"{source}: {key} escapes the repo root: {rel!r}")
    return resolved


def _check_catalog(data: dict, source: Path) -> None:
    """The catalog keys are all-or-nothing, and their
    values come from the shared vocabulary (the scheduler
    registry's axes). A partial or out-of-vocabulary
    classification is a hard error, like any other typo
    in this format."""
    present = [k for k in CATALOG_KEYS if k in data]
    if not present:
        return
    if len(present) != len(CATALOG_KEYS):
        missing = [k for k in CATALOG_KEYS if k not in data]
        raise ManifestError(
            f"{source}: catalog classification is "
            f"all-or-nothing; missing: {', '.join(missing)}")
    if data["catalog_origin"] not in CATALOG_ORIGINS:
        raise ManifestError(
            f"{source}: catalog_origin must be one of "
            f"{', '.join(CATALOG_ORIGINS)}, got "
            f"{data['catalog_origin']!r}")
    if data["catalog_generality"] not in CATALOG_GENERALITIES:
        raise ManifestError(
            f"{source}: catalog_generality must be one of "
            f"{', '.join(CATALOG_GENERALITIES)}, got "
            f"{data['catalog_generality']!r}")
    use_case = data["catalog_use_case"]
    if use_case != use_case.lower() or " " in use_case \
            or "_" in use_case:
        raise ManifestError(
            f"{source}: catalog_use_case is a lowercase "
            f"hyphenated label, got {use_case!r}")


def load_manifest(manifest_path: Path) -> Manifest:
    """Parse and resolve one manifest file. Raises
    ManifestError on any format or path problem."""
    manifest_path = Path(manifest_path)
    root = manifest_path.resolve().parent
    data = _parse_lines(manifest_path.read_text(encoding="utf-8"),
                        manifest_path)
    if "name" not in data:
        raise ManifestError(f"{manifest_path}: 'name' is required")
    _check_catalog(data, manifest_path)
    slug = data.get("slug") or root.name
    resolved = {}
    for key in PATH_KEYS:
        if key in data:
            resolved[key] = _resolve(root, data[key], manifest_path,
                                     key)
    registry = resolved.get("registry")
    # mockups/archive default to siblings of the registry DB.
    if registry is not None:
        if "mockups" not in resolved:
            resolved["mockups"] = registry.parent / "entries"
        if "archive" not in resolved:
            resolved["archive"] = registry.parent / "archive"
    return Manifest(root=root, name=data["name"], slug=slug,
                    registry=registry,
                    plans=resolved.get("plans"),
                    mockups=resolved.get("mockups"),
                    archive=resolved.get("archive"),
                    declared=data)
