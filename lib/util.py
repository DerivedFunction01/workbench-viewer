"""Shared low-level helpers for the workbench harness core.

Stdlib only. Everything here is pure or filesystem-leaf work;
no module in lib/ imports another lib module *through* this one
beyond these helpers.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (the one format
    every timestamp in the system uses)."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> str:
    """Deterministic JSON: sorted keys, no float noise. The
    dagstore manifest habit — the same fold everywhere
    (exports, state snapshots, hashes over state)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def state_sha256(state) -> str:
    """Fingerprint of an entry's internal state (approval
    binding is over exactly this)."""
    return sha256_bytes(canonical_json(state or {}).encode("utf-8"))
