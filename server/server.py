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
from lib import export as export_mod  # noqa: E402
from lib import files as files_mod  # noqa: E402
from lib import registry as reg  # noqa: E402
from lib import staleness  # noqa: E402
from lib import sweep as sweep_mod  # noqa: E402
from lib import validators as val_mod  # noqa: E402
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
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False}
    if m.registry is None or not m.registry.is_file():
        return {**base, "available": False, "todos": []}
    try:
        return {**base, "available": True,
                "todos": reg.list_todos(m.registry)}
    except Exception as e:
        return degraded({**base, "available": True,
                         "todos": []}, e)


def plans_feed(project) -> dict:
    m = project.manifest
    base = {"slug": project.slug, "name": project.name,
            "degraded": False}
    if m.plans is None or not m.plans.is_dir():
        return {**base, "available": False, "plans": []}
    try:
        return {**base, "available": True,
                "plans": plan_parser.list_plans(m.plans)}
    except Exception as e:
        return degraded({**base, "available": True,
                         "plans": []}, e)


def board_feed() -> dict:
    result = get_sweep()
    lanes = {"todo": [], "doing": [], "done": []}
    plan_cards = {"todo": [], "doing": [], "done": []}
    review_queue = []
    errors = []
    for project in result.projects:
        tf = todos_feed(project)
        if tf["degraded"]:
            errors.append({"slug": project.slug,
                           "reason": tf["reason"]})
        for todo in tf["todos"]:
            lanes[todo["status"]].append(
                {**todo, "project": project.slug,
                 "project_name": project.name})
        pf = plans_feed(project)
        for plan in pf["plans"]:
            plan_cards[plan["status_bucket"]].append(
                {**plan, "project": project.slug,
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
    db = _require_registry(project)
    verb = body.get("verb")
    try:
        if verb == "add":
            todo = reg.add_todo(
                db, body.get("id"), body.get("title"),
                actor="viewer", notes=body.get("notes"),
                link_kind=body.get("link_kind"),
                link_ref=body.get("link_ref"))
        elif verb == "set-status":
            todo = reg.set_todo_status(
                db, body.get("id"), body.get("status"),
                actor="viewer",
                expect_version=body.get("expect_version"))
        elif verb == "set":
            todo = reg.set_todo_fields(
                db, body.get("id"), body.get("fields") or {},
                actor="viewer",
                expect_version=body.get("expect_version"))
        else:
            raise ApiError(400, f"unknown verb: {verb!r}")
    except ApiError:
        raise
    except reg.VersionConflict as e:
        raise ApiError(409, str(e))
    except reg.RegistryError as e:
        raise ApiError(400, str(e))
    try:
        export_mod.regenerate(db, project=project.slug)
    except Exception as e:
        raise ApiError(500, f"mutation landed but export "
                            f"regeneration failed: {e}",
                       mutated=True)
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
