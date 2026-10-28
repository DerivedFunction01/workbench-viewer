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
import subprocess
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


def _write_atomically(target: Path, new_raw: bytes) -> None:
    """Replace target with new_raw, mode preserved, via a
    temp file in the same directory (the guarded save's
    write mechanics)."""
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


def _check_content(content, base_sha256) -> bytes:
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
    return new_raw


def _check_target(root: Path, rel_raw, base_sha256: str,
                  new_raw: bytes) -> tuple:
    """The guarded save's target discipline, shared by the
    entry save and the confined-file save: confinement,
    secret refusal (before existence), symlink refusal,
    binary/oversize refusal, and the sha compare-and-swap
    (stale → 409, nothing written). Returns (target, rel,
    sha_before)."""
    rel = Path(rel_raw or "")
    if rel.is_absolute() or not str(rel):
        raise FileError_(400, "path must be root-relative")
    if is_secret(rel):
        raise FileError_(
            403, "secret-shaped paths are never editable here")
    probe = root
    for part in rel.parts:
        probe = probe / part
        if os.path.islink(probe):
            raise FileError_(403, "symlinks are not editable")
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        raise FileError_(400, "path escapes the root")
    if not target.is_file():
        raise FileError_(404, "no such file")
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
    return target, target.relative_to(root), sha_before


def guarded_save_file(root, rel_raw: str, content,
                      base_sha256, *, editing_enabled: bool,
                      backup_root: Path,
                      backup_key: str) -> dict:
    """The guarded save for a confined text file that is
    not a registry entry (plan files are the caller): the
    entry save's exact discipline — editing flag, secret /
    symlink / binary refusals, edit caps, sha
    compare-and-swap, one-generation backup, atomic
    replace — minus the registry history append (there is
    no entry to land it on; the file is the record)."""
    if not editing_enabled:
        raise FileError_(
            403, "file editing is disabled (server config "
                 "file_editing_enabled)")
    new_raw = _check_content(content, base_sha256)
    root = Path(root).resolve()
    target, rel, _sha_before = _check_target(
        root, rel_raw, base_sha256, new_raw)
    backup = Path(backup_root) / backup_key \
        / (rel.as_posix() + ".bak")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, backup)
    _write_atomically(target, new_raw)
    return {"path": rel.as_posix(),
            "sha256": sha256_bytes(new_raw),
            "size_bytes": len(new_raw),
            "backup": str(backup)}


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
    _write_atomically(target, new_raw)
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


# ----------------------------------------------------------------
# Repo scope (absorption plan, Steps 4 + 6)
#
# The same peek/save discipline generalized from an entry's
# directory to any browsed repo root — the git repo viewer's
# semantics, re-derived in house idioms (FileError_ results,
# the module's one secret policy and caps, the atomic-write
# helper). Two deliberate differences from the entry scope,
# both inherited from the reference behavior this replaces:
# the escape check runs BEFORE the secret refusal (a path
# that escapes is refused as an escape, whatever its name),
# and a secret-shaped file, once explicitly revealed, is
# editable — its save then requires confirm_secret, where
# the entry scope refuses secret saves outright.
# ----------------------------------------------------------------

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def resolve_in_repo(root, rel_raw: str):
    """Resolve a path inside a browsed repo root, refusing
    escapes. Returns (target, rel) or raises FileError_."""
    root = Path(root).resolve()
    rel = Path(rel_raw or "")
    if not rel_raw or rel.is_absolute():
        raise FileError_(400, "path must be repo-relative")
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        raise FileError_(400, "path escapes the repo root")
    return target, target.relative_to(root)


def _repo_diff(root: Path, rel: Path):
    """The file's diff against HEAD (working state), or
    None — an unchanged file, an untracked file, a repo
    with no commits yet, and a git failure all read as no
    diff; a state, never an error. Read-only by
    construction (GIT_OPTIONAL_LOCKS=0, --no-ext-diff),
    capped at the peek byte cap. (A local git call rather
    than lib/diffs: that module imports this one.)"""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--no-ext-diff",
             "HEAD", "--", rel.as_posix()],
            capture_output=True, timeout=10, env=_GIT_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    diff = out.stdout.decode("utf-8", errors="replace")
    if not diff:
        return None
    return diff[:PEEK_MAX_BYTES]


def _dataset_descriptor(root, rel: Path):
    """The peek's dataset descriptor for a dataset-like
    file (datasets plan, step 3): {"kind"} plus the table
    names for the database kinds, whose peek is a picker.
    None when the file is not dataset-like, is
    secret-shaped (a secret-shaped dataset is never
    tabled), DuckDB is unavailable (the dataset view
    degrades to text/metadata), or the schema read fails.
    Single-relation kinds never open the file here —
    classification is by suffix alone."""
    if is_secret(rel):
        return None
    from . import datasets as datasets_mod
    kind = datasets_mod.classify(rel)
    if kind is None or not datasets_mod.available():
        return None
    descriptor = {"kind": kind}
    if kind in ("sqlite", "duckdb"):
        try:
            schema = datasets_mod.dataset_schema(
                root, rel.as_posix())
        except datasets_mod.DatasetError:
            return None
        descriptor["tables"] = [t["name"]
                                for t in schema["tables"]]
    return descriptor


def repo_peek(root, rel_raw: str, *, reveal: bool = False,
              editing_enabled: bool = False) -> dict:
    """Peek one file in a browsed repo: content under the
    peek caps, binary as metadata only, secret-shaped
    withheld by default (before existence, so the answer
    is the same either way) and returned flagged when
    revealed, the file's sha256, its editability verdict,
    and its diff against HEAD."""
    target, rel = resolve_in_repo(root, rel_raw)
    secret = is_secret(rel)
    if secret and not reveal:
        size = target.stat().st_size if target.is_file() else 0
        return {"path": rel.as_posix(), "size_bytes": size,
                "is_binary": False, "withheld": "secret",
                "content": None, "diff": None, "sha256": None,
                "editable": False,
                "editable_reason": "withheld"}
    if not target.is_file():
        raise FileError_(404, "no such file in the repo")
    raw = target.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if _is_binary(target, raw[:8192]):
        out = {"path": rel.as_posix(),
               "size_bytes": len(raw), "is_binary": True,
               "withheld": None, "content": None, "diff": None,
               "sha256": sha, "editable": False,
               "editable_reason": "binary",
               "dataset": _dataset_descriptor(root, rel)}
        if secret:
            out["revealed"] = True
        return out
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = len(raw) > PEEK_MAX_BYTES \
        or len(lines) > PEEK_MAX_LINES
    if not truncated:
        # Whole file within caps: serve the raw text so an
        # edit round-trips byte-faithfully (line endings,
        # trailing newline) instead of a line-joined copy.
        content = text
    else:
        content = "\n".join(lines[:PEEK_MAX_LINES])
        if len(content.encode()) > PEEK_MAX_BYTES:
            content = content.encode()[:PEEK_MAX_BYTES] \
                .decode("utf-8", errors="ignore")
    if not editing_enabled:
        editable, reason = False, "editing disabled"
    elif truncated:
        editable, reason = False, "too large"
    else:
        editable, reason = True, None
    out = {"path": rel.as_posix(), "size_bytes": len(raw),
           "is_binary": False, "withheld": None,
           "line_count": len(lines), "truncated": truncated,
           "content": content,
           "diff": _repo_diff(Path(root), rel),
           "sha256": sha, "editable": editable,
           "editable_reason": reason,
           "dataset": _dataset_descriptor(root, rel),
           "captured_at": now_iso()}
    if secret:
        out["revealed"] = True
    return out


def repo_save(root, rel_raw: str, content, base_sha256, *,
              editing_enabled: bool,
              confirm_secret: bool = False,
              backup_dir, audit_log) -> dict:
    """The guarded save for a file in a browsed repo — the
    reference gate set, in order: editing flag; content
    validity and caps; resolved containment in the repo
    root; secret-shaped refused before existence unless
    confirm_secret (every other gate still applies with
    it); symlink components refused on the raw path;
    existence; binary and over-cap refused; sha
    compare-and-swap (stale → 409, nothing written).
    Success: one-generation backup under backup_dir,
    atomic replace with mode preserved, one audit line
    appended to audit_log."""
    if not editing_enabled:
        raise FileError_(
            403, "file editing is disabled (server config "
                 "file_editing_enabled)")
    new_raw = _check_content(content, base_sha256)
    root = Path(root)
    target, rel = resolve_in_repo(root, rel_raw)
    if is_secret(rel) and not confirm_secret:
        raise FileError_(
            403, "secret-shaped path requires confirm_secret")
    probe = root
    for part in Path(rel_raw).parts:
        probe = probe / part
        if os.path.islink(probe):
            raise FileError_(403, "symlinks are not editable")
    if not target.is_file():
        raise FileError_(404, "no such file in the repo")
    raw = target.read_bytes()
    if _is_binary(target, raw[:8192]):
        raise FileError_(403, "binary files are not editable")
    if len(raw) > PEEK_MAX_BYTES \
            or len(raw.decode("utf-8", errors="replace")
                      .splitlines()) > PEEK_MAX_LINES:
        raise FileError_(403, "file is too large to edit")
    sha_before = hashlib.sha256(raw).hexdigest()
    if base_sha256 != sha_before:
        raise FileError_(
            409, "file changed on disk since it was opened",
            current_sha256=sha_before)
    backup = Path(backup_dir) / (rel.as_posix() + ".bak")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, backup)
    _write_atomically(target, new_raw)
    sha_after = sha256_bytes(new_raw)
    audit_log = Path(audit_log)
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": now_iso(), "path": rel.as_posix(),
              "bytes_before": len(raw),
              "bytes_after": len(new_raw),
              "sha_before": sha_before, "sha_after": sha_after}
    with open(audit_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"path": rel.as_posix(), "sha256": sha_after,
            "size_bytes": len(new_raw),
            "backup": str(backup)}
