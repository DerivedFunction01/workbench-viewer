"""Registry constants, field tuples, schema, and errors.

One slice of lib/registry (see the package docstring):
the vocabulary every other registry submodule shares —
statuses, kinds, the entry/todo field tuples, the v1
schema, the slug rule, and the typed refusals.
"""

import re

STATUSES = ("canonical", "implemented", "deferred",
            "unexplored", "hard-gate", "abandoned")
KINDS = ("mockup", "prototype", "test-route",
         "component-variant", "storyboard", "artifact")
SOURCE_KINDS = ("entry-dir", "artifact-slug", "external")
TODO_STATUSES = ("todo", "doing", "done")
REVIEW_DISPOSITIONS = ("approve", "needs-changes", "stale")
ACTORS = ("cli", "viewer", "stale-check")

ENTRY_FIELDS = ("id", "title", "kind", "status", "gate",
                "ruling_text", "ruling_date", "spec_ref",
                "plan_ref", "source_kind", "source_ref",
                "entry_dir", "main_file", "content_sha256",
                "config_path", "state_schema", "state_json",
                "owner_thread", "owner_label", "deploy_class",
                "created_at", "updated_at", "status_changed_at",
                "last_verified_at", "archived", "archived_at",
                "superseded_by", "version")
DEPLOY_CLASSES = ("standard", "deployed")
SETTABLE_FIELDS = ("title", "gate", "ruling_text", "spec_ref",
                   "plan_ref", "config_path", "main_file",
                   "source_ref")
TODO_FIELDS = ("id", "title", "status", "notes", "link_kind",
               "link_ref", "created_at", "updated_at", "version")

SCHEMA_V1 = """
CREATE TABLE entries (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'mockup',
  status TEXT NOT NULL DEFAULT 'unexplored',
  gate TEXT,
  ruling_text TEXT,
  ruling_date TEXT,
  spec_ref TEXT,
  plan_ref TEXT,
  source_kind TEXT NOT NULL DEFAULT 'entry-dir',
  source_ref TEXT,
  entry_dir TEXT,
  main_file TEXT,
  content_sha256 TEXT,
  config_path TEXT,
  state_schema TEXT,
  state_json TEXT,
  owner_thread TEXT,
  owner_label TEXT,
  deploy_class TEXT NOT NULL DEFAULT 'standard',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status_changed_at TEXT NOT NULL,
  last_verified_at TEXT,
  archived INTEGER NOT NULL DEFAULT 0,
  archived_at TEXT,
  superseded_by TEXT,
  version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_id TEXT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  verb TEXT NOT NULL,
  field TEXT,
  old TEXT,
  new TEXT,
  note TEXT
);
CREATE TABLE todos (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'todo',
  notes TEXT,
  link_kind TEXT,
  link_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE todo_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id TEXT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  verb TEXT NOT NULL,
  field TEXT,
  old TEXT,
  new TEXT,
  note TEXT
);
"""

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class RegistryError(Exception):
    """A mutation was refused, with a human-readable reason."""


class VersionConflict(RegistryError):
    def __init__(self, subject, expected, current):
        super().__init__(
            f"{subject}: version conflict — expected "
            f"{expected}, current version is {current}")
        self.current_version = current


class RulingRequired(RegistryError):
    pass


class UniformityRefused(RegistryError):
    def __init__(self, entry_id, findings):
        self.findings = findings
        detail = "; ".join(f["message"] for f in findings)
        super().__init__(
            f"{entry_id}: uniformity validators refuse this "
            f"transition: {detail}")


def check_slug(slug: str):
    if not _SLUG_RE.match(slug or ""):
        raise RegistryError(
            f"bad slug {slug!r}: lowercase letters, digits, "
            f"hyphens; must start with a letter or digit")
