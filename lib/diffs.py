"""Plan/worktree diffs (repo-home spec §18, phase B2).

One mechanism under every view: the triple (repo, base,
target, paths), resolved here from an anchor — a worktree,
a plan bundle, or a commit (§18.1). Diffs exist ONLY
anchored (decision D10): a request that cannot name its
anchor is refused. Absorption amendment (absorption plan,
2026-10-28-git-viewer-absorption): a repo anchor (repo +
path) is a first-class anchor for a single file's peek and
diff against HEAD, served by lib/files; arbitrary revision
browsing stays out of scope.

Read-only by construction, like lib/worktrees: every git
invocation runs with GIT_OPTIONAL_LOCKS=0 and --no-ext-diff,
and revisions are validated before they reach a command
line (nothing starting with "-" is ever a revision or a
path — paths ride behind "--" regardless).

Modes (§18.3) are presets of the same triple:
  working      working state vs merge-base (the default,
               §18.2 — committed-since-fork AND uncommitted)
  uncommitted  working state vs HEAD
  committed    HEAD vs merge-base
  range        base..target (two caller-picked commits)
  commit       <id>^..<id> (one commit's own change)
A bundle anchor narrows the paths to the plan's declared
`files:` lists intersected with the changed set, unless
widened back with all_files (§18.3).

Per-file entries carry `legs` (committed / staged /
unstaged) whenever the mode has a working-state leg, so
the §18.2 staged/unstaged split is a client grouping over
this data, not a second engine.

Untracked and ignored files are never in the diff (§18.4):
untracked files get their own group, each renderable as a
new-file (all-additions) diff under the peek caps and the
peek secret policy (lib/files — the one policy, reused,
not reinvented); ignored files are listed only when
recently changed (mtime newer than the worktree's HEAD
commit time), peekable the same way, and NEVER diffed —
no baseline exists. A plan-declared file that is
git-ignored earns a warning entry: it will not be
committed.

Vanished references are states, not errors: a repo
with no commits yet diffs against the empty tree
(everything renders as additions, payload marked
`base_kind: "empty-tree"` + a note); a worktree whose
directory was deleted returns a typed `gone` payload;
a bundle whose plan document no longer loads falls
back to the un-narrowed working-state diff with a
note; a declared path that exists nowhere simply
contributes nothing. Error text that can reach a
payload comes from a small label vocabulary — raw
git stderr never renders.
"""

import os
import re
import subprocess
from pathlib import Path

from . import files as files_mod
from .plans import bundles as bundle_parser
from .plans import parser as plan_parser
from .worktrees import plan_worktree_links

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

MODES = ("working", "uncommitted", "committed", "range",
         "commit")

MAX_BYTES = files_mod.PEEK_MAX_BYTES      # 200 KB, peek rules
MAX_LINES = files_mod.PEEK_MAX_LINES      # 2,000, peek rules
IGNORED_GROUP_CAP = 200

_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class DiffError(Exception):
    """A diff request that cannot be served, with the HTTP
    status the server should answer (the ApiError shape)."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# Error messages that can reach a payload come from
# this small vocabulary ONLY — raw git stderr never
# renders (a vanished reference is a state, not error
# text). The same vocabulary labels lib/worktrees.
def _label(stderr: str) -> str:
    text = (stderr or "").lower()
    if "not a git repository" in text:
        return "not a git repository"
    if "ambiguous argument 'head'" in text \
            or "unknown revision" in text \
            or "bad revision" in text \
            or "needed a single revision" in text:
        return "no commits yet"
    return "git command failed"


def _git(cwd, *args, timeout=10) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, timeout=timeout,
            env=_GIT_ENV)
    except subprocess.TimeoutExpired:
        raise DiffError(500, "git timed out")
    except OSError:
        raise DiffError(500, "git unavailable")
    if out.returncode != 0:
        raise DiffError(
            500, _label(out.stderr or out.stdout))
    return out.stdout


def _git_bytes(cwd, *args, timeout=15) -> bytes:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, timeout=timeout, env=_GIT_ENV)
    except subprocess.TimeoutExpired:
        raise DiffError(500, "git timed out")
    except OSError:
        raise DiffError(500, "git unavailable")
    if out.returncode != 0:
        reason = (out.stderr or b"").decode(
            "utf-8", errors="replace")
        raise DiffError(500, _label(reason))
    return out.stdout


def _rev(cwd, rev) -> str:
    """Validate a caller-supplied revision → full sha.
    Anything else is a 400, before git sees it as a flag."""
    if not rev or rev.startswith("-"):
        raise DiffError(400, f"invalid revision: {rev!r}")
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--verify",
             "--quiet", f"{rev}^{{commit}}"],
            capture_output=True, text=True, timeout=5,
            env=_GIT_ENV)
    except subprocess.TimeoutExpired:
        raise DiffError(500, "git timed out")
    except OSError:
        raise DiffError(500, "git unavailable")
    sha = out.stdout.strip()
    if out.returncode != 0 or not sha:
        raise DiffError(400, f"unknown revision: {rev!r}")
    return sha


def _head_sha(cwd):
    """HEAD's sha, or None when HEAD is unborn — a repo
    with no commits yet is a state, not an error."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--verify",
             "--quiet", "HEAD^{commit}"],
            capture_output=True, text=True, timeout=5,
            env=_GIT_ENV)
    except subprocess.TimeoutExpired:
        raise DiffError(500, "git timed out")
    except OSError:
        raise DiffError(500, "git unavailable")
    return out.stdout.strip() or None


def _merge_base(cwd, a, b):
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "merge-base", a, b],
            capture_output=True, text=True, timeout=5,
            env=_GIT_ENV)
    except subprocess.TimeoutExpired:
        raise DiffError(500, "git timed out")
    except OSError:
        raise DiffError(500, "git unavailable")
    sha = out.stdout.strip()
    return sha or None


def _worktree_paths(root) -> list:
    """[(path, branch)] for the repo at root, porcelain
    order (main checkout first)."""
    raw = _git(root, "worktree", "list", "--porcelain")
    entries, cur = [], None
    for line in raw.splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[9:], "branch": None}
            entries.append(cur)
        elif cur is not None and line.startswith("branch "):
            ref = line[7:]
            cur["branch"] = ref[len("refs/heads/"):] \
                if ref.startswith("refs/heads/") else ref
    return [(e["path"], e["branch"]) for e in entries]


def _main_branch(root, entries) -> str | None:
    for path, branch in entries:
        if Path(path) == Path(root):
            return branch
    return None


def _base_branch(cwd, branch, main_branch):
    """The branch a worktree forked from (the worktrees.py
    _base_ref rule, restated for refs): upstream when set,
    else origin/HEAD, else the main worktree's branch.
    None when the worktree IS the base branch."""
    try:
        upstream = _git(
            cwd, "rev-parse", "--abbrev-ref",
            "--symbolic-full-name", "@{upstream}").strip()
        if upstream:
            return upstream
    except DiffError:
        pass
    if branch is None or branch == main_branch:
        return None
    try:
        origin_head = _git(
            cwd, "symbolic-ref", "--short",
            "refs/remotes/origin/HEAD").strip()
        if origin_head:
            return origin_head
    except DiffError:
        pass
    return main_branch


# ----------------------------------------------------------------
# Plan declared files (the narrowing set, §18.3)
# ----------------------------------------------------------------

_PATH_TOKEN_RE = re.compile(
    r"[\w@+.-]+(?:/[\w@+.-]+)+(?:\.\w+)?|[\w.-]+\.\w{1,8}")


def declared_files(plan_doc) -> list:
    """The plan's declared file paths: the union of its
    steps' `files:` lists. Backtick-quoted spans win; bare
    path-shaped tokens are the fallback. Parenthetical
    notes ("(new)") and trailing punctuation never make
    it into a path."""
    out, seen = [], set()
    for step in plan_doc.get("steps", []):
        text = step.get("files") or ""
        spans = re.findall(r"`([^`]+)`", text)
        candidates = spans if spans else _PATH_TOKEN_RE.findall(
            text)
        for cand in candidates:
            path = cand.strip().strip(".,;:").strip()
            path = re.sub(r"\s*\(.*$", "", path).strip()
            if path and "/" not in path \
                    and not re.search(r"\.\w{1,8}$", path):
                continue
            if path and path not in seen:
                seen.add(path)
                out.append(path)
    return out


def _find_bundle(plans_dir, bundle_ref) -> dict:
    for bundle in bundle_parser.list_bundles(plans_dir):
        if bundle_ref in (bundle["id"], bundle["slug"]):
            return bundle
    raise DiffError(404, f"no such bundle: {bundle_ref!r}")


def _bundle_plan_doc(plans_dir, bundle) -> dict | None:
    plan = bundle.get("plan")
    if not plan:
        return None
    try:
        return plan_parser.load_plan(plans_dir, plan["path"])
    except (ValueError, FileNotFoundError, OSError,
            UnicodeDecodeError):
        return None


# ----------------------------------------------------------------
# Diff parsing
# ----------------------------------------------------------------

_HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _parse_patch(raw: bytes) -> list:
    """Unified-diff bytes → per-file entries with structured
    hunks. Filenames ride the `diff --git` header (git quotes
    exotic names; the common corpus is plain)."""
    text = raw.decode("utf-8", errors="replace")
    files, cur, hunk = [], None, None
    old_no = new_no = 0

    def flush_hunk():
        nonlocal hunk
        if cur is not None and hunk is not None:
            cur["hunks"].append(hunk)
        hunk = None

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush_hunk()
            m = re.match(r"^diff --git a/(.*) b/(.*)$", line)
            cur = {
                "path": m.group(2) if m else line[11:],
                "old_path": m.group(1) if m else None,
                "status": "modified", "binary": False,
                "hunks": [], "truncated": False,
                "_chunk_bytes": 0, "_line_count": 0,
            }
            files.append(cur)
            continue
        if cur is None:
            continue
        cur["_chunk_bytes"] += len(line.encode("utf-8")) + 1
        if line.startswith("new file mode"):
            cur["status"] = "added"
        elif line.startswith("deleted file mode"):
            cur["status"] = "deleted"
        elif line.startswith("rename from "):
            cur["status"] = "renamed"
            cur["old_path"] = line[len("rename from "):]
        elif line.startswith("rename to "):
            cur["path"] = line[len("rename to "):]
        elif line.startswith("Binary files ") \
                or line.startswith("GIT binary patch"):
            cur["binary"] = True
        elif line.startswith("@@ "):
            flush_hunk()
            m = _HUNK_RE.match(line)
            if m:
                hunk = {
                    "old_start": int(m.group(1)),
                    "old_lines": int(m.group(2) or 1),
                    "new_start": int(m.group(3)),
                    "new_lines": int(m.group(4) or 1),
                    "lines": [],
                }
                old_no = hunk["old_start"]
                new_no = hunk["new_start"]
        elif hunk is not None and line[:1] in (" ", "+", "-",
                                                "\\"):
            if cur["_line_count"] >= MAX_LINES \
                    or cur["_chunk_bytes"] > MAX_BYTES:
                cur["truncated"] = True
                continue
            cur["_line_count"] += 1
            marker = line[0]
            body = line[1:]
            if marker == " ":
                entry = {"kind": "context", "text": body,
                         "old_no": old_no, "new_no": new_no}
                old_no += 1
                new_no += 1
            elif marker == "+":
                entry = {"kind": "add", "text": body,
                         "old_no": None, "new_no": new_no}
                new_no += 1
            elif marker == "-":
                entry = {"kind": "del", "text": body,
                         "old_no": old_no, "new_no": None}
                old_no += 1
            else:  # "\ No newline at end of file"
                entry = {"kind": "meta", "text": line,
                         "old_no": None, "new_no": None}
            hunk["lines"].append(entry)
    flush_hunk()
    for f in files:
        if f["path"] == f["old_path"]:
            f["old_path"] = None
        if f["_chunk_bytes"] > MAX_BYTES:
            f["truncated"] = True
        del f["_chunk_bytes"], f["_line_count"]
    return files


def _numstat(cwd, spec_args, paths) -> dict:
    """{path: (additions, deletions, is_binary)} — "-"
    counts are git's binary marker."""
    raw = _git_bytes(
        cwd, "diff", "--numstat", "-z", "--no-ext-diff",
        *spec_args, "--", *paths)
    out = {}
    parts = raw.split(b"\x00")
    i = 0
    while i < len(parts):
        chunk = parts[i]
        i += 1
        if not chunk:
            continue
        fields = chunk.split(b"\t", 2)
        if len(fields) < 3:
            continue
        adds, dels, name = fields
        # Rename entries carry an empty name here + two
        # more NUL-separated fields (old path, new path);
        # the entry is keyed by the NEW path.
        if name == b"" and i + 1 < len(parts):
            name = parts[i + 1]
            i += 2
        path = name.decode("utf-8", errors="replace")
        if adds == b"-":
            out[path] = (0, 0, True)
        else:
            out[path] = (int(adds), int(dels), False)
    return out


def _name_set(cwd, spec_args) -> set:
    raw = _git_bytes(
        cwd, "diff", "--name-only", "-z", "--no-ext-diff",
        *spec_args, "--")
    return {p.decode("utf-8", errors="replace")
            for p in raw.split(b"\x00") if p}


def _run_diff(cwd, spec_args, paths, *, legs_from=None) -> list:
    """spec_args describes the comparison in ONE of git's
    forms: [base, target] for a range, [base] for
    base-vs-working-tree, [] for index-vs-working-tree.
    legs_from: optional {leg: spec_args} for the per-file
    leg sets (§18.2)."""
    raw = _git_bytes(
        cwd, "diff", "--no-ext-diff", "--find-renames",
        *spec_args, "--", *paths)
    files = _parse_patch(raw)
    stats = _numstat(cwd, spec_args, paths)
    leg_sets = {}
    if legs_from:
        for leg, leg_args in legs_from.items():
            leg_sets[leg] = _name_set(cwd, leg_args)
    for f in files:
        adds, dels, binary = stats.get(
            f["path"], (0, 0, f["binary"]))
        f["additions"] = adds
        f["deletions"] = dels
        f["binary"] = bool(f["binary"] or binary)
        if f["binary"]:
            f["hunks"] = []
        if leg_sets:
            f["legs"] = sorted(
                leg for leg, names in leg_sets.items()
                if f["path"] in names)
    return files


# ----------------------------------------------------------------
# Untracked + ignored groups (§18.4)
# ----------------------------------------------------------------

def _confined(root: Path, rel_raw: str):
    """(target, rel) for a worktree-relative path, or None
    when it escapes — the peek confinement rule restated
    for worktree scope."""
    rel = Path(rel_raw)
    if rel.is_absolute() or not str(rel):
        return None
    target = (root / rel).resolve()
    if root.resolve() not in target.parents \
            and target != root.resolve():
        return None
    return target, target.relative_to(root.resolve())


def _has_symlink_component(root: Path, rel: Path) -> bool:
    probe = root
    for part in rel.parts:
        probe = probe / part
        if os.path.islink(probe):
            return True
    return False


def render_new_file(root, rel_raw) -> dict:
    """One file as an all-additions diff entry — the peek
    of §18.4, under the lib/files caps and secret policy.
    Withheld and binary files carry metadata only."""
    root = Path(root)
    found = _confined(root, rel_raw)
    if found is None:
        return {"path": rel_raw, "withheld": "escapes",
                "is_binary": False, "size_bytes": 0,
                "hunks": [], "truncated": False}
    target, rel = found
    entry = {"path": rel.as_posix(), "withheld": None,
             "is_binary": False, "size_bytes": 0,
             "hunks": [], "truncated": False}
    if files_mod.is_secret(rel):
        # Before existence — the peek rule's own answer.
        if target.is_file():
            entry["size_bytes"] = target.stat().st_size
        entry["withheld"] = "secret"
        return entry
    if _has_symlink_component(root, rel):
        entry["withheld"] = "symlink"
        return entry
    if not target.is_file():
        entry["withheld"] = "missing"
        return entry
    if target.stat().st_size > 32 * 1024 * 1024:
        # Safety valve beyond the peek rule (which reads
        # whole files): a giant stray file is metadata
        # only, never loaded to be capped.
        entry["size_bytes"] = target.stat().st_size
        entry["truncated"] = True
        return entry
    raw = target.read_bytes()
    entry["size_bytes"] = len(raw)
    if files_mod._is_binary(target, raw[:8192]):
        entry["is_binary"] = True
        return entry
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = len(raw) > MAX_BYTES or len(lines) > MAX_LINES
    shown = lines[:MAX_LINES]
    if truncated and len(raw) > MAX_BYTES:
        # Byte cap as well as the line cap (the peek rule):
        # trim whole lines until the shown text fits.
        total = 0
        keep = 0
        for ln in shown:
            total += len(ln.encode("utf-8")) + 1
            if total > MAX_BYTES:
                break
            keep += 1
        shown = shown[:keep]
    entry["truncated"] = truncated
    entry["hunks"] = [{
        "old_start": 0, "old_lines": 0,
        "new_start": 1, "new_lines": len(lines),
        "lines": [
            {"kind": "add", "text": ln, "old_no": None,
             "new_no": i + 1}
            for i, ln in enumerate(shown)
        ],
    }]
    return entry


def _untracked(root) -> list:
    raw = _git(root, "status", "--porcelain", "-z",
               "--untracked-files=normal")
    out = []
    for record in raw.split("\x00"):
        if len(record) < 4 or not record.startswith("?? "):
            continue
        rel = record[3:]
        is_dir = rel.endswith("/")
        item = render_new_file(root, rel.rstrip("/")) \
            if not is_dir else {
                "path": rel, "withheld": None,
                "is_binary": False, "size_bytes": 0,
                "hunks": [], "truncated": False}
        item["is_dir"] = is_dir
        out.append(item)
    return out


def _ignored_changed(root) -> dict:
    try:
        head_time = int(_git(root, "log", "-1",
                             "--format=%ct",
                             "HEAD").strip() or 0)
    except DiffError:
        # No commits yet: no baseline time exists, so
        # every ignored file present counts as changed.
        head_time = 0
    raw = _git(root, "ls-files", "--others", "--ignored",
               "--exclude-standard", "-z")
    out, truncated = [], False
    for record in raw.split("\x00"):
        if not record:
            continue
        target = Path(root) / record
        try:
            st = target.stat()
        except OSError:
            continue
        if int(st.st_mtime) <= head_time:
            continue
        if len(out) >= IGNORED_GROUP_CAP:
            truncated = True
            break
        rel = Path(record)
        out.append({
            "path": record,
            "size_bytes": st.st_size,
            "modified": int(st.st_mtime),
            "withheld": "secret"
            if files_mod.is_secret(rel) else None,
            "is_binary": files_mod._is_binary(
                target, target.read_bytes()[:8192])
            if target.is_file() else False,
        })
    return {"files": out, "truncated": truncated,
            "head_commit_time": head_time}


def peek_file(root, *, worktree=None, path) -> dict:
    """Content peek for one untracked/ignored file in a
    worktree (read-only, the §18.4 peek): the same
    rendering as a new file, minus any diff claim. The
    server's `?peek=` rides this; the file is never part
    of a diff by being peeked."""
    root = Path(root)
    entries = _worktree_paths(root)
    wt_path = entries[0][0] if entries else None
    if worktree:
        wt_path = None
        for cand, branch in entries:
            if worktree in (cand, branch):
                wt_path = cand
                break
        if wt_path is None:
            raise DiffError(
                404, f"unknown worktree: {worktree!r}")
    if wt_path is None:
        raise DiffError(404, f"not a git repository: {root}")
    return render_new_file(wt_path, path)


# ----------------------------------------------------------------
# The one entry point
# ----------------------------------------------------------------

def get_diff(root, *, worktree=None, mode="working",
             base=None, target=None, bundle=None,
             plans_dir=None, all_files=False) -> dict:
    """Resolve the anchor + mode to the (base, target,
    paths) triple and serve the diff, structured.

    Anchors: `worktree` (branch name or path; default the
    main checkout), `bundle` (bundle id or slug — selects
    its linked worktree per D5 and narrows paths to the
    plan's declared files), or a commit (mode=commit with
    base=<id>, or mode=range with base=/target=). A
    request naming none of these is unanchored — refused
    (D10)."""
    root = Path(root)
    if mode not in MODES:
        raise DiffError(400, f"unknown mode: {mode!r} "
                             f"(modes: {', '.join(MODES)})")
    try:
        entries = _worktree_paths(root)
    except DiffError:
        raise DiffError(404, f"not a git repository: {root}")
    if not entries:
        raise DiffError(404, f"not a git repository: {root}")
    main_branch = _main_branch(root, entries)

    declared, warnings, bundle_id = [], [], None
    linked_branch = None
    plan_gone = False
    if bundle is not None:
        if plans_dir is None:
            raise DiffError(
                400, "bundle anchor needs a plans dir")
        found = _find_bundle(plans_dir, bundle)
        bundle_id = found["id"]
        doc = _bundle_plan_doc(plans_dir, found)
        if doc is None and found.get("plan"):
            # The bundle still references a plan document
            # that no longer loads — deleted or moved by
            # later work. The diff falls back to the
            # un-narrowed working state with a note; the
            # worktree's changes are still real.
            plan_gone = True
        if doc is not None:
            declared = declared_files(doc)
            for key, value in doc["fields"].items():
                if key.lower() == "worktree":
                    linked_branch = value.strip() \
                        .split("\n")[0].strip() or None
        if linked_branch is None:
            links = plan_worktree_links(plans_dir)
            by_plan = {v: k for k, v in links.items()}
            plan_rel = found["plan"]["path"] \
                if found.get("plan") else None
            if plan_rel and plan_rel in by_plan:
                linked_branch = by_plan[plan_rel]
        if linked_branch is None:
            for todo in found.get("todos", []):
                if todo.get("worktree"):
                    linked_branch = todo["worktree"]
                    break

    # -- anchor → worktree --------------------------------
    anchor_kind = "worktree"
    wt_path = wt_branch = None
    wanted = worktree or linked_branch
    if wanted:
        for path, branch in entries:
            if wanted in (path, branch):
                wt_path, wt_branch = path, branch
                break
        if wt_path is None:
            raise DiffError(
                404, f"unknown worktree: {wanted!r}")
    else:
        wt_path, wt_branch = entries[0]
    if bundle is not None:
        anchor_kind = "bundle"
    if mode in ("range", "commit"):
        anchor_kind = "commit"
    cwd = Path(wt_path)

    # -- vanished worktree --------------------------------
    if not cwd.is_dir():
        # The directory was deleted without `git worktree
        # remove` — a typed, honest "gone" result in the
        # normal payload shape, never a 500.
        return {
            "anchor": {"kind": anchor_kind,
                       "worktree": wt_path,
                       "branch": wt_branch,
                       "bundle": bundle_id},
            "mode": mode,
            "base": None, "target": None,
            "merge_base": None, "head": None,
            "base_kind": None,
            "note": "worktree path missing",
            "gone": True, "no_commits": False,
            "narrowed": False,
            "declared_files": declared
            if bundle is not None else [],
            "files": [],
            "totals": {"files": 0, "additions": 0,
                       "deletions": 0},
            "empty": True,
            "untracked": [],
            "ignored_changed": [],
            "ignored_truncated": False,
            "warnings": [],
        }

    # -- mode → comparison --------------------------------
    head = _head_sha(cwd)
    no_commits = head is None
    base_ref = _base_branch(cwd, wt_branch, main_branch)
    merge_base = _merge_base(cwd, base_ref, "HEAD") \
        if base_ref else None
    target_desc = base_desc = base_kind = None
    legs_from = None
    if no_commits and mode in ("working", "uncommitted"):
        # Zero-commit repo: the empty tree is the base,
        # so every tracked-or-staged file renders as an
        # addition; untracked files keep their §18.4
        # group. There is no committed leg.
        spec = [_EMPTY_TREE]
        base_desc = "empty tree"
        base_kind = "empty-tree"
        target_desc = "working state"
        legs_from = {"staged": [_EMPTY_TREE, "--cached"],
                     "unstaged": []}
    elif mode == "working":
        if merge_base:
            spec = [merge_base]
            base_desc = f"merge-base with {base_ref}"
            base_kind = "merge-base"
            legs_from = {
                "committed": [merge_base, "HEAD"],
                "staged": ["HEAD", "--cached"],
                "unstaged": [],
            }
        else:
            spec = ["HEAD"]
            base_desc = "HEAD"
            base_kind = "head"
            legs_from = {
                "staged": ["HEAD", "--cached"],
                "unstaged": [],
            }
        target_desc = "working state"
    elif mode == "uncommitted":
        spec = ["HEAD"]
        base_desc = "HEAD"
        base_kind = "head"
        target_desc = "working state"
        legs_from = {"staged": ["HEAD", "--cached"],
                     "unstaged": []}
    elif mode == "committed":
        if no_commits:
            raise DiffError(
                400, "no commits yet — nothing "
                     "committed to diff")
        if not merge_base:
            raise DiffError(
                400, "committed mode needs a fork point: "
                     "this worktree is its base branch")
        spec = [merge_base, "HEAD"]
        base_desc = f"merge-base with {base_ref}"
        base_kind = "merge-base"
        target_desc = "HEAD"
    elif mode == "range":
        if not base or not target:
            raise DiffError(
                400, "range mode needs base= and target=")
        lo, hi = _rev(cwd, base), _rev(cwd, target)
        spec = [lo, hi]
        base_desc, target_desc = lo[:12], hi[:12]
        base_kind = "range"
    else:  # commit
        if not base:
            raise DiffError(
                400, "commit mode needs base=<commit id>")
        sha = _rev(cwd, base)
        try:
            parent = _git(cwd, "rev-parse", "--verify",
                          "--quiet", f"{sha}^").strip() \
                or None
        except DiffError:
            parent = None
        spec = [parent or _EMPTY_TREE, sha]
        base_desc = (parent or "∅")[:12]
        target_desc = sha[:12]
        base_kind = "empty-tree" if parent is None \
            else "commit"

    # -- paths narrowing (bundle anchor) -----------------
    paths, narrowed = [], False
    if bundle is not None and declared and not all_files:
        paths = declared
        narrowed = True

    files = _run_diff(cwd, spec, paths, legs_from=legs_from)

    totals = {
        "files": len(files),
        "additions": sum(f["additions"] for f in files),
        "deletions": sum(f["deletions"] for f in files),
    }

    # -- the §18.4 groups ----------------------------------
    untracked = _untracked(cwd) \
        if mode in ("working", "uncommitted") else []
    ignored = _ignored_changed(cwd)
    if declared:
        ignored_paths = _check_ignored(cwd, declared)
        for path in ignored_paths:
            warnings.append({
                "kind": "plan-file-ignored",
                "path": path,
                "message": "plan file is git-ignored; "
                           "it will not be committed",
            })

    notes = []
    if no_commits:
        notes.append(
            "No commits yet — everything here is new.")
    if plan_gone:
        notes.append(
            "The plan anchored here no longer exists — "
            "showing the full working-state diff.")
    return {
        "anchor": {"kind": anchor_kind,
                   "worktree": wt_path,
                   "branch": wt_branch,
                   "bundle": bundle_id},
        "mode": mode,
        "base": base_desc, "target": target_desc,
        "merge_base": merge_base,
        "head": head,
        "base_kind": base_kind,
        "note": " ".join(notes) or None,
        "gone": False,
        "no_commits": no_commits,
        "narrowed": narrowed,
        "declared_files": declared if bundle is not None
        else [],
        "files": files,
        "totals": totals,
        "empty": not files,
        "untracked": untracked,
        "ignored_changed": ignored["files"],
        "ignored_truncated": ignored["truncated"],
        "warnings": warnings,
    }


def _check_ignored(cwd, paths) -> list:
    """The declared paths git ignores (check-ignore exits
    0 when any path is ignored, 1 when none are)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "check-ignore", "--",
             *paths], capture_output=True, text=True,
            timeout=5, env=_GIT_ENV)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode not in (0, 1):
        return []
    return [ln for ln in out.stdout.splitlines() if ln]
