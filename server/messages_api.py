"""Message-store API: maintenance loops and endpoints.

One slice of the companion server: the store handles
(db path + cleanup policy from config), the cleanup
and notify background loops, the annotation-anchor
context join, the message endpoint functions, the
outbox feed, the manual cleanup endpoint, and the
effective-settings payload.
"""

import sys
import threading
import time

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))  # for lib/
sys.path.insert(0, str(HERE))        # for config (flat, donor-style)

import config as cfgmod  # noqa: E402
from lib import annotations as ann_mod  # noqa: E402
from lib import messages as msg_mod  # noqa: E402
from lib import notify as notify_mod  # noqa: E402
from lib.util import now_iso  # noqa: E402

from common import (CFG, ApiError, find_project,  # noqa: E402
                    get_sweep)

# ================================================================
# REPO-HOME ADDITIONS — BEGIN (repo-home spec §§5-7)
# Everything in this block is additive: the message store
# (lib/messages.py), its cleanup lifecycle, and the /api
# namespace. All store access goes through lib/ — no SQL
# here, per the one-mutation-path rule. The UI for these
# endpoints is a later phase; this block is backend only.
# ================================================================

MSG_DB = cfgmod.messages_db_path(CFG)
MSG_POLICY = cfgmod.messages_policy(CFG)


def run_message_cleanup(reason: str) -> dict:
    """One cleanup pass over the viewer message store with
    the sweep's current slugs as the known-project set.
    Never raises: a cleanup failure must not block the
    server (counts are logged either way)."""
    try:
        slugs = [p.slug for p in get_sweep().projects]
        counts = msg_mod.cleanup(MSG_DB, known_slugs=slugs,
                                 policy=MSG_POLICY)
        print(f"workbench-viewer: message cleanup ({reason}):"
              f" {counts}", file=sys.stderr)
        return counts
    except Exception as e:  # containment, like the feeds
        print(f"workbench-viewer: message cleanup ({reason})"
              f" failed: {e}", file=sys.stderr)
        return {"error": str(e)[:200]}


def _message_cleanup_loop():
    while True:
        time.sleep(24 * 3600)
        run_message_cleanup("daily")


def fire_pending_notifications() -> dict:
    """One watcher-notify pass (spec §15.1): read outbox
    rows past the store's notify checkpoint, fire the
    configured targets for each, then advance the
    checkpoint past the ATTEMPTED rows (notify is a
    wake-up; the durable record is the outbox + the
    messages). Never raises — a dead target is logged,
    never a server failure."""
    targets = cfgmod.notify_targets(CFG)
    if not targets["webhook"] and not targets["command"]:
        return {"events": 0, "results": []}
    try:
        checkpoint = msg_mod.notify_checkpoint(MSG_DB)
        events = msg_mod.list_outbox(MSG_DB, after=checkpoint)
        if not events:
            return {"events": 0, "results": []}
        results = notify_mod.fire_targets(targets, events)
        msg_mod.set_notify_checkpoint(MSG_DB, events[-1]["id"])
        failed = [r for r in results if not r["ok"]]
        if failed:
            print(f"workbench-viewer: notify fired "
                  f"{len(events)} event(s), {len(failed)} "
                  f"target failure(s): {failed}",
                  file=sys.stderr)
        return {"events": len(events), "results": results}
    except Exception as e:  # containment, like the feeds
        print(f"workbench-viewer: notify pass failed: {e}",
              file=sys.stderr)
        return {"error": str(e)[:200]}


def _notify_loop():
    while True:
        fire_pending_notifications()
        time.sleep(max(5, CFG["messages_notify_poll_s"]))


def start_message_maintenance():
    """Spec §5.3: the cleanup pass runs at server start and
    daily inside the server process. No cron. Spec §15.1:
    when notify targets are configured, a poll loop fires
    them for new outbox rows (its checkpoint lives in the
    store's meta, in lib/)."""
    run_message_cleanup("startup")
    thread = threading.Thread(target=_message_cleanup_loop,
                              name="message-cleanup",
                              daemon=True)
    thread.start()
    targets = cfgmod.notify_targets(CFG)
    if targets["webhook"] or targets["command"]:
        notify_thread = threading.Thread(
            target=_notify_loop, name="message-notify",
            daemon=True)
        notify_thread.start()


def with_anchor_context(message: dict) -> dict:
    """Attach the derived anchor_context (§12/§13) to an
    annotation message: lib re-location against the
    target's CURRENT state, computed at read, never
    stored. The project resolves from the sweep by the
    message's project_slug; an unresolvable project still
    yields a context (target_missing) — the annotation
    itself is never dropped."""
    if message.get("selection"):
        slug = message.get("project_slug")
        project = find_project(slug) if slug else None
        message["anchor_context"] = \
            ann_mod.resolve_context(project, message)
    return message


def messages_list(query: dict) -> dict:
    if query.get("pickup") == "1":
        # Agent pickup (spec D3): the fetch acknowledges.
        # The pickup payload IS the agent's work order, so
        # each annotation rides with its anchor_context
        # (§13: what it points at, re-located now).
        picked = msg_mod.fetch_unacked(
            MSG_DB, query.get("project") or None)
        return {"messages": [with_anchor_context(m)
                             for m in picked],
                "picked_up": len(picked),
                "captured_at": now_iso()}
    rows = msg_mod.list_messages(
        MSG_DB, project_slug=query.get("project") or None,
        state=query.get("state") or None,
        anchor_type=query.get("anchor_type") or None,
        anchor_ref=query.get("anchor_ref") or None,
        badge_days=CFG["messages_awaiting_badge_days"])
    return {"messages": [with_anchor_context(r) for r in rows],
            "captured_at": now_iso()}


def message_create(body: dict) -> dict:
    if not body.get("author"):
        raise ApiError(400, "message needs an author "
                            "(owner|Muse)")
    try:
        message = msg_mod.create_message(
            MSG_DB, author=body["author"],
            body=body.get("body") or "",
            project_slug=body.get("project_slug"),
            anchor_type=body.get("anchor_type") or "none",
            anchor_ref=body.get("anchor_ref"),
            showcase=body.get("showcase"),
            parent_id=body.get("parent_id"),
            send=bool(body.get("send")),
            selection=body.get("selection"))
    except msg_mod.MessageError as e:
        raise ApiError(400, str(e))
    return {"message": message}


def message_update_body(message_id: int, body: dict) -> dict:
    """POST /api/messages/<id>/body: the annotation
    composer's draft autosave (D7 — drafts are real
    draft-state messages; lib update_draft is the one
    path and refuses non-drafts)."""
    if not isinstance(body.get("body"), str):
        raise ApiError(400, "draft body update needs a "
                            "string \"body\"")
    try:
        message = msg_mod.update_draft(MSG_DB, message_id,
                                       body["body"])
    except msg_mod.MessageError as e:
        raise ApiError(400, str(e))
    return {"message": message}


def message_done(message_id: int) -> dict:
    try:
        message = msg_mod.mark_done(MSG_DB, message_id)
    except msg_mod.MessageError as e:
        raise ApiError(400, str(e))
    return {"message": message}


def message_send(message_id: int) -> dict:
    """draft -> sent for an existing draft (the Inbox's
    send action; lib send_message is the one path, and the
    outbox row lands in its transaction, §15.1)."""
    try:
        message = msg_mod.send_message(MSG_DB, message_id)
    except msg_mod.MessageError as e:
        raise ApiError(400, str(e))
    return {"message": message}


def message_archive(message_id: int) -> dict:
    try:
        message = msg_mod.archive_message(MSG_DB, message_id)
    except msg_mod.MessageError as e:
        raise ApiError(400, str(e))
    return {"message": message}


def outbox_feed(query: dict) -> dict:
    """GET /api/outbox?after=<id> (spec §15.1): the watcher
    poll. Consumers keep their own checkpoints; reading
    never consumes."""
    after = query.get("after") or "0"
    try:
        after_id = int(after)
    except ValueError:
        raise ApiError(400, f"after must be an event id, "
                            f"got {after!r}")
    events = msg_mod.list_outbox(MSG_DB, after=after_id)
    return {"events": events,
            "last_id": events[-1]["id"] if events
                       else after_id,
            "captured_at": now_iso()}


def message_cleanup(body: dict) -> dict:
    """Guarded manual controls (§5.4): cleanup now, or a
    per-state purge. All require an explicit confirm."""
    if body.get("confirm") is not True:
        raise ApiError(400, "guarded mutation: pass "
                            "{\"confirm\": true}")
    purge = body.get("purge")
    if purge == "archived":
        return {"purged": msg_mod.purge_archived(MSG_DB),
                "captured_at": now_iso()}
    if purge == "drafts":
        return {"purged": msg_mod.purge_drafts(MSG_DB),
                "captured_at": now_iso()}
    if purge is not None:
        raise ApiError(400, f"unknown purge: {purge!r}")
    return {"cleanup": run_message_cleanup("manual"),
            "captured_at": now_iso()}


def effective_settings() -> dict:
    """GET /api/settings/effective: the seam's resolved
    values, read-only (Settings → Workspace, spec §3).
    Anything secret-shaped is excluded by key name — the
    config carries no secrets today, and this keeps it
    that way by construction."""
    hidden = ("secret", "token", "password", "key")
    shown = {k: v for k, v in CFG.items()
             if not any(h in k.lower() for h in hidden)}
    try:
        stats = msg_mod.store_stats(MSG_DB)
    except Exception as e:
        stats = {"error": str(e)[:200]}
    return {
        "config": shown,
        "config_hash": cfgmod.config_hash(CFG),
        "config_file": str(cfgmod.config_path()),
        "messages": {"db": str(MSG_DB),
                     "policy": MSG_POLICY, **stats},
        "captured_at": now_iso(),
    }
