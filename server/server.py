#!/usr/bin/env python3
"""Workbench Viewer companion server — HTTP layer only.

Routes, feeds assembled from lib/ reads, guarded file saves,
and mutation endpoints that delegate to lib/. This module
contains NO SQL and no mutation logic of its own: if a write
is missing, it is added to lib/ first (the one-mutation-path
rule — wb and this server are both thin callers over lib/).

Write surface, exactly: guarded file saves (lib/files) +
lib/ registry mutations, each paired with an export
regeneration. Actor on every server-side write: "viewer".

Per-project containment: every project feed is built
independently; a locked or broken project DB degrades only
that project's payload (`degraded: true` + reason), never
the request.

Single instance: an flock on state/server.lock, held for the
process's life, carrying {pid, port, started_at, version}.
"""

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, \
    ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))  # for lib/
sys.path.insert(0, str(HERE))        # for config (flat, donor-style)

import config as cfgmod  # noqa: E402
from lib import active as active_mod  # noqa: E402
from lib import bundles as bundle_mod  # noqa: E402
from lib import diffs as diff_mod  # noqa: E402
from lib import export as export_mod  # noqa: E402
from lib import files as files_mod  # noqa: E402
from lib import home as home_mod  # noqa: E402
from lib import messages as msg_mod  # noqa: E402
from lib import notify as notify_mod  # noqa: E402
from lib import worktrees as wt_mod  # noqa: E402
from lib import registry as reg  # noqa: E402
from lib import staleness  # noqa: E402
from lib import sweep as sweep_mod  # noqa: E402
from lib import validators as val_mod  # noqa: E402
from lib.plans import bundles as bundle_parser  # noqa: E402
from lib.plans import parser as plan_parser  # noqa: E402
from lib.util import now_iso  # noqa: E402

VERSION = "1.0.0"
MAX_BODY = 1024 * 1024

CFG = cfgmod.load()
STARTED_AT = datetime.now(timezone.utc)
_lock_fd = None
_sweep_cache = {"at": 0.0, "result": None}


def _git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse",
             "--short", "HEAD"], capture_output=True, text=True,
            timeout=3)
        return out.stdout.strip() or None
    except Exception:
        return None


COMMIT = _git_head()


# ----------------------------------------------------------------
# Sweep cache
# ----------------------------------------------------------------

def get_sweep(force: bool = False):
    now = time.monotonic()
    ttl = CFG["sweep_ttl_s"]
    if not force and _sweep_cache["result"] is not None \
            and now - _sweep_cache["at"] < ttl:
        return _sweep_cache["result"]
    result = sweep_mod.sweep(
        cfgmod.sweep_roots(CFG),
        manifest_name=CFG["sweep_manifest"],
        max_depth=CFG["sweep_max_depth"],
        prune=CFG["sweep_prune"])
    _sweep_cache.update(at=now, result=result)
    return result


def find_project(slug: str):
    return get_sweep().by_slug(slug)


def layout_of(project):
    m = project.manifest
    return (m.mockups, m.archive)


def degraded(base: dict, exc: Exception) -> dict:
    out = dict(base)
    out["degraded"] = True
    out["reason"] = str(exc)[:200]
    return out


# ----------------------------------------------------------------
# Feed builders (reads; each contained per project)
# ----------------------------------------------------------------

def entry_detail(db_path, entry_id) -> dict:
    entry = reg.get_entry(db_path, entry_id)
    latest = reg.latest_review(db_path, entry_id)
    thresholds = staleness.load_thresholds(db_path)
    return {
        "entry": entry,
        "derived": staleness.entry_staleness(
            entry, thresholds=thresholds),
        "approval": staleness.approval_coverage(entry, latest),
        "latest_review": latest,
        "history": reg.history_for(db_path, entry_id),
        "files": files_mod.list_entry_files(entry),
    }


def mockups_feed(project, *, archived: bool) -> dict:
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False}
    if m.registry is None:
        return {**base, "available": False,
                "reason": "no registry declared in manifest",
                "entries": [], "triage": [],
                "reconcile": None}
    if not m.registry.is_file():
        return {**base, "available": False,
                "reason": "registry not initialized yet "
                          "(wb init creates it)",
                "entries": [], "triage": [],
                "reconcile": None}
    try:
        data = export_mod.build_export(m.registry,
                                       project=project.slug)
        entries = [e for e in data["entries"]
                   if bool(e["archived"]) == archived]
        triage = []
        for e in data["entries"]:
            if e["archived"]:
                continue
            reasons = staleness.triage_reasons(
                e, e["derived"],
                reg.latest_review(m.registry, e["id"]))
            if reasons:
                triage.append({"id": e["id"], "title": e["title"],
                               "reasons": reasons})
        return {**base, "available": True, "entries": entries,
                "triage": triage,
                "reconcile": val_mod.reconcile(
                    m.registry, layout_of(project))}
    except Exception as e:
        return degraded({**base, "available": True,
                         "entries": [], "triage": [],
                         "reconcile": None}, e)


def todos_feed(project) -> dict:
    """Todos read from bundle todo FILES (live-work spec
    §3.7: file todos supersede the registry DB). The DB is
    read ONLY as the §3.7 fallback — a project with DB
    todos and no file todos shows its DB todos until they
    are imported; the moment file todos exist they are the
    source and the DB rows are not merged in. Invalid
    front-matter todos stay in the list, flagged, and their
    parser errors ride on the feed — never a silent skip."""
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False}
    file_todos, errors = [], []
    if m.plans is not None and m.plans.is_dir():
        try:
            for bundle in bundle_parser.list_bundles(m.plans):
                errors.extend(bundle["errors"])
                file_todos.extend(bundle["todos"])
        except Exception as e:
            return degraded({**base, "available": True,
                             "source": "files", "todos": [],
                             "errors": errors}, e)
    if file_todos:
        return {**base, "available": True, "source": "files",
                "todos": file_todos, "errors": errors}
    if m.registry is not None and m.registry.is_file():
        try:
            db_todos = reg.list_todos(m.registry)
        except Exception as e:
            return degraded({**base, "available": True,
                             "source": "db-fallback",
                             "todos": [], "errors": errors}, e)
        if db_todos:
            return {**base, "available": True,
                    "source": "db-fallback",
                    "todos": [{**t, "source": "db",
                               "bundle": None, "feature": None,
                               "worktree": None, "valid": True,
                               "errors": []}
                              for t in db_todos],
                    "errors": errors}
        return {**base, "available": True, "source": "files",
                "todos": [], "errors": errors}
    if m.plans is not None and m.plans.is_dir():
        return {**base, "available": True, "source": "files",
                "todos": [], "errors": errors}
    return {**base, "available": False, "source": "files",
            "todos": [], "errors": errors}


def plans_feed(project) -> dict:
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False}
    if m.plans is None or not m.plans.is_dir():
        return {**base, "available": False, "plans": [],
                "bundles": []}
    try:
        return {**base, "available": True,
                "plans": plan_parser.list_plans(m.plans),
                "bundles": bundle_parser.list_bundles(m.plans)}
    except Exception as e:
        return degraded({**base, "available": True,
                         "plans": [], "bundles": []}, e)


def board_feed() -> dict:
    result = get_sweep()
    lanes = {"todo": [], "doing": [], "blocked": [],
             "done": []}
    plan_cards = {"todo": [], "doing": [], "done": []}
    review_queue = []
    errors = []
    for project in result.projects:
        tf = todos_feed(project)
        if tf["degraded"]:
            errors.append({"slug": project.slug,
                           "reason": tf["reason"]})
        for err in tf.get("errors", []):
            errors.append({"slug": project.slug, **err})
        for todo in tf["todos"]:
            if not todo.get("valid", True) \
                    or todo.get("status") not in lanes:
                continue  # invalid todos surface as errors
            lanes[todo["status"]].append(
                {**todo, "project": project.slug,
                 "project_name": project.name})
        pf = plans_feed(project)
        for bundle in pf.get("bundles", []):
            plan = bundle.get("plan")
            if plan is None:
                continue  # plan-less bundle: no plan card
            plan_cards[plan["status_bucket"]].append(
                {**plan, "bundle": bundle["id"],
                 "bundle_kind": bundle["kind"],
                 "feature": bundle.get("feature"),
                 "project": project.slug,
                 "project_name": project.name})
        mf = mockups_feed(project, archived=False)
        if mf["degraded"]:
            errors.append({"slug": project.slug,
                           "reason": mf["reason"]})
        for item in mf.get("triage", []):
            review_queue.append(
                {**item, "project": project.slug,
                 "project_name": project.name})
    return {"todos": lanes, "plans": plan_cards,
            "review_queue": review_queue, "errors": errors,
            "sweep_errors": result.errors}


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


def messages_list(query: dict) -> dict:
    if query.get("pickup") == "1":
        # Agent pickup (spec D3): the fetch acknowledges.
        picked = msg_mod.fetch_unacked(
            MSG_DB, query.get("project") or None)
        return {"messages": picked,
                "picked_up": len(picked),
                "captured_at": now_iso()}
    rows = msg_mod.list_messages(
        MSG_DB, project_slug=query.get("project") or None,
        state=query.get("state") or None,
        anchor_type=query.get("anchor_type") or None,
        anchor_ref=query.get("anchor_ref") or None,
        badge_days=CFG["messages_awaiting_badge_days"])
    return {"messages": rows, "captured_at": now_iso()}


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


def home_feed() -> dict:
    """GET /api/home (repo-home §4): one row per swept
    project, from lib/home derivations."""
    result = get_sweep()
    feed = home_mod.home_feed(
        result.projects,
        stale_days=CFG["worktree_stale_days"])
    feed["sweep_errors"] = result.errors
    return feed


def worktrees_feed(project) -> dict:
    """GET /api/projects/<slug>/worktrees (repo-home §6):
    the project's worktrees, derived read-only, each with
    its active-plan resolution attached (§17 — resolved in
    lib from that worktree's own .plans/)."""
    result = wt_mod.list_worktrees(
        project.root, plans_dir=project.manifest.plans,
        stale_days=CFG["worktree_stale_days"])
    if result["available"]:
        actives = active_mod.active_by_worktree(
            project.root, project.manifest.plans,
            result["worktrees"])
        by_path = {a["path"]: a["active"] for a in actives}
        for w in result["worktrees"]:
            w["active"] = by_path.get(w["path"])
    return {"slug": project.slug, "name": project.name,
            "captured_at": now_iso(), **result}


def diff_feed(project, query: dict) -> dict:
    """GET /api/projects/<slug>/diff (repo-home §18.5,
    B2): the anchored diff, structured by lib/diffs — this
    layer only translates query params. `?peek=<path>`
    answers the §18.4 peek for one untracked/ignored file
    in the anchored worktree instead. Unanchored or
    unknown requests are honest 4xx (DiffError carries
    the status)."""
    plans_dir = project.manifest.plans
    try:
        if query.get("peek"):
            peek = diff_mod.peek_file(
                project.root,
                worktree=query.get("worktree") or None,
                path=query["peek"])
            return {"slug": project.slug,
                    "name": project.name,
                    "captured_at": now_iso(), "peek": peek}
        result = diff_mod.get_diff(
            project.root,
            worktree=query.get("worktree") or None,
            mode=query.get("mode") or "working",
            base=query.get("base") or None,
            target=query.get("target") or None,
            bundle=query.get("bundle") or None,
            plans_dir=plans_dir,
            all_files=query.get("all") == "1")
    except diff_mod.DiffError as e:
        raise ApiError(e.status, e.message)
    return {"slug": project.slug, "name": project.name,
            "captured_at": now_iso(), **result}


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


# ================================================================
# REPO-HOME ADDITIONS — END
# ================================================================


# ----------------------------------------------------------------
# Mutations (delegate to lib/, actor=viewer, then regenerate)
# ----------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message, **extra}


def _require_registry(project):
    m = project.manifest
    if m.registry is None or not m.registry.is_file():
        raise ApiError(409, "project has no initialized "
                            "registry")
    return m.registry


def _after_mutation(project, entry_id):
    db = project.manifest.registry
    try:
        export_mod.regenerate(db, project=project.slug)
    except Exception as e:
        raise ApiError(500, f"mutation landed but export "
                            f"regeneration failed: {e}",
                       mutated=True)
    return entry_detail(db, entry_id)


def entry_action(project, entry_id, body: dict) -> dict:
    db = _require_registry(project)
    verb = body.get("verb")
    layout = layout_of(project)
    try:
        if verb == "set":
            reg.set_fields(db, entry_id, body.get("fields") or {},
                           actor="viewer",
                           expect_version=body.get(
                               "expect_version"))
        elif verb == "set-status":
            reg.set_status(db, entry_id, body.get("status"),
                           actor="viewer",
                           ruling=body.get("ruling"),
                           gate=body.get("gate"),
                           expect_version=body.get(
                               "expect_version"),
                           layout=layout)
        elif verb == "verify":
            reg.verify_entry(db, entry_id, actor="viewer",
                             accept_drift=bool(
                                 body.get("accept_drift")))
        elif verb == "archive":
            reg.archive_entry(db, layout, entry_id,
                              actor="viewer",
                              resume=bool(body.get("resume")))
        elif verb == "unarchive":
            reg.unarchive_entry(db, layout, entry_id,
                                actor="viewer")
        elif verb == "supersede":
            if not body.get("new_id"):
                raise ApiError(400, "supersede needs new_id")
            reg.supersede(db, entry_id, body["new_id"],
                          actor="viewer",
                          ruling=body.get("ruling"))
        elif verb == "review":
            reg.review_entry(db, entry_id,
                             body.get("disposition"),
                             actor="viewer",
                             comment=body.get("comment"),
                             layout=layout)
        elif verb == "set-state":
            reg.set_state(db, entry_id, body.get("state") or {},
                          actor="viewer",
                          expect_version=body.get(
                              "expect_version"))
        elif verb == "set-state-schema":
            reg.set_state_schema(db, entry_id,
                                 body.get("schema"),
                                 actor="viewer")
        else:
            raise ApiError(400, f"unknown verb: {verb!r}")
    except ApiError:
        raise
    except reg.VersionConflict as e:
        raise ApiError(409, str(e))
    except reg.UniformityRefused as e:
        raise ApiError(422, str(e),
                       findings=getattr(e, "findings", []))
    except reg.RulingRequired as e:
        raise ApiError(400, str(e))
    except reg.RegistryError as e:
        raise ApiError(400, str(e))
    return _after_mutation(project, entry_id)


def todo_action(project, body: dict) -> dict:
    """The server's one todo mutation: a status move on a
    bundle todo FILE, through the same lib writer `wb todo
    set` calls (lib.bundles.set_todo_status — one mutation
    path; the server holds no file-writing logic of its
    own). The retired registry-DB todo verbs are gone:
    file todos are the store (§3.7)."""
    m = project.manifest
    if m.plans is None or not m.plans.is_dir():
        raise ApiError(409, "project declares no plans dir "
                            "— it has no bundle todos")
    verb = body.get("verb")
    if verb != "set-status":
        raise ApiError(400, f"unknown verb: {verb!r}")
    if not body.get("id"):
        raise ApiError(400, "set-status needs a todo id")
    try:
        todo = bundle_mod.set_todo_status(
            m.plans, body["id"], body.get("status"),
            note=body.get("note"))
    except bundle_mod.BundleError as e:
        raise ApiError(400, str(e))
    return {"todo": todo}


# ----------------------------------------------------------------
# HTTP layer
# ----------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = f"WorkbenchViewer/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep stderr for errors
        if args and str(args[0]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    # -- plumbing ------------------------------------------------
    def _send(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False,
                         indent=1).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",
                         "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ApiError(413, "body too large")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ApiError(400, "body must be JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "body must be a JSON object")
        return data

    def _project_or_404(self, slug):
        project = find_project(slug)
        if project is None:
            raise ApiError(404, f"no such project: {slug}")
        return project

    # -- routing -------------------------------------------------
    def do_GET(self):
        try:
            self._route_get()
        except ApiError as e:
            self._send(e.status, e.payload)
        except Exception as e:  # last-resort containment
            self._send(500, {"error": f"internal: {e}"[:300]})

    def do_POST(self):
        try:
            self._route_post()
        except ApiError as e:
            self._send(e.status, e.payload)
        except files_mod.FileError_ as e:
            self._send(e.status, dict(e.payload))
        except Exception as e:
            self._send(500, {"error": f"internal: {e}"[:300]})

    def _parts(self):
        split = urlsplit(self.path)
        parts = [unquote(p) for p in split.path.split("/")
                 if p != ""]
        query = {k: v[0] for k, v in
                 parse_qs(split.query).items()}
        return parts, query

    def _route_get(self):
        parts, query = self._parts()
        if parts == ["health"]:
            result = get_sweep()
            uptime = (datetime.now(timezone.utc)
                      - STARTED_AT).total_seconds()
            return self._send(200, {
                "ok": True, "version": VERSION,
                "commit": COMMIT,
                "started_at": STARTED_AT.isoformat(),
                "uptime_s": round(uptime, 1),
                "host": CFG["host"], "port": CFG["port"],
                "projects_count": len(result.projects),
                "config_hash": cfgmod.config_hash(CFG),
                "sweep": {"projects": len(result.projects),
                          "errors": len(result.errors)},
            })
        if parts == ["config"]:
            return self._send(200, {
                "config": CFG,
                "config_hash": cfgmod.config_hash(CFG),
                "config_file": str(cfgmod.config_path()),
            })
        # -- repo-home additions (additive /api namespace) --
        if parts == ["api", "home"]:
            return self._send(200, home_feed())
        if len(parts) == 4 and parts[0] == "api" \
                and parts[1] == "projects" \
                and parts[3] == "worktrees":
            project = self._project_or_404(parts[2])
            return self._send(200, worktrees_feed(project))
        if len(parts) == 4 and parts[0] == "api" \
                and parts[1] == "projects" \
                and parts[3] == "diff":
            project = self._project_or_404(parts[2])
            return self._send(200, diff_feed(project, query))
        if parts == ["api", "messages"]:
            try:
                return self._send(200, messages_list(query))
            except msg_mod.MessageError as e:
                raise ApiError(400, str(e))
        if parts == ["api", "outbox"]:
            return self._send(200, outbox_feed(query))
        if parts == ["api", "settings", "effective"]:
            return self._send(200, effective_settings())
        if parts == ["projects"]:
            result = get_sweep()
            return self._send(200, result.summary())
        if parts == ["board"]:
            return self._send(200, board_feed())
        if parts == ["todos"]:
            items, errors = [], []
            for project in get_sweep().projects:
                feed = todos_feed(project)
                if feed["degraded"]:
                    errors.append({"slug": project.slug,
                                   "reason": feed["reason"]})
                for err in feed.get("errors", []):
                    errors.append({"slug": project.slug,
                                   **err})
                for todo in feed["todos"]:
                    items.append({**todo,
                                  "project": project.slug,
                                  "project_name": project.name})
            return self._send(200, {"todos": items,
                                    "errors": errors})
        if len(parts) >= 2 and parts[0] == "projects":
            project = self._project_or_404(parts[1])
            if len(parts) == 3 and parts[2] == "mockups":
                archived = query.get("archived") == "1"
                return self._send(
                    200, mockups_feed(project,
                                      archived=archived))
            if len(parts) == 3 and parts[2] == "plans":
                return self._send(200, plans_feed(project))
            if len(parts) == 3 and parts[2] == "plan":
                rel = query.get("path")
                if not rel:
                    raise ApiError(400, "plan needs ?path=")
                if project.manifest.plans is None:
                    raise ApiError(409, "project declares no "
                                        "plans dir")
                try:
                    doc = plan_parser.load_plan(
                        project.manifest.plans, rel)
                except (ValueError, FileNotFoundError) as e:
                    raise ApiError(404, str(e))
                return self._send(200, doc)
            if len(parts) == 3 and parts[2] == "todos":
                return self._send(200, todos_feed(project))
            if len(parts) == 4 and parts[2] == "entries":
                db = _require_registry(project)
                try:
                    detail = entry_detail(db, parts[3])
                except reg.RegistryError as e:
                    raise ApiError(404, str(e))
                return self._send(200, detail)
            if len(parts) == 5 and parts[2] == "entries" \
                    and parts[4] == "file":
                db = _require_registry(project)
                try:
                    entry = reg.get_entry(db, parts[3])
                except reg.RegistryError as e:
                    raise ApiError(404, str(e))
                rel = query.get("path")
                if not rel:
                    raise ApiError(400, "file needs ?path=")
                try:
                    peek = files_mod.peek_file(
                        entry, rel,
                        editing_enabled=CFG[
                            "file_editing_enabled"])
                except files_mod.FileError_ as e:
                    raise ApiError(e.status, str(e))
                return self._send(200, peek)
        raise ApiError(404, f"no route: {'/' + '/'.join(parts)}")

    def _route_post(self):
        parts, _query = self._parts()
        # -- repo-home additions (additive /api namespace) --
        if parts == ["api", "messages"]:
            return self._send(200,
                              message_create(self._body()))
        if parts == ["api", "messages", "cleanup"]:
            return self._send(200,
                              message_cleanup(self._body()))
        if len(parts) == 4 and parts[0] == "api" \
                and parts[1] == "messages" \
                and parts[3] in ("done", "send", "archive",
                                 "body"):
            try:
                message_id = int(parts[2])
            except ValueError:
                raise ApiError(404, "no such message: "
                                    f"{parts[2]}")
            if parts[3] == "body":
                return self._send(200, message_update_body(
                    message_id, self._body()))
            verb = {"done": message_done, "send": message_send,
                    "archive": message_archive}[parts[3]]
            return self._send(200, verb(message_id))
        if parts == ["projects", "rescan"]:
            result = get_sweep(force=True)
            return self._send(200, result.summary())
        if len(parts) == 3 and parts[0] == "projects" \
                and parts[2] == "todos":
            project = self._project_or_404(parts[1])
            return self._send(200,
                              todo_action(project, self._body()))
        if len(parts) == 5 and parts[0] == "projects" \
                and parts[2] == "entries" \
                and parts[4] == "action":
            project = self._project_or_404(parts[1])
            return self._send(
                200, entry_action(project, parts[3],
                                  self._body()))
        if len(parts) == 5 and parts[0] == "projects" \
                and parts[2] == "entries" \
                and parts[4] == "file":
            project = self._project_or_404(parts[1])
            db = _require_registry(project)
            body = self._body()
            try:
                entry = reg.get_entry(db, parts[3])
            except reg.RegistryError as e:
                raise ApiError(404, str(e))
            backup_root = cfgmod.state_dir(CFG) \
                / CFG["edit_backups_dir"]
            result = files_mod.save_file(
                db, entry, body.get("path"),
                body.get("content"), body.get("base_sha256"),
                editing_enabled=CFG["file_editing_enabled"],
                backup_root=backup_root, actor="viewer")
            try:
                export_mod.regenerate(db,
                                      project=project.slug)
            except Exception as e:
                raise ApiError(500, f"save landed but export "
                                    f"regeneration failed: {e}",
                               mutated=True)
            return self._send(200, result)
        raise ApiError(404, f"no route: {'/' + '/'.join(parts)}")


# ----------------------------------------------------------------
# Startup
# ----------------------------------------------------------------

def acquire_lock():
    global _lock_fd
    state = cfgmod.state_dir(CFG)
    state.mkdir(parents=True, exist_ok=True)
    lock_path = state / CFG["lock_file"]
    fd = open(lock_path, "a+")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"workbench-viewer: another instance holds "
              f"{lock_path}", file=sys.stderr)
        raise SystemExit(2)
    fd.seek(0)
    fd.truncate()
    fd.write(json.dumps({
        "pid": os.getpid(),
        "port": CFG["port"],
        "started_at": STARTED_AT.isoformat(),
        "version": VERSION,
    }) + "\n")
    fd.flush()
    _lock_fd = fd  # held for the process's life


def main() -> int:
    acquire_lock()
    get_sweep()  # warm the cache; sweep errors never block
    start_message_maintenance()  # repo-home §5.3 cleanup
    server = ThreadingHTTPServer((CFG["host"], CFG["port"]),
                                 Handler)
    print(f"workbench-viewer server v{VERSION} on "
          f"{CFG['host']}:{CFG['port']} "
          f"(workspace {CFG['workspace_root']})",
          file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
