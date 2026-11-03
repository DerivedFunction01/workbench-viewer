"""Repos feed: the cross-repo census and datasets.

One slice of the companion server: the repos feed
derivation behind its TTL cache (background refresh,
write invalidation by generation), the per-repo status
feed, and the dataset console schema/rows/stats feeds.
"""

import json
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
from lib import datasets as datasets_mod  # noqa: E402
from lib import files as files_mod  # noqa: E402
from lib import repo_state as repo_state_mod  # noqa: E402
from lib import repos as repos_mod  # noqa: E402
from lib.util import fan_out, now_iso  # noqa: E402

from common import CFG, ApiError  # noqa: E402

# ----------------------------------------------------------------
# Repos (absorption plan, steps 2-7): census, status, tree,
# peek/save, registry, history — every derivation in lib/;
# this layer only resolves ids and shapes payloads.
# ----------------------------------------------------------------

def _census() -> dict:
    """id -> census record, freshly walked (the walk is
    the cheap part; derivations run per feed)."""
    prune = CFG["repos_prune"] or repos_mod.DEFAULT_PRUNE
    records = repos_mod.discover_repos(
        CFG["workspace_root"],
        max_depth=CFG["repos_max_depth"], prune=prune)
    return {r["id"]: r for r in records}


def _repo_or_404(repo_id: str) -> dict:
    record = _census().get(repo_id)
    if record is None:
        raise ApiError(404, f"unknown repo: {repo_id}")
    return record


def _repos_registry_path():
    return cfgmod.state_file(CFG, "repos_registry_file")


def _repos_history_path():
    return cfgmod.state_file(CFG, "repos_history_file")


def _compute_repos_feed() -> dict:
    """The /api/repos derivation itself: every discovered
    repo's summary with its registry entry attached;
    registry entries that discovery did not find ride as
    missing rows. Serves record history, as the reference
    did. Expensive — a git fan-out per repo — so the
    request path goes through the cache below, never
    straight here."""
    census = _census()
    data = repo_state_mod.load_registry(_repos_registry_path())
    data, changed = repo_state_mod.reconcile(
        data, list(census.values()),
        healthy_scan=len(census) > 0, now=now_iso())
    if changed:
        repo_state_mod.save_registry(_repos_registry_path(),
                                     data)
    # The summaries are a per-repo git fan-out — computed
    # on the pool (fan_out preserves census order); the
    # registry attach and the history recording stay
    # serial, in the original iteration order.
    records = list(census.values())
    computed = fan_out(repos_mod.repo_summary, records,
                       workers=CFG["feed_pool_workers"])
    summaries = []
    for record, s in zip(records, computed):
        s["registry"] = data["repos"].get(record["id"])
        if not s.get("error"):
            repo_state_mod.record_history(
                _repos_history_path(), s)
        summaries.append(s)
    for repo_id, entry in data["repos"].items():
        if repo_id not in census:
            summaries.append({
                "id": repo_id, "name": repo_id,
                "root": entry.get("root"),
                "is_worktree": False, "parent_id": None,
                "missing": True, "error": None,
                "registry": dict(entry)})
    summaries.sort(key=lambda s: s["id"])
    return {"repos": summaries, "captured_at": now_iso()}


# ----------------------------------------------------------------
# Repos feed cache
#
# The derivation fans out git subprocesses per repo and
# costs seconds even warm (measured 7.2 s cold, 1.2 s warm
# over ~20 repos), so the request path serves the last
# computed payload: within repos_ttl_s as-is; past the TTL
# the stale payload while ONE background thread recomputes;
# and only a never-filled cache computes on the request
# path, single-flighted so a burst of cold requests shares
# one derivation. main() warms the cache in a thread at
# startup, so the first open after a restart does not pay
# the cold cost either. Writes that change what the feed
# derives (registry curation, a guarded repo save)
# invalidate the cache — a save must never look unstuck
# for a TTL — and the generation counter keeps a payload
# computed across an invalidation from being stored.
# ----------------------------------------------------------------

_repos_cache = {"at": 0.0, "result": None}
_repos_state_lock = threading.Lock()
_repos_compute_lock = threading.Lock()
_repos_refreshing = False
_repos_generation = 0


def _repos_invalidate_cache() -> None:
    global _repos_generation
    with _repos_state_lock:
        _repos_generation += 1
        _repos_cache.update(at=0.0, result=None)


def _repos_store(result, generation: int) -> None:
    with _repos_state_lock:
        if generation == _repos_generation:
            _repos_cache.update(at=time.monotonic(),
                                result=result)


def _repos_refresh_background() -> None:
    global _repos_refreshing
    try:
        with _repos_state_lock:
            generation = _repos_generation
        _repos_store(_compute_repos_feed(), generation)
    except Exception as e:
        # The stale payload keeps serving; the next stale
        # request kicks another refresh.
        print(f"workbench-viewer: repos feed refresh "
              f"failed: {e}", file=sys.stderr)
    finally:
        with _repos_state_lock:
            _repos_refreshing = False


def _repos_kick_refresh() -> None:
    global _repos_refreshing
    with _repos_state_lock:
        if _repos_refreshing:
            return
        _repos_refreshing = True
    threading.Thread(target=_repos_refresh_background,
                     daemon=True).start()


def repos_feed() -> dict:
    """GET /api/repos: the cached census payload (see the
    cache note above); captured_at is when the payload was
    computed, not when it was served."""
    cached = _repos_cache["result"]
    if cached is not None:
        if time.monotonic() - _repos_cache["at"] \
                < CFG["repos_ttl_s"]:
            return cached
        _repos_kick_refresh()
        return cached
    with _repos_compute_lock:
        # The startup warm or a racing request may have
        # filled the cache while this one waited.
        cached = _repos_cache["result"]
        if cached is not None:
            return cached
        with _repos_state_lock:
            generation = _repos_generation
        result = _compute_repos_feed()
        _repos_store(result, generation)
        return result


def repo_status_feed(record) -> dict:
    """GET /api/repos/<id>/status: the full status with
    its registry entry; the serve records history."""
    status = repos_mod.repo_status(record)
    data = repo_state_mod.load_registry(_repos_registry_path())
    status["registry"] = data["repos"].get(record["id"])
    if not status.get("error"):
        repo_state_mod.record_history(_repos_history_path(),
                                      status)
    return status


def _dataset_call(fn, *args, **kwargs):
    """One dataset derivation with the house error shape:
    lib/files refusals keep their status; dataset
    refusals are 400 with the module's renderable
    message."""
    try:
        return fn(*args, **kwargs)
    except files_mod.FileError_ as e:
        raise ApiError(e.status, str(e))
    except datasets_mod.DatasetError as e:
        raise ApiError(400, str(e))


def dataset_schema_feed(record, query) -> dict:
    """GET /api/repos/<id>/dataset?path=: the dataset's
    schema (for database kinds, every table's)."""
    rel = query.get("path")
    if not rel:
        raise ApiError(400, "dataset needs ?path=")
    return _dataset_call(datasets_mod.dataset_schema,
                         record["root"], rel)


def dataset_rows_feed(record, query) -> dict:
    """GET /api/repos/<id>/dataset/rows: one bounded
    page; filters ride as one JSON array parameter."""
    rel = query.get("path")
    if not rel:
        raise ApiError(400, "dataset rows need ?path=")
    try:
        limit = int(query.get("limit", "100"))
        offset = int(query.get("offset", "0"))
    except ValueError:
        raise ApiError(400, "limit/offset must be integers")
    filters = []
    raw_filters = query.get("filters")
    if raw_filters:
        try:
            filters = json.loads(raw_filters)
        except json.JSONDecodeError:
            raise ApiError(400, "filters must be a JSON array")
        if not isinstance(filters, list):
            raise ApiError(400, "filters must be a JSON array")
    return _dataset_call(
        datasets_mod.dataset_rows, record["root"], rel,
        table=query.get("table") or None, limit=limit,
        offset=offset, sort=query.get("sort") or None,
        descending=query.get("dir") == "desc",
        filters=filters)


def dataset_stats_feed(record, query) -> dict:
    """GET /api/repos/<id>/dataset/stats?path=: the
    on-demand column statistics."""
    rel = query.get("path")
    if not rel:
        raise ApiError(400, "dataset stats need ?path=")
    return _dataset_call(
        datasets_mod.dataset_stats, record["root"], rel,
        table=query.get("table") or None)
