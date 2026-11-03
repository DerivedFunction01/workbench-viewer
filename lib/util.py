"""Shared low-level helpers for the workbench harness core.

Stdlib only. Everything here is pure or filesystem-leaf work;
no module in lib/ imports another lib module *through* this one
beyond these helpers.
"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
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


def write_text(path, text, *, encoding="utf-8") -> None:
    """Write text to a file through the builtin open().

    Path.write_text is deliberately not used anywhere in
    lib/ or server/: this environment intermittently denies
    it to agent-domain processes (EPERM windows, first
    observed 2026-10-26) while builtin open() keeps working
    in strictly more of those conditions. One seam, so the
    write strategy can change in exactly one place."""
    with open(path, "w", encoding=encoding) as f:
        f.write(text)


def fan_out(fn, items, *, workers=1) -> list:
    """Map `fn` over `items`, on a bounded thread pool when
    `workers > 1`. Results come back in input order
    regardless of completion order; `workers <= 1` (or a
    single item) is a plain sequential map. An exception
    from `fn` propagates exactly as the sequential map
    would raise it — per-item containment stays with the
    caller, whose derivations already contain per item.

    The pool exists for subprocess- and IO-bound fan-outs
    (the per-repo and per-project git derivations), where
    the wait releases the GIL; it buys nothing for
    pure-Python CPU work such as parsing, which stays
    sequential by design."""
    items = list(items)
    if workers <= 1 or len(items) <= 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


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
