"""Server-shared state and helpers.

The seam every server module stands on: the loaded
config, the process identity (version, start time,
commit), the sweep cache with its project/layout/
degraded helpers, and ApiError — the one refusal type
the HTTP layer renders. Siblings import from here;
nothing here imports a sibling (no cycles).
"""

import subprocess
import time
from datetime import datetime, timezone

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))  # for lib/
sys.path.insert(0, str(HERE))        # for config (flat, donor-style)

import config as cfgmod  # noqa: E402
from lib import sweep as sweep_mod  # noqa: E402

VERSION = "1.0.0"
MAX_BODY = 1024 * 1024

CFG = cfgmod.load()
STARTED_AT = datetime.now(timezone.utc)

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


class ApiError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message, **extra}
