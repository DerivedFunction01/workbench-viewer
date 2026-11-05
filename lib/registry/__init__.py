"""The per-project registry store: schema, mutations, history.

THE mutation path. The `wb` CLI and the companion server both
write exclusively through the functions in this module; the
server holds no SQL of its own. Modeled on the prototype's
calendar store discipline (subplan 09): schema via
`PRAGMA user_version`, WAL + busy_timeout on every connection,
ONE short BEGIN IMMEDIATE per mutation, per-row `version`
compare-and-swap — a stale version fails naming the newer
state, never a silent overwrite. History is append-only and
kept whole; "latest" is a derivation, not a destructive
update. Every function takes an explicit db path so tests run
on temp files.

Ruled vs derived (the split is the design): `status` changes
only through `set_status`/`supersede` carrying a ruling note.
Staleness is computed elsewhere (lib/staleness.py) and never
written here.

The module is a package now (800-line cap split):
constants+errors, the store, entry CRUD + history, and
todos live in the submodules; this __init__ re-exports
the existing public surface so `import lib.registry`
and every current importer keep working unchanged.
"""

import json

from ..util import sha256_file
from .constants import (ACTORS, ENTRY_FIELDS, KINDS,
                        REVIEW_DISPOSITIONS,
                        SETTABLE_FIELDS, SOURCE_KINDS,
                        STATUSES, TODO_FIELDS,
                        TODO_STATUSES, SCHEMA_V1,
                        RegistryError, RulingRequired,
                        UniformityRefused, VersionConflict,
                        check_slug)
from .store import (_append_history, _tx, connect,
                    connect_readonly, registry_state_token)
from .entries import (add_entry, apply_export,
                      archive_entry, entry_dict,
                      get_entry, history_for,
                      init_registry, latest_review,
                      list_entries, record_stale_check,
                      review_entry, set_fields,
                      set_state, set_state_schema,
                      set_status, supersede,
                      unarchive_entry, verify_entry)
from .todos import (add_todo, list_todos,
                    set_todo_fields, set_todo_status,
                    todo_dict)
