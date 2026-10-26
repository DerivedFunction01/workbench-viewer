"""The validator registry (the ALL_SCANNERS shape, at
workbench scale): small validator functions collected in one
ALL_VALIDATORS tuple; `wb validate` runs them and reports
named findings. A finding is {validator, entry, message}.

Uniformity is part of this registry, and the canonical /
approve paths run the uniformity subset — a non-uniform
mockup cannot be approved by accident (subplan 09).
"""

import json
import re
from pathlib import Path

from . import registry as reg
from .util import sha256_file

STATE_FIELD_TYPES = ("toggle", "select", "text", "number")
_VARIANT_SUFFIX = re.compile(
    r"(New|Final|V\d+|Copy|Old|Bak|Temp)\.(html?|tsx|jsx|ts|js)$")
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _finding(validator, entry_id, message):
    return {"validator": validator, "entry": entry_id,
            "message": message}


# ----------------------------------------------------------------
# State schema / values (used by registry mutations too)
# ----------------------------------------------------------------

def check_state_schema(schema):
    """None if well-formed, else a problem string. Schema
    shape: {field: {"type": toggle|select|text|number,
    "options": [...] (select), "default": ...}}"""
    if not isinstance(schema, dict):
        return "schema must be an object of field specs"
    for name, spec in schema.items():
        if not isinstance(spec, dict):
            return f"field {name!r}: spec must be an object"
        t = spec.get("type")
        if t not in STATE_FIELD_TYPES:
            return (f"field {name!r}: type must be one of "
                    f"{STATE_FIELD_TYPES}")
        if t == "select" and not spec.get("options"):
            return f"field {name!r}: select needs options"
    return None


def check_state_values(schema, state):
    if not isinstance(state, dict):
        return "state must be an object"
    for name, value in state.items():
        spec = schema.get(name)
        if spec is None:
            return f"unknown state field {name!r}"
        t = spec["type"]
        if t == "toggle" and not isinstance(value, bool):
            return f"field {name!r}: toggle needs true/false"
        if t == "select" and value not in spec.get("options", []):
            return f"field {name!r}: not one of its options"
        if t == "number" and not isinstance(value, (int, float)):
            return f"field {name!r}: needs a number"
        if t == "text" and not isinstance(value, str):
            return f"field {name!r}: needs text"
    return None


# ----------------------------------------------------------------
# Uniformity subset (runs on the canonical / approve paths)
# ----------------------------------------------------------------

def uniformity_findings_for(entry: dict, layout) -> list:
    """Uniformity findings for ONE entry. layout is the
    (entries_dir, archive_dir) pair (unused except for shape
    parity with project validation)."""
    findings = []
    eid = entry["id"]
    if entry.get("state_schema") is not None:
        problem = check_state_schema(entry["state_schema"])
        if problem:
            findings.append(_finding(
                "uniformity", eid,
                f"state schema not well-formed: {problem}"))
    if entry.get("source_kind") != "entry-dir":
        return findings
    entry_dir = Path(entry["entry_dir"]) \
        if entry.get("entry_dir") else None
    if entry_dir is None or not entry_dir.is_dir():
        findings.append(_finding(
            "uniformity", eid, "entry dir missing"))
        return findings
    main_file = entry.get("main_file")
    if main_file:
        main = entry_dir / main_file
        if not main.is_file():
            findings.append(_finding(
                "uniformity", eid,
                f"main file missing: {main_file}"))
        elif main.suffix.lower() in (".html", ".htm"):
            text = main.read_text(encoding="utf-8",
                                  errors="replace")
            findings.extend(_html_discipline(eid, text))
    for path in sorted(entry_dir.rglob("*")):
        if path.is_file() and _VARIANT_SUFFIX.search(path.name):
            findings.append(_finding(
                "uniformity", eid,
                f"variant-suffix file (variants belong in "
                f"state, not files): "
                f"{path.relative_to(entry_dir)}"))
    return findings


def _html_discipline(entry_id, text: str) -> list:
    """The mechanically checkable slice of the mockup
    uniformity discipline for HTML mocks: hardcoded hex colors
    outside a token-definition block are a finding (tokens are
    defined in one :root{...} block or a <style data-tokens>
    block; everything else must reference tokens). Prose and
    taste remain human review — not everything is a regex."""
    findings = []
    token_spans = []
    for m in re.finditer(r":root\s*\{[^}]*\}", text, re.S):
        token_spans.append((m.start(), m.end()))
    for m in re.finditer(
            r"<style[^>]*data-tokens[^>]*>.*?</style>",
            text, re.S):
        token_spans.append((m.start(), m.end()))

    def in_tokens(pos):
        return any(a <= pos < b for a, b in token_spans)

    for m in _HEX_COLOR.finditer(text):
        if not in_tokens(m.start()):
            findings.append(_finding(
                "uniformity", entry_id,
                f"hardcoded color {m.group(0)} outside the "
                f"token block — use the shared tokens"))
            break  # one finding per entry is enough to refuse
    return findings


# ----------------------------------------------------------------
# Project-wide validators
# ----------------------------------------------------------------

def v_status_vocabulary(ctx):
    out = []
    for e in ctx["entries"]:
        if e["status"] not in reg.STATUSES:
            out.append(_finding(
                "status-in-vocabulary", e["id"],
                f"status {e['status']!r} not in the vocabulary"))
        if e["kind"] not in reg.KINDS:
            out.append(_finding(
                "status-in-vocabulary", e["id"],
                f"kind {e['kind']!r} not in the vocabulary"))
    return out


def v_supersedes(ctx):
    out = []
    by_id = {e["id"]: e for e in ctx["entries"]}
    for e in ctx["entries"]:
        target = e.get("superseded_by")
        if not target:
            continue
        if target not in by_id:
            out.append(_finding(
                "supersedes-resolve", e["id"],
                f"superseded_by {target!r} does not resolve"))
            continue
        # acyclic: walk the chain with a visited set
        seen = {e["id"]}
        cur = target
        while cur:
            if cur in seen:
                out.append(_finding(
                    "supersedes-resolve", e["id"],
                    f"supersedes chain is cyclic at {cur!r}"))
                break
            seen.add(cur)
            cur = by_id.get(cur, {}).get("superseded_by")
    return out


def v_archived_folder(ctx):
    out = []
    entries_dir, archive_dir = ctx["layout"]
    for e in ctx["entries"]:
        if e["source_kind"] != "entry-dir" or not e["entry_dir"]:
            continue
        p = Path(e["entry_dir"])
        in_archive = _is_under(p, archive_dir)
        if e["archived"] and not in_archive:
            out.append(_finding(
                "archived-folder-agreement", e["id"],
                "archived=1 but the folder is not under the "
                "archive dir (repair: wb archive --resume)"))
        if not e["archived"] and in_archive:
            out.append(_finding(
                "archived-folder-agreement", e["id"],
                "folder is under the archive dir but "
                "archived=0"))
        if not p.is_dir():
            out.append(_finding(
                "archived-folder-agreement", e["id"],
                f"entry dir missing on disk: {p}"))
    return out


def v_fingerprints(ctx):
    out = []
    for e in ctx["entries"]:
        if e["source_kind"] != "entry-dir" \
                or not e["entry_dir"] or not e["main_file"] \
                or not e["content_sha256"]:
            continue
        main = Path(e["entry_dir"]) / e["main_file"]
        if main.is_file() and sha256_file(main) != e["content_sha256"]:
            out.append(_finding(
                "fingerprint-match", e["id"],
                "content drifted: the main file's hash differs "
                "from the recorded fingerprint (wb verify "
                "accepts or reports it)"))
    return out


def v_dirs_have_rows(ctx):
    out = []
    entries_dir, archive_dir = ctx["layout"]
    known = {e["entry_dir"] for e in ctx["entries"]
             if e["entry_dir"]}
    candidates = []
    if entries_dir.is_dir():
        candidates += [d for d in entries_dir.iterdir()
                         if d.is_dir()]
    if archive_dir.is_dir():
        for year in archive_dir.iterdir():
            if year.is_dir():
                candidates += [d for d in year.iterdir()
                                 if d.is_dir()]
    for d in candidates:
        if str(d) not in known:
            out.append(_finding(
                "entry-dirs-have-rows", d.name,
                f"folder with no registry row: {d}"))
    return out


def v_uniformity(ctx):
    out = []
    for e in ctx["entries"]:
        if not e["archived"]:
            out.extend(uniformity_findings_for(e, ctx["layout"]))
    return out


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


ALL_VALIDATORS = (
    ("status-in-vocabulary", v_status_vocabulary),
    ("supersedes-resolve", v_supersedes),
    ("archived-folder-agreement", v_archived_folder),
    ("fingerprint-match", v_fingerprints),
    ("entry-dirs-have-rows", v_dirs_have_rows),
    ("uniformity", v_uniformity),
)


def validate_project(db_path, layout) -> list:
    """Run the whole registry against one project's DB.
    Returns a flat list of findings ([] = clean)."""
    entries = reg.list_entries(db_path, archived=None)
    ctx = {"entries": entries, "layout": layout,
           "db_path": db_path}
    findings = []
    for _name, fn in ALL_VALIDATORS:
        findings.extend(fn(ctx))
    return findings


def reconcile(db_path, layout) -> dict:
    """Serve-time reconciliation (viewer banners): folders
    with no row, rows whose folder is gone. Guarded: a scan
    that fails reports status 'unknown', never mass-flags
    (the git viewer's prune-guard lesson)."""
    try:
        findings = validate_project(db_path, layout)
    except Exception as e:
        return {"status": "unknown", "problems": [],
                "error": str(e)[:200]}
    structural = [f for f in findings
                  if f["validator"] in
                  ("archived-folder-agreement",
                   "entry-dirs-have-rows")]
    return {"status": "problems" if structural else "ok",
            "problems": structural, "error": None}
