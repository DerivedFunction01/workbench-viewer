#!/usr/bin/env python3
"""File-length scanner: the 800-line cap (context/code-standards.md).

Any in-scope source file over MAX_LINES is a finding. At the cap
the promotion rule applies: the file becomes a same-named module
folder whose files split by intent, each leaf at or under the cap
with headroom (splits target 780).

Scope: tracked and unignored untracked source files — .py, .ts,
.tsx, .js, .mjs — enumerated through git so worktrees and fresh
clones see the same set. Excluded: the vendored SDK tree
(viewer/vendor/**, pinned third-party), dependency and build
output (node_modules, .bun-cache, dist segments), and the
builder-generated viewer/server/.generated/**.

Line count is the splitlines count of the UTF-8 text, matching the
sister repos' length scanner. Unreadable or non-UTF-8 files are
skipped, never findings.

    python3 tools/length.py [root]   # exit 0 = clean, 1 = findings
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_LINES = 800

EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs"}
EXCLUDED_SEGMENTS = {"node_modules", ".bun-cache", "dist"}
EXCLUDED_PREFIXES = ("viewer/vendor/", "viewer/server/.generated/")


def is_in_scope(rel_path: str) -> bool:
    if rel_path.startswith(EXCLUDED_PREFIXES):
        return False
    parts = rel_path.split("/")
    if any(part in EXCLUDED_SEGMENTS for part in parts):
        return False
    return Path(rel_path).suffix in EXTENSIONS


def source_files(root: Path) -> list[str]:
    """Repo-relative source paths via git (tracked + unignored)."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others",
         "--exclude-standard", "-z"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return sorted(p for p in out.split("\0") if p and is_in_scope(p))


def line_count(path: Path) -> int | None:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return None


def find_over_cap(root: Path, rel_paths: list[str]) -> list[tuple[str, int]]:
    findings = []
    for rel_path in rel_paths:
        count = line_count(root / rel_path)
        if count is not None and count > MAX_LINES:
            findings.append((rel_path, count))
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 \
        else Path(__file__).resolve().parent.parent
    findings = find_over_cap(root, source_files(root))
    for rel_path, count in findings:
        print(f"{rel_path}: {count} lines exceeds the {MAX_LINES}-line "
              "cap; promote to a module split by intent")
    if findings:
        print(f"length: {len(findings)} file(s) over the cap")
        return 1
    print(f"length: clean (cap {MAX_LINES})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
