"""Repo census + git-state derivations (absorption plan,
steps 2-3).

The census walks a workspace root and finds every git repo
under it — manifest or not; a repo record is a distinct
concept from a project. Status, publication, and exposure
are derivations over one repo, computed here so the client
renders what it is served.

Derivation only, and read-only by construction: every git
invocation runs with GIT_OPTIONAL_LOCKS=0 and no command
writes (no index updates, no fetches, no worktree changes).
A broken, locked, or mid-operation repo degrades its own
record with an error field; it never raises into the census
or the list.
"""

import fnmatch
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .util import now_iso, parse_iso

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

# Directories the census never descends into, matched as
# fnmatch patterns against each path segment (".venv*"
# covers ".venv", ".venv-2", and friends). ".git" is listed
# for completeness; a ".git" segment means the parent was
# already claimed as a repo before descent is considered.
DEFAULT_PRUNE = (".git", "node_modules", "__pycache__",
                 ".artifacts", ".venv*", "venv",
                 ".pytest_cache", ".tox", ".mypy_cache")

# A repo's ahead/behind numbers are only as fresh as the
# newest remote-ref mtime; older than this the remote view
# is flagged stale.
REMOTE_STALE_AFTER_HOURS = 24


class RepoError(Exception):
    """A git derivation failed, with a human-readable
    reason (carried on the degraded record, never raised
    past the per-repo derivation boundary)."""


# Reasons that can reach a payload come from this small
# vocabulary ONLY — raw git stderr never renders (a
# vanished reference is a state, not error text).
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
        raise RepoError("git timed out")
    except OSError:
        raise RepoError("git unavailable")
    if out.returncode != 0:
        raise RepoError(_label(out.stderr or out.stdout))
    return out.stdout


def _git_ok(cwd, *args) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, timeout=10,
            env=_GIT_ENV)
        return out.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ----------------------------------------------------------------
# Census

def _pruned(name: str, prune) -> bool:
    return any(fnmatch.fnmatchcase(name, pat) for pat in prune)


def _worktree_parent(here: Path, root: Path):
    """The census id of a linked worktree's parent repo:
    resolve --git-common-dir against the worktree, take
    its parent directory, and express it relative to the
    census root. None when resolution fails or the parent
    lives outside the walked root."""
    try:
        common = _git(here, "rev-parse",
                      "--git-common-dir").strip()
    except RepoError:
        return None
    main_root = (here / common).resolve().parent
    try:
        return main_root.relative_to(root).as_posix()
    except ValueError:
        return None


def discover_repos(root, max_depth=3, prune=DEFAULT_PRUNE) -> list:
    """Every repo under `root`, as records sorted by id:
    {id, name, root, is_worktree, parent_id}. The id is
    the root-relative path (a repo AT the root takes the
    root's own name). The walk never descends into a found
    repo or a pruned directory, and never looks deeper
    than `max_depth` segments below the root."""
    root = Path(root).resolve()
    records = {}
    base = len(root.parts)
    for dirpath, dirnames, _files in os.walk(root):
        here = Path(dirpath)
        depth = len(here.parts) - base
        git_dir = here / ".git"
        if git_dir.is_dir() or git_dir.is_file():
            rel = here.relative_to(root).as_posix()
            is_wt = git_dir.is_file()
            records[rel] = {
                "id": root.name if rel == "." else rel,
                "name": root.name if rel == "." else rel,
                "root": str(here),
                "is_worktree": is_wt,
                "parent_id": _worktree_parent(here, root)
                if is_wt else None,
            }
            dirnames[:] = []  # never descend into a repo
            continue
        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = sorted(
                d for d in dirnames if not _pruned(d, prune))
    return [records[k] for k in sorted(records)]


# ----------------------------------------------------------------
# Status pieces

def _porcelain(root) -> tuple:
    """(staged, unstaged, untracked) path lists from
    porcelain v1; a path may appear in both staged and
    unstaged. Renames report their target path."""
    out = _git(root, "status", "--porcelain=v1",
               "--untracked-files=normal")
    staged, unstaged, untracked = [], [], []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        x, y, path = line[0], line[1], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if x == "?" and y == "?":
            untracked.append(path)
            continue
        if x not in (" ", "?"):
            staged.append(path)
        if y not in (" ", "?"):
            unstaged.append(path)
    return staged, unstaged, untracked


def _numstat(root, cached: bool) -> dict:
    """path -> (insertions, deletions) from diff --numstat;
    insertions None marks a binary file."""
    args = ["diff", "--numstat"]
    if cached:
        args.append("--cached")
    result = {}
    for line in _git(root, *args).splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, dels, path = parts[0], parts[1], parts[-1]
        if " => " in path:
            path = path.split(" => ")[-1].strip("{}")
        result[path] = (None if ins == "-" else int(ins),
                        None if dels == "-" else int(dels))
    return result


def _has_upstream(root) -> bool:
    return _git_ok(root, "rev-parse", "--abbrev-ref",
                   "@{upstream}")


def _upstream(root):
    if not _has_upstream(root):
        return None
    return _git(root, "rev-parse", "--abbrev-ref",
                "--symbolic-full-name", "@{upstream}").strip()


# ----------------------------------------------------------------
# Publication pieces

def _display_url(url: str) -> str:
    """A remote URL safe to show: credentials stripped,
    scp-style folded to host/path, trailing .git removed."""
    u = url.strip()
    if "://" in u:  # scheme://[user@]host/path
        scheme, rest = u.split("://", 1)
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        u = f"{scheme}://{rest}"
    elif "@" in u and ":" in u:  # scp style user@host:path
        u = u.split("@", 1)[1].replace(":", "/", 1)
    if u.endswith(".git"):
        u = u[:-4]
    return u


def _url_host(url: str) -> str:
    d = _display_url(url)
    d = d.split("://", 1)[-1]
    return d.split("/", 1)[0] or None


def _remotes(root) -> list:
    out = []
    for name in _git(root, "remote").split():
        url = _git(root, "remote", "get-url", name).strip()
        out.append({"name": name,
                    "url_display": _display_url(url),
                    "host": _url_host(url)})
    return out


def _remote_view_as_of(root):
    """Newest mtime among the remote-tracking ref files
    and FETCH_HEAD, as an ISO string (None when the repo
    has never fetched). Ahead/behind numbers are only as
    fresh as this timestamp."""
    try:
        common = _git(root, "rev-parse",
                      "--git-common-dir").strip()
    except RepoError:
        return None
    gitdir = (Path(root) / common).resolve()
    candidates = []
    refs = gitdir / "refs" / "remotes"
    if refs.is_dir():
        candidates += [p for p in refs.rglob("*") if p.is_file()]
    if (gitdir / "FETCH_HEAD").is_file():
        candidates.append(gitdir / "FETCH_HEAD")
    newest = None
    for p in candidates:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if newest is None or m > newest:
            newest = m
    if newest is None:
        return None
    return datetime.fromtimestamp(
        newest, timezone.utc).isoformat()


def _unpushed(root, ref: str) -> tuple:
    """(count, oldest_date) of commits on `ref` that are
    in NO remote-tracking ref."""
    shas = _git(root, "rev-list", ref, "--not",
                "--remotes").split()
    if not shas:
        return 0, None
    oldest = _git(root, "log", "-1", "--format=%aI",
                  shas[-1]).strip()
    return len(shas), oldest


def _default_branch(names):
    for cand in ("main", "master"):
        if cand in names:
            return cand
    return None


def _branch_details(root) -> tuple:
    """(rows, default_branch): one row per local branch —
    upstream, ahead/behind against it, unpushed count and
    oldest unpushed date, and whether the default branch
    already contains it."""
    fmt = "%(refname:short)%09%(upstream:short)"
    parsed, names = [], []
    raw = _git(root, "for-each-ref", "refs/heads",
               f"--format={fmt}")
    for line in raw.splitlines():
        if not line.strip():
            continue
        name, _, upstream = line.partition("\t")
        parsed.append((name.strip(), upstream.strip() or None))
        names.append(name.strip())
    default = _default_branch(names)
    rows = []
    for name, upstream in parsed:
        ahead = behind = None
        if upstream:
            counts = _git(root, "rev-list", "--left-right",
                          "--count",
                          f"{name}...{upstream}").split()
            ahead, behind = int(counts[0]), int(counts[1])
        unpushed, oldest = _unpushed(root, name)
        contained = None
        if default and name != default:
            contained = _git_ok(root, "merge-base",
                                "--is-ancestor", name, default)
        rows.append({"name": name, "upstream": upstream,
                     "ahead": ahead, "behind": behind,
                     "unpushed_commits": unpushed,
                     "oldest_unpushed_at": oldest,
                     "contained_in_default": contained})
    return rows, default


def _publication(root, summary: dict, *,
                 remote_stale_after_hours, now) -> dict:
    """Fill remotes / publication / sync / exposure /
    remote freshness onto a summary dict, in place."""
    remotes = _remotes(root)
    summary["remotes"] = remotes
    upstream = summary.get("upstream")
    if not remotes:
        publication = "local_only"
    elif not upstream:
        publication = "remote_no_upstream"
    else:
        publication = "tracking"
    summary["publication"] = publication
    as_of = _remote_view_as_of(root) if remotes else None
    summary["remote_view_as_of"] = as_of
    stale = False
    if as_of:
        age_h = (now - parse_iso(as_of)).total_seconds() / 3600
        stale = age_h > remote_stale_after_hours
    summary["remote_stale"] = stale
    branch = summary.get("branch")
    unpushed, oldest = (0, None)
    if branch and branch != "HEAD":
        unpushed, oldest = _unpushed(root, branch)
    if publication == "local_only":
        state = "local_only"
    elif not upstream:
        state = "no_upstream"
    elif summary.get("behind") and summary.get("ahead"):
        state = "diverged"
    elif summary.get("ahead"):
        state = "ahead"
    elif summary.get("behind"):
        state = "behind"
    else:
        state = "synced"
    summary["sync"] = {"state": state,
                       "unpushed_count": unpushed,
                       "oldest_unpushed_at": oldest}
    dirty_counts = summary.get("dirty_counts") or {}
    dirty_total = sum(dirty_counts.values())
    if publication == "local_only":
        total = int(_git(root, "rev-list", "--count",
                         "HEAD").strip())
        level = "local_only" if total > 0 else "backed_up"
        exposed_commits = total
    elif dirty_total > 0:
        level, exposed_commits = "uncommitted_work", unpushed
    elif unpushed > 0:
        level, exposed_commits = "unbacked_commits", unpushed
    else:
        level, exposed_commits = "backed_up", 0
    summary["exposure"] = {"level": level,
                           "commits": exposed_commits,
                           "files": dirty_total}
    return summary


# ----------------------------------------------------------------
# Public derivations

def repo_summary(repo: dict, *,
                 remote_stale_after_hours=REMOTE_STALE_AFTER_HOURS,
                 now=None) -> dict:
    """The list-level derivation for one census record:
    branch, head, upstream, ahead/behind, dirty counts,
    and the publication / sync / exposure block. A repo
    whose git state cannot be read degrades in place:
    the identity fields survive, the derived fields go
    None, and `error` carries the reason."""
    now = now or datetime.now(timezone.utc)
    root = Path(repo["root"])
    s = dict(repo)
    try:
        s["branch"] = _git(
            root, "rev-parse", "--abbrev-ref", "HEAD").strip()
        s["head"] = _git(root, "rev-parse", "HEAD").strip()
        s["head_full"] = s["head"]
        s["head_short"] = s["head"][:7]
        s["head_subject"] = _git(
            root, "log", "-1", "--format=%s").strip()
        upstream = _upstream(root)
        s["upstream"] = upstream
        if upstream:
            counts = _git(root, "rev-list", "--left-right",
                          "--count",
                          "HEAD...@{upstream}").split()
            s["ahead"], s["behind"] = int(counts[0]), int(counts[1])
        else:
            s["ahead"] = s["behind"] = None
        staged, unstaged, untracked = _porcelain(root)
        s["dirty_counts"] = {"staged": len(staged),
                             "unstaged": len(unstaged),
                             "untracked": len(untracked)}
        s["is_clean"] = not (staged or unstaged or untracked)
        s["error"] = None
        s = _publication(
            root, s,
            remote_stale_after_hours=remote_stale_after_hours,
            now=now)
    except RepoError as e:
        s.update(branch=None, head=None, head_full=None,
                 head_short=None,
                 head_subject=None, upstream=None, ahead=None,
                 behind=None, dirty_counts=None, is_clean=None,
                 error=str(e), remotes=[], publication=None,
                 sync=None, exposure=None,
                 remote_view_as_of=None, remote_stale=None)
    return s


def repo_status(repo: dict, *,
                remote_stale_after_hours=REMOTE_STALE_AFTER_HOURS,
                now=None) -> dict:
    """The full derivation: the summary plus the three
    dirty groups with per-file insertions/deletions, the
    last 10 commits, per-branch publication details, and
    the worktree list. A degraded summary returns as-is —
    there is nothing further to derive from it."""
    root = Path(repo["root"])
    s = repo_summary(
        repo,
        remote_stale_after_hours=remote_stale_after_hours,
        now=now)
    if s.get("error"):
        return s
    staged, unstaged, untracked = _porcelain(root)
    staged_stat = _numstat(root, cached=True)
    unstaged_stat = _numstat(root, cached=False)

    def entries(paths, stats):
        out = []
        for p in paths:
            ins, dels = stats.get(p, (None, None))
            out.append({"path": p, "insertions": ins,
                        "deletions": dels,
                        "is_binary": ins is None and p in stats})
        return sorted(out, key=lambda e: e["path"])

    s["staged"] = entries(staged, staged_stat)
    s["unstaged"] = entries(unstaged, unstaged_stat)
    s["untracked"] = [{"path": p} for p in sorted(untracked)]
    log = _git(root, "log", "-10",
               "--format=%H%x1f%h%x1f%s%x1f%aI")
    s["commits"] = [
        {"hash": f[0], "short": f[1], "subject": f[2],
         "date": f[3]}
        for f in (line.split("\x1f")
                  for line in log.splitlines())
        if len(f) == 4
    ]
    details, default = _branch_details(root)
    s["branches"] = [row["name"] for row in details]
    s["branch_details"] = details
    s["default_branch"] = default
    worktrees, current = [], {}
    for line in _git(root, "worktree", "list",
                     "--porcelain").splitlines():
        if not line.strip():
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, val = line.partition(" ")
        current[key] = val
    if current:
        worktrees.append(current)
    s["worktrees"] = [
        {"path": w.get("worktree"),
         "head": (w.get("HEAD") or "")[:7],
         "branch": (w.get("branch") or "")
         .replace("refs/heads/", "") or None}
        for w in worktrees
    ]
    s["captured_at"] = now_iso()
    return s


# ----------------------------------------------------------------
# File tree (absorption plan, step 4)

# The full-tree answer is capped: past this many entries
# (files + folders) the payload truncates and says so,
# rather than growing without bound on a huge repo.
ALL_ENTRIES_CAP = 20000


def _hidden(path: str) -> bool:
    return any(part.startswith(".")
               for part in path.split("/"))


def repo_files(repo: dict, include_all: bool = False) -> dict:
    """The repo's file lists: tracked + untracked always;
    with include_all, the full tree — every file classified
    tracked / untracked / ignored from git's own
    enumerations, plus the folder skeleton (empty and
    hidden folders included; `.git` never listed; prune-
    list directories collapse to one flagged node), each
    entry flagged hidden when any path segment is a
    dot-name, capped at ALL_ENTRIES_CAP with an
    all_truncated flag."""
    root = Path(repo["root"])
    tracked = _git(root, "ls-files").splitlines()
    _staged, _unstaged, untracked = _porcelain(root)
    out = {"tracked": sorted(tracked),
           "untracked": sorted(untracked),
           "captured_at": now_iso()}
    if not include_all:
        return out
    untracked_files = _git(
        root, "ls-files", "--others",
        "--exclude-standard").splitlines()
    ignored_files = _git(
        root, "ls-files", "--others", "--ignored",
        "--exclude-standard").splitlines()
    entries = []
    for kind, paths in (("tracked", tracked),
                        ("untracked", untracked_files),
                        ("ignored", ignored_files)):
        for path in paths:
            if path.endswith("/"):
                continue  # directory entries are the walk's job
            entries.append({"path": path, "kind": kind,
                            "hidden": _hidden(path)})
    folders = []
    resolved = root.resolve()
    for dirpath, dirnames, _names in os.walk(resolved):
        rel_dir = Path(dirpath).relative_to(resolved)
        keep = []
        for name in sorted(dirnames):
            rel = (rel_dir / name).as_posix() \
                if rel_dir != Path(".") else name
            if name == ".git":
                continue
            collapsed = _pruned(name, DEFAULT_PRUNE)
            folders.append({"path": rel,
                            "hidden": _hidden(rel),
                            "collapsed": collapsed})
            if not collapsed:
                keep.append(name)
        dirnames[:] = keep
    entries.sort(key=lambda e: e["path"])
    folders.sort(key=lambda f: f["path"])
    truncated_all = len(entries) + len(folders) > ALL_ENTRIES_CAP
    if truncated_all:
        entries = entries[:ALL_ENTRIES_CAP]
    out.update({"entries": entries, "folders": folders,
                "all_truncated": truncated_all})
    return out


# One directory's listing is capped far below the
# whole-tree cap: a single directory holding more than
# this many children is pathological, and the flag says
# so rather than truncating silently.
DIR_LISTING_CAP = 2000


def repo_dir(repo: dict, dir_rel: str) -> dict:
    """One directory's immediate listing (the tree's
    lazy unit): the files directly in `dir_rel` classified
    tracked / untracked / ignored from git's own
    enumerations (the repo_files sets, prefix-filtered),
    plus its immediate subdirectories with their prune
    (collapsed) and hidden flags. The Files tree loads
    the root first and builds outward only as folders
    open, so a huge repo costs one small listing per
    opened folder instead of one capped enumeration.

    Raises ValueError for a malformed directory path and
    FileNotFoundError when it names no directory here.
    Symlinked directories are not listed (the tree never
    follows links out of the repo)."""
    root = Path(repo["root"])
    rel = (dir_rel or "").strip("/")
    if rel == ".":
        rel = ""
    if rel.startswith("/") or ".." in rel.split("/"):
        raise ValueError(f"bad directory: {dir_rel!r}")
    target = (root / rel) if rel else root
    if not target.is_dir():
        raise FileNotFoundError(rel or ".")
    prefix = f"{rel}/" if rel else ""
    entries = []
    for kind, paths in (
            ("tracked", _git(root, "ls-files").splitlines()),
            ("untracked", _git(
                root, "ls-files", "--others",
                "--exclude-standard").splitlines()),
            ("ignored", _git(
                root, "ls-files", "--others", "--ignored",
                "--exclude-standard").splitlines())):
        for path in paths:
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix):]
            if rest and "/" not in rest:
                entries.append({"path": path, "kind": kind,
                                "hidden": _hidden(path)})
    folders = []
    for child in sorted(target.iterdir(), key=lambda p: p.name):
        if child.is_symlink() or not child.is_dir() \
                or child.name == ".git":
            continue
        crel = prefix + child.name
        folders.append({"path": crel,
                        "hidden": _hidden(crel),
                        "collapsed": _pruned(
                            child.name, DEFAULT_PRUNE)})
    entries.sort(key=lambda e: e["path"])
    truncated = len(entries) + len(folders) > DIR_LISTING_CAP
    if truncated:
        entries = entries[:DIR_LISTING_CAP]
    return {"dir": rel, "entries": entries,
            "folders": folders, "truncated": truncated,
            "captured_at": now_iso()}
