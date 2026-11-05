"""Server-shared state and helpers.

The seam every server module stands on: the loaded
config, the process identity (version, start time,
commit), the sweep cache with its project/layout/
degraded helpers, and ApiError — the one refusal type
the HTTP layer renders. Siblings import from here;
nothing here imports a sibling (no cycles).
"""

import hashlib
import subprocess
import threading
import time
from datetime import datetime, timezone

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))  # for lib/
sys.path.insert(0, str(HERE))        # for config (flat, donor-style)

import config as cfgmod  # noqa: E402
from lib import fingerprint as fingerprint_mod  # noqa: E402
from lib import sweep as sweep_mod  # noqa: E402
from lib.util import fan_out  # noqa: E402

VERSION = "1.0.0"
MAX_BODY = 1024 * 1024

CFG = cfgmod.load()
STARTED_AT = datetime.now(timezone.utc)

_sweep_cache = {"at": 0.0, "result": None}
_sweep_compute_lock = threading.Lock()
_fingerprint_cache = {"map": {}}


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
    """The swept projects, TTL-cached. The compute is
    single-flighted (the feed caches' double-checked
    idiom): concurrent cold requests share one walk
    instead of each re-walking the tree."""
    ttl = CFG["sweep_ttl_s"]
    if not force and _sweep_cache["result"] is not None \
            and time.monotonic() - _sweep_cache["at"] < ttl:
        return _sweep_cache["result"]
    with _sweep_compute_lock:
        # A racing request may have filled the cache while
        # this one waited for the lock.
        if not force and _sweep_cache["result"] is not None \
                and time.monotonic() - _sweep_cache["at"] \
                < ttl:
            return _sweep_cache["result"]
        result = sweep_mod.sweep(
            cfgmod.sweep_roots(CFG),
            manifest_name=CFG["sweep_manifest"],
            max_depth=CFG["sweep_max_depth"],
            prune=CFG["sweep_prune"])
        _sweep_cache.update(at=time.monotonic(),
                            result=result)
        # Auxiliary to the sweep's real job: a result
        # without projects (never in production) simply
        # leaves every feed uncached, never breaks
        # discovery.
        _fingerprint_cache["map"] = \
            _compute_fingerprints(
                getattr(result, "projects", None) or [])
        return result


def _compute_fingerprints(projects) -> dict:
    """Per-project content fingerprints (lib/fingerprint),
    computed alongside the sweep under the same lock and
    lifecycle: the fingerprint cadence IS the sweep
    cadence, at one stat walk per project per sweep. The
    walks fan out over the feed pool — stat calls are
    syscall-bound, so the pool's threads genuinely help."""
    pairs = fan_out(
        lambda p: (p.slug,
                   fingerprint_mod.project_fingerprint(
                       p.root)),
        projects, workers=CFG["feed_pool_workers"])
    by_slug: dict = {}
    for slug, fp in pairs:
        by_slug.setdefault(slug, []).append(fp)
    # A slug borne by two swept roots (a repo and its
    # checkout) folds both walks into one value, so a
    # write to either root moves the slug's fingerprint.
    return {slug: fps[0] if len(fps) == 1 else
            hashlib.sha256(
                "\n".join(sorted(fps)).encode("utf-8"))
            .hexdigest()
            for slug, fps in by_slug.items()}


def get_fingerprints() -> dict:
    """{slug: fingerprint} for the currently swept
    projects, from the sweep-lifecycle cache above."""
    get_sweep()
    return dict(_fingerprint_cache["map"])


def combined_fingerprint() -> str:
    """One hash over every project's fingerprint (sorted
    slug:fp pairs) — the home feed's change signal: any
    project's corpus moving moves the combination."""
    fps = get_fingerprints()
    h = hashlib.sha256()
    for slug in sorted(fps):
        h.update(f"{slug}:{fps[slug]}\n".encode("utf-8"))
    return h.hexdigest()


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


class ApiError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message, **extra}
