"""Shared low-level helpers for the workbench harness core.

Stdlib only. Everything here is pure or filesystem-leaf work;
no module in lib/ imports another lib module *through* this one
beyond these helpers.
"""

import hashlib
import json
import os
import tempfile
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


SCRATCH_DIR_MARKERS = frozenset(
    {"tmp", "temp", "scratch", "tmp-gate"})


def platform_temp_roots() -> set:
    """The platform's temp roots, resolved: the system
    temp (tempfile's answer), $TMPDIR when it names
    another, and the conventional defaults. Python caches
    its tempdir after the first call, so the answer is
    never trusted alone: the candidates derive from the
    CURRENT environment on every call. WB_TMP_ROOT is
    deliberately NOT consulted here — a per-run scratch
    dir leaked into it must not mint a fake root (the
    answer would then change with whatever last wrote
    the variable)."""
    roots = set()
    for candidate in (os.environ.get("TMPDIR"),
                      tempfile.gettempdir(),
                      "/tmp", "/var/tmp", "/usr/tmp"):
        if candidate:
            roots.add(Path(candidate).resolve())
    return roots


def temp_roots() -> set:
    """The platform temp roots plus every root the
    WB_TMP_ROOT seam lists (this box's discipline points
    TMPDIR at disk-backed scratch under the workspace
    itself, which no anchor or system-temp check can
    recognize — the seam names it). A seam entry that
    itself sits under a platform temp root is skipped:
    it is a run's own scratch dir, not a root."""
    roots = platform_temp_roots()
    for item in os.environ.get(
            "WB_TMP_ROOT", "").split(os.pathsep):
        if not item:
            continue
        path = Path(item).resolve()
        if any(path == root or root in path.parents
               for root in roots):
            continue
        roots.add(path)
    return roots


def under_temp_root(path) -> bool:
    """True when the resolved path sits under a temp
    root (see temp_roots) — scratch state (test fixtures,
    gate scratch), not the live workspace's own."""
    resolved = Path(path).resolve()
    return any(resolved == root
               or root in resolved.parents
               for root in temp_roots())


def scratch_marked(path) -> bool:
    """True when any component of the path names
    scratch: a dot-directory (hidden trees are scratch,
    snapshots, or tool state — never a live checkout's
    home), or a component carrying a scratch marker
    (an exact marker name, or one containing `tmp` /
    `scratch`). The caller passes the path RELATIVE to
    the sweep root it is judging under — components
    above that root (the machine's own directories)
    never convict a subtree."""
    for part in Path(path).parts:
        if part in (".", ".."):
            continue
        if part.startswith(".") and len(part) > 1:
            return True
        low = part.lower()
        if low in SCRATCH_DIR_MARKERS or "tmp" in low \
                or "scratch" in low:
            return True
    return False


def write_text(path, text, *, encoding="utf-8") -> None:
    """Write text to a file, atomically: stage the full
    text to a sibling temp file, then rename it over the
    target.

    Path.write_text is deliberately not used anywhere in
    lib/ or server/: this environment intermittently denies
    writes to agent-domain processes (EPERM windows, first
    observed 2026-10-26). The earlier form of this seam
    opened the target directly — truncate first, then
    write — so a flush denied inside one of those windows
    left the target at 0 bytes (a steampowernj programme
    todo was lost exactly that way, 2026-11-13: the
    truncated file parsed as an invalid todo and its id
    resolved nowhere). Rename-over was never denied in
    any probe of those windows, and a failed stage now
    leaves the target untouched. The target's existing
    mode is carried onto the staged file before the
    rename. One seam, so the write strategy can change
    in exactly one place."""
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(text)
        if target.exists():
            os.chmod(tmp, target.stat().st_mode & 0o7777)
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


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
