"""The per-project companion manifest: `workbench.yaml`.

Format (spec'd in context/architecture.md): a RESTRICTED YAML
subset — flat `key: value` lines, `#` comments, blank lines
ignored, plain scalar values. No nesting, no lists, no
anchors: stdlib has no YAML, and the manifest needs nothing
more. Strictness is the feature: unknown keys and malformed
lines are hard errors, so a typo surfaces instead of silently
doing nothing.

All declared paths are relative to the repo root and must not
escape it.
"""

from dataclasses import dataclass, field
from pathlib import Path

KNOWN_KEYS = ("name", "slug", "registry", "plans", "mockups",
              "archive", "registration")
PATH_KEYS = ("registry", "plans", "mockups", "archive")

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


def load_manifest(manifest_path: Path) -> Manifest:
    """Parse and resolve one manifest file. Raises
    ManifestError on any format or path problem."""
    manifest_path = Path(manifest_path)
    root = manifest_path.resolve().parent
    data = _parse_lines(manifest_path.read_text(encoding="utf-8"),
                        manifest_path)
    if "name" not in data:
        raise ManifestError(f"{manifest_path}: 'name' is required")
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
