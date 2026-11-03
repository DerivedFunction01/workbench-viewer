"""Annotation re-location (repo-home spec §12): given a
stored selection payload and the CURRENT anchor target,
find the quoted passage again — or say honestly that it
moved.

One algorithm, two implementations: this lib side feeds
agent pickup context (server pickup attaches
`anchor_context`); the client mirrors it over the rendered
DOM for highlight rendering. Both are tested against the
same fixtures. The rules (annotation plan, design §):

  1. Normalize: collapse every whitespace run (spaces,
     newlines, NBSP) to a single space and trim — in the
     stored quote/prefix/suffix and in the searched text.
     Matching is case-sensitive after normalization.
  2. Scope: search only inside the enclosing component
     (the structural derivation of sections/plans/
     anchors.ts, mirrored here against the parser's
     document model: section by heading slug, step block
     by number, table/diagram by index within section).
  3. Zero quote occurrences in scope -> orphan.
  4. Disambiguate by context score (prefix+suffix >
     prefix-only > suffix-only > bare). A unique best
     score wins; a tie -> ambiguous. Never guess.
  5. If the component id itself is absent (renamed or
     removed), widen ONCE to the whole document; a unique
     match there still locates, flagged component_missing.
  6. Re-location is a derivation at read time, never
     stored back (ruled-vs-derived discipline).

No writes anywhere in this module. A missing plan/entry
is `target_missing`, distinct from orphan: the target is
gone, not the passage.
"""

import re
from pathlib import Path

from . import registry as reg
from .plans import parser as plan_parser

_WS_RUN = re.compile(r"\s+")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def normalize(text) -> str:
    """Collapse every whitespace run to one space; trim.
    (Python's \\s on str covers NBSP and the Unicode space
    family, matching the client's /\\s+/ on the same text.)
    """
    return _WS_RUN.sub(" ", text or "").strip()


def slugify(text: str) -> str:
    """Mirror of sections/plans/anchors.ts slugify."""
    slug = _NON_SLUG.sub("-", (text or "").lower())
    slug = slug.strip("-")
    return slug or "section"


def _normalize_with_map(text: str):
    """Normalized text + a source-offset map: map[i] is
    the source index at which normalized char i begins
    (a collapsed whitespace run maps to its first char).
    Lets a normalized match span project back onto the
    raw source for excerpts."""
    out = []
    src = []
    pending = None  # source index of a pending space
    for i, ch in enumerate(text):
        if ch.isspace():
            if out and pending is None:
                pending = i
            continue
        if pending is not None:
            out.append(" ")
            src.append(pending)
            pending = None
        out.append(ch)
        src.append(i)
    return "".join(out), src


def _occurrences(haystack: str, needle: str):
    out = []
    at = haystack.find(needle)
    while at != -1:
        out.append(at)
        at = haystack.find(needle, at + 1)
    return out


def relocate(source_text: str, selection: dict) -> dict:
    """The pure algorithm over ONE text (the scoped
    region). Returns {status, span, component_missing}
    with span = (start, end) offsets into the RAW
    source_text when located, else None."""
    quote = normalize(selection.get("quote"))
    if not quote:
        return {"status": "orphan", "span": None,
                "component_missing": False}
    norm, src = _normalize_with_map(source_text or "")
    prefix = normalize(selection.get("prefix"))
    suffix = normalize(selection.get("suffix"))
    hits = _occurrences(norm, quote)
    if not hits:
        return {"status": "orphan", "span": None,
                "component_missing": False}

    def score(at):
        # Context match tolerates the single separator
        # space normalization leaves at the boundary: the
        # stored context is end-trimmed by normalize(),
        # so one leading/trailing space is stripped from
        # the source side before the exact comparison
        # (the client mirror applies the identical rule).
        end = at + len(quote)
        before = norm[:at]
        if before.endswith(" "):
            before = before[:-1]
        after = norm[end:]
        if after.startswith(" "):
            after = after[1:]
        pre = bool(prefix) and before.endswith(prefix)
        suf = bool(suffix) and after.startswith(suffix)
        return (3 if pre and suf else 2 if pre else
                1 if suf else 0)

    best = max(score(at) for at in hits)
    winners = [at for at in hits if score(at) == best]
    if len(winners) > 1:
        return {"status": "ambiguous", "span": None,
                "component_missing": False}
    at = winners[0]
    end = at + len(quote)
    span = (src[at], src[end - 1] + 1)
    return {"status": "located", "span": span,
            "component_missing": False}


def excerpt(source_text: str, span, *, context_lines=2) -> str:
    """The located passage with its surrounding lines
    from the raw source (the pickup work order's
    evidence)."""
    if span is None:
        return ""
    start, end = span
    lines = source_text.split("\n")
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    first = last = 0
    for i, off in enumerate(offsets):
        if off <= start:
            first = i
        if off < end:
            last = i
    lo = max(0, first - context_lines)
    hi = min(len(lines), last + context_lines + 1)
    return "\n".join(lines[lo:hi])


# ----------------------------------------------------------------
# Plan scoping: component id -> the source region it
# denotes (mirrors anchors.ts against the parser model)
# ----------------------------------------------------------------

def _section_by_slug(doc, slug):
    for sec in doc["sections"]:
        if slugify(sec["heading"]) == slug:
            return sec
    return None


def _scope_text(doc, component_id):
    """(region_text, section, step) for the component,
    or None when the component id denotes nothing in
    this document (renamed/removed — the caller widens
    to the whole document once)."""
    if not component_id or not component_id.startswith(
            "plans/"):
        return None
    name = component_id[len("plans/"):]
    if name in ("plan-reader", "plan-list"):
        return doc["markdown"], None, None
    if name == "plan-header":
        return doc["header_raw"], None, None
    if name.startswith("step-"):
        try:
            n = int(name[len("step-"):])
        except ValueError:
            return None
        for step in doc["steps"]:
            if step["n"] == n:
                section = _steps_section(doc)
                return step["raw"], section, step
        return None
    if name.startswith("section-"):
        sec = _section_by_slug(doc, name[len("section-"):])
        if sec is None:
            return None
        return sec["raw"], sec, None
    for kind in ("table-", "diagram-"):
        if name.startswith(kind):
            rest = name[len(kind):]
            slug, _, index = rest.rpartition("-")
            sec = _section_by_slug(doc, slug)
            if sec is None:
                return None
            if kind == "diagram-":
                try:
                    idx = int(index)
                except ValueError:
                    return None
                diagrams = [b for b in sec["blocks"]
                            if b["type"] == "mermaid"]
                if 1 <= idx <= len(diagrams):
                    return (diagrams[idx - 1]["raw"], sec,
                            None)
                return None
            # A table lives inside a markdown block; the
            # source cannot isolate one rendered table
            # from its block mates 1:1, so the scope is
            # the section raw (still scoped; context
            # disambiguation keeps it honest).
            return sec["raw"], sec, None
    return None


def _steps_section(doc):
    for sec in doc["sections"]:
        if sec["is_steps"]:
            return sec
    return None


def _step_at(doc, region_text, span):
    """The step whose raw region (inside the searched
    region — a steps section searched whole for table
    scopes, or the whole document after a widen) contains
    the span, if any."""
    cursor = 0
    for step in doc["steps"]:
        at = region_text.find(step["raw"], cursor)
        if at == -1:
            continue
        if at <= span[0] < at + len(step["raw"]):
            return step
        cursor = at + len(step["raw"])
    return None


# ----------------------------------------------------------------
# Pickup context (Step 7's shape, built here)
# ----------------------------------------------------------------

def resolve_context(project, message) -> dict | None:
    """The anchor_context for one message, or None when
    the message carries no selection (not an annotation
    root). `project` is the sweep project (duck-typed:
    .manifest with .plans/.registry paths). Read-only."""
    selection = message.get("selection")
    if not selection:
        return None
    anchor_type = message.get("anchor_type")
    if anchor_type == "text":
        return _text_context(project, message, selection)
    if anchor_type == "component":
        return _component_context(project, message,
                                  selection)
    return None


def _text_context(project, message, selection) -> dict:
    base = {
        "kind": "text",
        "relocated": False,
        "status": "target_missing",
        "component_id": selection.get("component_id"),
        "component_label": selection.get("component_label"),
        "section_heading":
            selection.get("section_heading"),
        "step": None,
        "quote": selection.get("quote"),
        "excerpt": None,
        "component_missing": False,
    }
    plans_dir = project.manifest.plans \
        if project is not None else None
    ref = message.get("anchor_ref")
    if plans_dir is None or not ref:
        return base
    try:
        doc = plan_parser.load_plan(plans_dir, ref)
    except (ValueError, FileNotFoundError, OSError):
        return base
    scoped = _scope_text(doc, selection.get("component_id"))
    if scoped is not None:
        region, section, step = scoped
        result = relocate(region, selection)
        missing = False
    else:
        region = doc["markdown"]
        section, step = None, None
        result = relocate(region, selection)
        missing = True
    base["status"] = result["status"]
    base["component_missing"] = missing
    base["relocated"] = result["status"] == "located"
    if section is not None:
        base["section_heading"] = section["heading"]
    if step is None and result["span"] is not None:
        step = _step_at(doc, region, result["span"])
    if step is not None:
        base["step"] = step["n"]
    if result["span"] is not None:
        base["excerpt"] = excerpt(region, result["span"])
    return base


def _component_context(project, message, selection) -> dict:
    base = {
        "kind": "component",
        "component_id": selection.get("component_id"),
        "component_label":
            selection.get("component_label"),
        "entry_id": selection.get("entry_id")
        or message.get("anchor_ref"),
        "entry_title": None,
        "present": False,
        "status": "target_missing",
    }
    manifest = project.manifest if project else None
    db = manifest.db_path if manifest else None
    if db is None or not base["entry_id"]:
        return base
    try:
        entry = reg.get_entry(db, base["entry_id"])
    except Exception:
        return base
    base["entry_title"] = entry.get("title")
    base["present"] = _component_present(entry, selection)
    base["status"] = "present" if base["present"] \
        else "anchor moved"
    return base


def _component_present(entry, selection) -> bool:
    """Component presence, as far as lib can know it: the
    entry's main file, when it lives in the repo
    (entry-dir source), is scanned for the component's
    data-anchor id. An entry held by reference has no
    file to scan — the entry's existence is all lib can
    attest, and the drill-in's own render makes the
    final call client-side."""
    component_id = selection.get("component_id") or ""
    entry_dir = entry.get("entry_dir")
    main_file = entry.get("main_file")
    if not entry_dir or not main_file:
        return True
    path = Path(entry_dir) / main_file
    try:
        text = path.read_text(encoding="utf-8",
                              errors="replace")
    except OSError:
        return True
    needle = re.compile(
        r"data-anchor\s*=\s*[\"']" + re.escape(component_id)
        + r"[\"']")
    return bool(needle.search(text))
