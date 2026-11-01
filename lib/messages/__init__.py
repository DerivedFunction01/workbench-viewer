"""The viewer-tied message store (repo-home spec §5).

Messages live in a SQLite database owned by the VIEWER — in
the server's state directory, never inside a project repo,
never in a project registry (the owner's ruling, repo-home spec
D4). Projects are referenced by slug only. The store carries
its OWN `user_version` lineage, independent of the registry
schema: adopting the viewer needs no registry migration to
receive messages.

Same store discipline as lib/registry.py: WAL + busy_timeout
on every connection, ONE short BEGIN IMMEDIATE per mutation,
append-only `message_events` audit (a purged message's rows
are deleted; its event rows remain). Every function takes an
explicit db path so tests run on temp files. Stdlib only.

State machine (spec §5.2), enforced here — the ONLY path:
  draft -> sent -> acknowledged -> done -> archived -> purged
Side exits: draft -> purged and done -> purged happen only
through the manual purge controls (spec §5.4); the cleanup
pass (cleanup()) drives draft -> purged, done -> archived,
archived -> purged on the §5.3 schedule, plus orphan and
cap archiving. Sent-but-unacknowledged messages are never
purged by anything automatic.

Watcher core (spec §15.1): every transition INTO `sent`
also writes one row to the `outbox` table IN THE SAME
TRANSACTION as the state change — an event can never
exist without its state change or vice versa. Consumers
poll list_outbox(after=<id>) and keep their own
checkpoints; the cleanup pass prunes outbox rows once
they age past the archived horizon. The server's notify
checkpoint (meta key `notify_checkpoint`) is read/written
through the helpers here so no SQL lives outside lib/.

Annotations (spec §12): an annotation is a message whose
anchor is a SELECTION — a text passage in a plan
(anchor_type `text`) or a component in a mockup exhibit
(anchor_type `component`). The selection payload rides in
the nullable `selection` JSON column (schema v3): quote +
surrounding context for text, the deterministic manifest
component id for components. Raw offsets are REFUSED at
create — quote + context is the anchor, re-located at
read time by lib/annotations.py (never stored back).

The module is a package now (800-line cap split):
constants+policy, the store, selection validation,
the lifecycle, and outbox + cleanup live in the
submodules; this __init__ re-exports the existing
public surface so `import lib.messages` and every
current importer keep working unchanged.
"""

from .constants import (ANCHOR_TYPES, AUTHORS,
                        CONTEXT_CAP, DEFAULT_POLICY,
                        OFFSET_KEYS, QUOTE_CAP,
                        SCHEMA_V1, SCHEMA_V2, SCHEMA_V3,
                        SCHEMA_VERSION, STATES,
                        TRANSITIONS, MessageError)
from .store import _event, connect, message_dict
from .lifecycle import (_outbox, archive_message,
                        counts_by_state, create_message,
                        events_for, fetch_unacked,
                        get_message, list_messages,
                        mark_done, purge_message,
                        send_message, update_draft)
from .cleanup import (cleanup, list_outbox,
                       notify_checkpoint, purge_archived,
                       purge_drafts,
                       set_notify_checkpoint, store_stats)
