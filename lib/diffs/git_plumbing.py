"""Diff git plumbing: the read-only git invocations.

One slice of lib/diffs (see the package docstring):
every git call runs with GIT_OPTIONAL_LOCKS=0 and
--no-ext-diff, revisions are validated before they
reach a command line, and error text comes from a
small label vocabulary — raw git stderr never renders.
"""

import os
import subprocess
from pathlib import Path

from .. import files as files_mod

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
