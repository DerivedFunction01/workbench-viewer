"""Entry file peek + the guarded save — the server's one
filesystem write path, with the git viewer's v2.1 mechanics
(subplan 09): editing behind a config flag (default OFF),
secret-shaped paths refused before existence is checked,
binary/oversized refused, symlinks refused (tested on the
raw path components, not the resolved path), sha-checked
saves (stale → conflict, nothing written), atomic replace
with mode preserved, one-generation backup, and every save
audit-landed in the entry's history (actor=viewer).

Paths are confined to the entry's own directory: the viewer
edits a mockup's files and its config, nothing else in the
project tree.
"""

import fnmatch
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

from . import registry as reg
from .util import now_iso, sha256_bytes

SECRET_PATTERNS = [".env*", "*secret*", "*credential*", "*.pem",
                   "*.key", "id_rsa*", "id_ed25519*", "*.keystore",
                   "*.p12", "*.pfx"]
SECRET_PARTS = {".git", ".ssh", ".aws", ".gnupg", ".venv",
                "node_modules", "__pycache__"}
BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
               ".bmp", ".tif", ".tiff", ".pdf", ".zip", ".gz",
               ".tgz", ".bz2", ".xz", ".7z", ".parquet", ".db",
               ".sqlite", ".sqlite3", ".pyc", ".so", ".dylib",
               ".dll", ".exe", ".bin", ".woff", ".woff2", ".ttf",
               ".otf", ".mp3", ".mp4", ".mov", ".wasm"}
PEEK_MAX_BYTES = 200 * 1024
PEEK_MAX_LINES = 2000


class FileError_(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message, **extra}


def is_secret(rel: Path) -> bool:
    if any(part in SECRET_PARTS for part in rel.parts):
        return True
    name = rel.name.lower()
    return any(fnmatch.fnmatch(name, p.lower())
               for p in SECRET_PATTERNS)


def _is_binary(target: Path, raw_head: bytes) -> bool:
    if target.suffix.lower() in BINARY_EXTS:
        return True
    return b"\x00" in raw_head


def resolve_in_entry(entry: dict, rel_raw: str):
    """Resolve a path inside the entry dir, refusing escapes.
    Returns (target, rel) or raises FileError_."""
    if entry.get("source_kind") != "entry-dir" \
            or not entry.get("entry_dir"):
        raise FileError_(
            400, "entry has no local files (source is "
                 f"{entry.get('source_kind')})")
    rel = Path(rel_raw or "")
    if rel.is_absolute() or not str(rel):
        raise FileError_(400, "path must be entry-relative")
    root = Path(entry["entry_dir"]).resolve()
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        raise FileError_(400, "path escapes the entry dir")
    return target, target.relative_to(root)


def list_entry_files(entry: dict) -> list:
    if entry.get("source_kind") != "entry-dir" \
            or not entry.get("entry_dir"):
        return []
    root = Path(entry["entry_dir"])
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append({
                "path": p.relative_to(root).as_posix(),
                "size_bytes": p.stat().st_size,
                "is_main": p.relative_to(root).as_posix()
                == entry.get("main_file"),
            })
    return out


def peek_file(entry: dict, rel_raw: str, *,
              editing_enabled: bool = False) -> dict:
    target, rel = resolve_in_entry(entry, rel_raw)
    if is_secret(rel):
        # Before existence: the same answer either way.
        size = target.stat().st_size if target.is_file() else 0
        return {"path": rel.as_posix(), "size_bytes": size,
                "is_binary": False, "withheld": "secret",
                "content": None, "sha256": None,
                "editable": False,
                "editable_reason": "withheld"}
    if not target.is_file():
        raise FileError_(404, "no such file in the entry")
    raw = target.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    binary = _is_binary(target, raw[:8192])
    if binary:
        return {"path": rel.as_posix(),
                "size_bytes": len(raw), "is_binary": True,
                "withheld": None, "content": None,
                "sha256": sha, "editable": False,
                "editable_reason": "binary"}
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = len(raw) > PEEK_MAX_BYTES \
        or len(lines) > PEEK_MAX_LINES
    content = text if not truncated else "\n".join(
        lines[:PEEK_MAX_LINES])
    if not editing_enabled:
        editable, reason = False, "editing disabled"
    elif truncated:
        editable, reason = False, "too large"
    else:
        editable, reason = True, None
    return {"path": rel.as_posix(), "size_bytes": len(raw),
            "is_binary": False, "withheld": None,
            "line_count": len(lines), "truncated": truncated,
            "content": content, "sha256": sha,
            "editable": editable, "editable_reason": reason,
            "captured_at": now_iso()}


def save_file(db_path, entry: dict, rel_raw: str, content,
              base_sha256, *, editing_enabled: bool,
              backup_root: Path, actor: str = "viewer") -> dict:
    """The guarded save. Returns the success payload or
    raises FileError_ with the HTTP status the server should
    answer."""
    if not editing_enabled:
        raise FileError_(
            403, "file editing is disabled (server config "
                 "file_editing_enabled)")
    if not isinstance(content, str) \
            or not isinstance(base_sha256, str):
        raise FileError_(
            400, "need {path, content, base_sha256}")
    if "\x00" in content:
        raise FileError_(400, "content must be text (no NULs)")
    new_raw = content.encode("utf-8")
    if len(new_raw) > PEEK_MAX_BYTES \
            or len(content.splitlines()) > PEEK_MAX_LINES:
        raise FileError_(413, "content exceeds the edit caps")
    target, rel = resolve_in_entry(entry, rel_raw)
    if is_secret(rel):
        raise FileError_(
            403, "secret-shaped paths are never editable here")
    root = Path(entry["entry_dir"])
    probe = root
    for part in Path(rel_raw).parts:
        probe = probe / part
        if os.path.islink(probe):
            raise FileError_(403, "symlinks are not editable")
    if not target.is_file():
        raise FileError_(404, "no such file in the entry")
    raw = target.read_bytes()
    if _is_binary(target, raw[:8192]):
        raise FileError_(403, "binary files are not editable")
    if len(raw) > PEEK_MAX_BYTES:
        raise FileError_(403, "file is too large to edit")
    sha_before = hashlib.sha256(raw).hexdigest()
    if base_sha256 != sha_before:
        raise FileError_(
            409, "file changed on disk since it was opened",
            current_sha256=sha_before)
    backup = Path(backup_root) / entry["id"] \
        / (rel.as_posix() + ".bak")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, backup)
    mode = stat.S_IMODE(target.stat().st_mode)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent),
                               prefix=target.name + ".",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_raw)
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    sha_after = sha256_bytes(new_raw)
    conn = reg.connect(db_path)
    try:
        with reg._tx(conn):
            reg._append_history(
                conn, entry["id"], actor, "file-save",
                field=rel.as_posix(), old=sha_before,
                new=sha_after,
                note=json.dumps({"backup": str(backup)}))
    finally:
        conn.close()
    return {"path": rel.as_posix(), "sha256": sha_after,
            "size_bytes": len(new_raw),
            "backup": str(backup)}
