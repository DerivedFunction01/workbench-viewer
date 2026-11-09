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
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, \
    ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlsplit

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))  # for lib/
sys.path.insert(0, str(HERE))        # for config (flat, donor-style)

import config as cfgmod  # noqa: E402
import feedcache  # noqa: E402
from lib import export as export_mod  # noqa: E402
from lib import files as files_mod  # noqa: E402
from lib import messages as msg_mod  # noqa: E402
from lib import registry as reg  # noqa: E402
from lib import repo_state as repo_state_mod  # noqa: E402
from lib import repos as repos_mod  # noqa: E402
from lib.datasets import console as dataset_console_mod  # noqa: E402
from lib import datasets as datasets_mod  # noqa: E402
from lib.plans import parser as plan_parser  # noqa: E402
from lib.util import now_iso  # noqa: E402

from common import (CFG, COMMIT, MAX_BODY,  # noqa: E402
                    STARTED_AT, VERSION, ApiError,
                    find_project, get_sweep)
from feeds import (_home_invalidate_cache,  # noqa: E402
                   artifacts_feed, board_project_feed,
                   classification_feed, diff_feed,
                   entry_detail, home_feed, mockups_feed,
                   plans_feed, todos_feed, worktrees_feed)
from messages_api import (effective_settings,  # noqa: E402
                          message_archive, message_cleanup,
                          message_create, message_done,
                          message_send, message_update_body,
                          messages_list, outbox_feed,
                          start_message_maintenance)
from repos_feed import (_repo_or_404,  # noqa: E402
                        _repos_history_path,
                        _repos_invalidate_cache,
                        _repos_registry_path, dataset_rows_feed,
                        dataset_schema_feed,
                        dataset_stats_feed, repo_status_feed,
                        repos_feed)
from actions import (_require_registry, entry_action,  # noqa: E402
                     plan_resolve, todo_action)

_lock_fd = None

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
        if parts == ["api", "health"]:
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
        if parts == ["api", "config"]:
            return self._send(200, {
                "config": CFG,
                "config_hash": cfgmod.config_hash(CFG),
                "config_file": str(cfgmod.config_path()),
            })
        if parts == ["api", "home"]:
            return self._send(200, home_feed())
        if parts == ["api", "repos"]:
            return self._send(200, repos_feed())
        if parts == ["api", "repos", "registry"]:
            data = repo_state_mod.load_registry(
                _repos_registry_path())
            return self._send(200, {
                "repos": data["repos"],
                "captured_at": now_iso()})
        if len(parts) >= 4 and parts[0] == "api" \
                and parts[1] == "repos" \
                and parts[-1] in ("status", "files", "file",
                                  "history"):
            record = _repo_or_404("/".join(parts[2:-1]))
            if parts[-1] == "status":
                return self._send(200,
                                  repo_status_feed(record))
            if parts[-1] == "files":
                # The dir parameter's presence is read from
                # the raw query: parse_qs drops blank
                # values, and ?dir= (the root) is a real
                # request, distinct from no dir at all.
                raw_pairs = parse_qsl(
                    urlsplit(self.path).query,
                    keep_blank_values=True)
                if any(k == "dir" for k, _v in raw_pairs):
                    try:
                        listing = repos_mod.repo_dir(
                            record, query.get("dir") or "")
                    except ValueError as e:
                        raise ApiError(400, str(e))
                    except FileNotFoundError:
                        raise ApiError(404, "no such directory")
                    return self._send(200, listing)
                include_all = query.get("all") in ("1", "true")
                return self._send(200, repos_mod.repo_files(
                    record, include_all=include_all))
            if parts[-1] == "history":
                return self._send(
                    200, repo_state_mod.history_for(
                        _repos_history_path(), record["id"]))
            rel = query.get("path")
            if not rel:
                raise ApiError(400, "file needs ?path=")
            try:
                peek = files_mod.repo_peek(
                    record["root"], rel,
                    reveal=query.get("reveal") in ("1", "true"),
                    editing_enabled=CFG[
                        "file_editing_enabled"])
            except files_mod.FileError_ as e:
                raise ApiError(e.status, str(e))
            return self._send(200, peek)
        if len(parts) >= 4 and parts[0] == "api" \
                and parts[1] == "repos" \
                and parts[-1] == "dataset":
            record = _repo_or_404("/".join(parts[2:-1]))
            return self._send(200,
                              dataset_schema_feed(record, query))
        if len(parts) >= 5 and parts[0] == "api" \
                and parts[1] == "repos" \
                and parts[-2] == "dataset" \
                and parts[-1] in ("rows", "stats"):
            record = _repo_or_404("/".join(parts[2:-2]))
            if parts[-1] == "rows":
                return self._send(
                    200, dataset_rows_feed(record, query))
            return self._send(
                200, dataset_stats_feed(record, query))
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
        if parts == ["api", "projects"]:
            result = get_sweep()
            return self._send(200, result.summary())
        if len(parts) >= 3 and parts[0] == "api" \
                and parts[1] == "projects":
            project = self._project_or_404(parts[2])
            if len(parts) == 4 and parts[3] == "mockups":
                archived = query.get("archived") == "1"
                return self._send(
                    200, mockups_feed(project,
                                      archived=archived))
            if len(parts) == 4 and parts[3] == "artifacts":
                archived = query.get("archived") == "1"
                return self._send(
                    200, artifacts_feed(project,
                                        archived=archived))
            if len(parts) == 4 and parts[3] == "plans":
                return self._send(200, plans_feed(project))
            if len(parts) == 4 and parts[3] == "plan":
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
            if len(parts) == 4 and parts[3] == "todos":
                return self._send(200, todos_feed(project))
            if len(parts) == 4 and parts[3] == "classification":
                return self._send(
                    200, classification_feed(project))
            if len(parts) == 4 and parts[3] == "board":
                return self._send(
                    200, board_project_feed(project, query))
            if len(parts) == 5 and parts[3] == "entries":
                db = _require_registry(project)
                try:
                    detail = entry_detail(db, parts[4])
                except reg.RegistryError as e:
                    raise ApiError(404, str(e))
                return self._send(200, detail)
            if len(parts) == 6 and parts[3] == "entries" \
                    and parts[5] == "file":
                db = _require_registry(project)
                try:
                    entry = reg.get_entry(db, parts[4])
                except reg.RegistryError as e:
                    raise ApiError(404, str(e))
                rel = query.get("path")
                if not rel:
                    raise ApiError(400, "file needs ?path=")
                try:
                    if query.get("preview"):
                        # The rendered-preview read: the
                        # entry's own file, whole — the
                        # peek caps guard the source
                        # surface, not a rendered study.
                        peek = files_mod.entry_preview(
                            entry, rel)
                    else:
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
        if parts == ["api", "projects", "rescan"]:
            result = get_sweep(force=True)
            return self._send(200, result.summary())
        if parts == ["api", "refresh"]:
            # The manual escape hatch (cache-refresh plan,
            # 2026-11-05): force the sweep — which also
            # recomputes the per-project fingerprints —
            # and bust every feed cache, so the next read
            # of any feed re-derives from disk.
            result = get_sweep(force=True)
            _repos_invalidate_cache()
            _home_invalidate_cache()
            feedcache.invalidate_all()
            return self._send(200, {
                "ok": True,
                "projects": len(result.projects),
                "invalidated": ["sweep", "home", "repos",
                                "feeds"]})
        if parts == ["api", "repos", "registry"]:
            body = self._body()
            repo_id = body.get("id")
            patch = body.get("patch")
            if not repo_id or not isinstance(patch, dict):
                raise ApiError(400, "need {id, patch}")
            data = repo_state_mod.load_registry(
                _repos_registry_path())
            entry, err = repo_state_mod.update_entry(
                data, repo_id, patch)
            if err:
                raise ApiError(400, err)
            repo_state_mod.save_registry(
                _repos_registry_path(), data)
            _repos_invalidate_cache()
            _home_invalidate_cache()
            return self._send(200, {"id": repo_id,
                                    "registry": entry})
        if len(parts) >= 4 and parts[0] == "api" \
                and parts[1] == "repos" \
                and parts[-1] == "file":
            record = _repo_or_404("/".join(parts[2:-1]))
            body = self._body()
            state = cfgmod.state_dir(CFG)
            result = files_mod.repo_save(
                record["root"], body.get("path"),
                body.get("content"),
                body.get("base_sha256"),
                editing_enabled=CFG["file_editing_enabled"],
                confirm_secret=body.get("confirm_secret")
                is True,
                backup_dir=state / CFG["edit_backups_dir"]
                / "repos" / record["id"],
                audit_log=state / CFG["edit_audit_log"])
            _repos_invalidate_cache()
            _home_invalidate_cache()
            return self._send(200, result)
        if len(parts) >= 5 and parts[0] == "api" \
                and parts[1] == "repos" \
                and parts[-2] == "dataset" \
                and parts[-1] == "sql":
            record = _repo_or_404("/".join(parts[2:-2]))
            body = self._body()
            if not body.get("path") or not body.get("sql"):
                raise ApiError(400, "sql needs {path, sql}")
            try:
                result = dataset_console_mod.run_dataset_sql(
                    record["root"], body["path"],
                    body["sql"],
                    table=body.get("table") or None,
                    timeout_s=CFG["datasets_sql_timeout_s"])
            except datasets_mod.DatasetError as e:
                raise ApiError(400, str(e))
            return self._send(200, result)
        if len(parts) == 4 and parts[0] == "api" \
                and parts[1] == "projects" \
                and parts[3] == "todos":
            project = self._project_or_404(parts[2])
            result = todo_action(project, self._body())
            # The server's own .plans writes invalidate
            # the keyed feed caches immediately (the
            # registry-curation precedent): the fingerprint
            # only re-derives on the sweep cadence, and the
            # client's post-drag refetch must not be served
            # the pre-move payload.
            feedcache.invalidate_all()
            return self._send(200, result)
        if len(parts) == 5 and parts[0] == "api" \
                and parts[1] == "projects" \
                and parts[3] == "plan" \
                and parts[4] == "resolve":
            project = self._project_or_404(parts[2])
            result = plan_resolve(project, self._body())
            feedcache.invalidate_all()
            return self._send(200, result)
        if len(parts) == 6 and parts[0] == "api" \
                and parts[1] == "projects" \
                and parts[3] == "entries" \
                and parts[5] == "action":
            project = self._project_or_404(parts[2])
            return self._send(
                200, entry_action(project, parts[4],
                                  self._body()))
        if len(parts) == 6 and parts[0] == "api" \
                and parts[1] == "projects" \
                and parts[3] == "entries" \
                and parts[5] == "file":
            project = self._project_or_404(parts[2])
            db = _require_registry(project)
            body = self._body()
            try:
                entry = reg.get_entry(db, parts[4])
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


def _warm_feeds() -> None:
    """Fill the TTL-cached feeds (repos census, home)
    once at startup, off the request path."""
    repos_feed()
    home_feed()


def main() -> int:
    acquire_lock()
    get_sweep()  # warm the cache; sweep errors never block
    start_message_maintenance()  # repo-home §5.3 cleanup
    # Warm the cached feeds off the request path: their
    # first derivations cost seconds and must not land on
    # the first open after a restart.
    threading.Thread(target=_warm_feeds, daemon=True).start()
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
