"""Diff anchors: plan declared files and bundles.

One slice of lib/diffs (see the package docstring):
the bundle anchor's narrowing set — the plan's
declared `files:` lists (§18.3) — and the bundle /
plan-document resolution behind it.
"""

import re

from ..plans import bundles as bundle_parser
from ..plans import parser as plan_parser
from .git_plumbing import DiffError

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
