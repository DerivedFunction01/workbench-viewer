"""The house plan parser: plan markdown → structured document.

Design rule (founding plan): the parser NEVER drops content.
The document is built by partitioning the source lines into a
header block and sections — every line lands in exactly one
of them, in order — and the structured views (fields, steps,
blocks) are derived from that partition. A plan that does not
match the house format is flagged `conforming: False` and
still returns its whole text (the viewer renders it as
formatted markdown); nothing is silently structured away.

House format (from the real corpus — the founding plan, v2's
subplans, the 2026-10-23 PowerBI plans, the 2026-10-22
bootstrap plan):
  - `# Title`, then header fields `Key: value` (values wrap),
    notably Status / Created / Parent.
  - `## Rulings`, `## Steps`, ... sections. The plan syntax
    standard's semantic sections are read structurally:
    `## Open questions` task-list items (with checked state),
    the `## Subplans` declared-path list, and the
    `## Critical files` path list join the payload;
    their absence is empty, never an error.
  - Steps, two shapes: `N. **Title.**` items with `files:` /
    `verify:` / `done when:` labels, or `### Step N — Title`
    headings — both under a steps-ish heading (`## Steps`,
    `## Implementation steps`) or after a bare `Steps:` line.
Numbered lists elsewhere (goals, open questions) are NOT
steps: steps are only read inside a steps region.
"""

import re
from pathlib import Path

_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 /_-]{0,38}):\s+(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_STEP_ITEM_RE = re.compile(r"^(\d+)[.)]\s+(.*)$")
_STEP_HEAD_RE = re.compile(r"^###\s+Step\s+(\d+)\s*[—–-]\s*(.*)$")
_LABEL_RE = re.compile(
    r"^\s*(files|verify|done when)\s*:\s?(.*)$", re.IGNORECASE)
_STEPS_INTRO_RE = re.compile(r"^Steps( \([^)]*\))?:\s*$")
_FENCE_RE = re.compile(r"^```(\w*)\s*$")
_TASK_ITEM_RE = re.compile(r"^\s*- \[( |x|X)\]\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*-\s+(.*)$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")

DONE_WORDS = ("superseded", "complete", "completed", "done",
              "finished", "implemented")
DOING_WORDS = ("in progress", "in_progress")


def declared_status(status_raw):
    """The status a plan DECLARES: the leading status word
    of its Status header, normalized — "complete" for
    "complete (closed ...)", "in progress" for the
    two-word form, markdown emphasis stripped. None when
    the plan carries no Status header: it declares
    nothing, and callers (the closeout check) draw no
    conclusion from silence. A header leading with no
    standard word yields that leading word, so a caller
    can name what was declared."""
    if status_raw is None:
        return None
    s = status_raw.strip().lower().strip("*").strip()
    if not s:
        return None
    if s.startswith("in progress") \
            or s.startswith("in_progress"):
        return "in progress"
    word = re.split(r"[\s(]", s, maxsplit=1)[0].strip("*_")
    if word == "completed":
        return "complete"
    return word or None


def status_bucket(status_raw, *, archived=False) -> str:
    """Board placement for a plan: todo | doing | done, from
    its header Status text (the plan files carry no per-step
    state and the board does not invent any)."""
    if archived:
        return "done"
    s = (status_raw or "").lower()
    if any(w in s for w in DONE_WORDS):
        return "done"
    if any(w in s for w in DOING_WORDS):
        return "doing"
    return "todo"


def _split_fences(lines):
    """Split a section's lines into blocks. Fenced code is its
    own block; a mermaid fence is a diagram block (source
    without the fence markers, raw with them). Everything
    else accumulates into markdown blocks. Lossless: block
    raws joined reproduce the input lines."""
    blocks = []
    buf = []

    def flush():
        if buf:
            blocks.append({"type": "markdown",
                           "text": "\n".join(buf),
                           "raw": "\n".join(buf)})
            buf.clear()

    i = 0
    while i < len(lines):
        m = _FENCE_RE.match(lines[i])
        if m:
            flush()
            lang = m.group(1) or ""
            raw_lines = [lines[i]]
            src_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                raw_lines.append(lines[i])
                src_lines.append(lines[i])
                i += 1
            if i < len(lines):
                raw_lines.append(lines[i])
                i += 1
            if lang == "mermaid":
                blocks.append({"type": "mermaid",
                               "source": "\n".join(src_lines),
                               "raw": "\n".join(raw_lines)})
            else:
                blocks.append({"type": "code", "lang": lang,
                               "text": "\n".join(src_lines),
                               "raw": "\n".join(raw_lines)})
            continue
        buf.append(lines[i])
        i += 1
    flush()
    return blocks


def _parse_fields(header_lines):
    fields = {}
    current = None
    for line in header_lines:
        m = _FIELD_RE.match(line)
        if m and not line.startswith((" ", "\t")):
            current = m.group(1).strip()
            fields[current] = m.group(2)
        elif current is not None and line.strip():
            fields[current] += "\n" + line.strip()
    return fields


def _clean_step_title(text: str) -> str:
    t = text.strip()
    if t.startswith("**") and "**" in t[2:]:
        t = t[2:t.index("**", 2)].strip()
    return t


def _step_from_lines(n, title, lines):
    step = {"n": n, "title": title, "body": "",
            "files": "", "verify": "", "done_when": "",
            "raw": "\n".join(lines)}
    buckets = {"body": []}
    current = "body"
    for line in lines:
        m = _LABEL_RE.match(line)
        if m:
            label = m.group(1).lower()
            current = {"files": "files", "verify": "verify",
                       "done when": "done_when"}[label]
            buckets[current] = [m.group(2)]
        else:
            buckets.setdefault(current, []).append(line)
    for key in ("body", "files", "verify", "done_when"):
        step[key] = "\n".join(buckets.get(key, [])).strip()
    return step


def _extract_steps(section_lines):
    """Steps inside one section's lines, or [] if the section
    is not a steps region. A region starts at a bare `Steps:`
    line; the section's own heading was already checked by
    the caller for the heading-shaped variant."""
    lines = section_lines
    start = None
    for i, line in enumerate(lines):
        if _STEPS_INTRO_RE.match(line.strip()):
            start = i + 1
            break
    if start is None:
        start = 0
    region = lines[start:]
    steps = []
    # Shape (b): ### Step N — Title headings
    head_idx = [i for i, ln in enumerate(region)
                if _STEP_HEAD_RE.match(ln)]
    if head_idx:
        for k, i in enumerate(head_idx):
            m = _STEP_HEAD_RE.match(region[i])
            end = head_idx[k + 1] if k + 1 < len(head_idx) \
                else len(region)
            body = region[i + 1:end]
            steps.append(_step_from_lines(
                int(m.group(1)), m.group(2).strip(),
                [region[i], *body]))
        return steps
    # Shape (a): N. **Title** items. The bold title is the
    # house marker — a plain numbered line inside a steps
    # region is body text of the step above it, not a step.
    item_idx = [i for i, ln in enumerate(region)
                if _STEP_ITEM_RE.match(ln) and "**" in ln]
    if not item_idx:
        return []
    for k, i in enumerate(item_idx):
        m = _STEP_ITEM_RE.match(region[i])
        end = item_idx[k + 1] if k + 1 < len(item_idx) \
            else len(region)
        chunk = region[i:end]
        title_line = m.group(2)
        step = _step_from_lines(int(m.group(1)),
                                _clean_step_title(title_line),
                                chunk)
        # the title line's remainder after the bold title is
        # body text, already inside raw; keep body clean:
        steps.append(step)
    return steps


def _is_steps_heading(heading: str) -> bool:
    return bool(heading) and "step" in heading.lower()


def _unfenced(lines):
    """The lines outside fenced blocks: quoted examples in
    a section (a fenced sample task list, say) are not the
    section's own structure and must not be read as such."""
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line


def _extract_open_questions(body_lines):
    """Task-list items of an `## Open questions` section
    (plan syntax standard): one {text, checked} per item.
    Indented continuation lines — the recommendation rides
    on one — fold into the item's text; a section with no
    task items yields [], never an error."""
    items = []
    current = None
    for line in _unfenced(body_lines):
        m = _TASK_ITEM_RE.match(line)
        if m:
            current = {"text": m.group(2).strip(),
                       "checked": m.group(1).lower() == "x"}
            items.append(current)
        elif current is not None and line.strip():
            current["text"] += "\n" + line.strip()
    return items


def _extract_subplans(body_lines):
    """The declared list of a `## Subplans` section
    (repo-home spec §21): one `.plans/`-relative path per
    bullet, same discipline as Critical files — fence-aware,
    the backticked span when the bullet carries one, else
    the text up to the em-dash note. Declaration order is
    preserved; the parent declares, children declare
    nothing back.

    Precision rule: a span counts as a declaration only
    when it names a plan file — it ends in `.md`. A
    section can also be prose ABOUT the format (the plan
    syntax standard's own `## Subplans` section is exactly
    that: rules bullets carrying backticked spans like
    `.plans/` and `Parent:`), and prose declares nothing."""
    paths = []
    for line in _unfenced(body_lines):
        m = _BULLET_RE.match(line)
        if not m:
            continue
        item = m.group(1).strip()
        bt = _BACKTICK_RE.search(item)
        if bt:
            candidate = bt.group(1).strip()
        else:
            candidate = item.split(" — ")[0].strip()
        if candidate.endswith(".md"):
            paths.append(candidate)
    return paths


def _extract_critical_files(body_lines):
    """The path list of a `## Critical files` section: one
    path per bullet — the backticked span when the bullet
    carries one, else the text up to the em-dash note."""
    paths = []
    for line in _unfenced(body_lines):
        m = _BULLET_RE.match(line)
        if not m:
            continue
        item = m.group(1).strip()
        bt = _BACKTICK_RE.search(item)
        if bt:
            paths.append(bt.group(1).strip())
        else:
            path = item.split(" — ")[0].strip()
            if path:
                paths.append(path)
    return paths


def parse_plan(text: str, *, path: str = "") -> dict:
    lines = text.split("\n")
    # Partition: header (everything before the first section
    # heading) + sections. Every line lands exactly once, in
    # order. The title H1 belongs to the header when it is the
    # file's first non-blank line (the corpus shape); any
    # later level<=2 heading opens a section.
    first_content = next(
        (i for i, ln in enumerate(lines) if ln.strip()), None)
    header_lines = []
    sections = []
    current = None
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        is_title = i == first_content and line.startswith("# ")
        if m and len(m.group(1)) <= 2 and not is_title:
            current = {"heading": m.group(2).strip(),
                       "level": len(m.group(1)), "lines": [line]}
            sections.append(current)
            continue
        if current is None:
            header_lines.append(line)
        else:
            current["lines"].append(line)
    title = ""
    if first_content is not None \
            and lines[first_content].startswith("# "):
        title = lines[first_content][2:].strip()
    fields = _parse_fields(
        [ln for ln in header_lines
         if not ln.startswith("# ")])
    status_raw = None
    for key, value in fields.items():
        if key.lower() == "status":
            status_raw = value.strip()
            break
    steps = []
    open_questions = []
    subplans = []
    critical_files = []
    out_sections = []
    for sec in sections:
        body_lines = sec["lines"][1:]
        sec_steps = []
        if _is_steps_heading(sec["heading"]) or any(
                _STEPS_INTRO_RE.match(ln.strip())
                for ln in body_lines):
            sec_steps = _extract_steps(body_lines)
            steps.extend(sec_steps)
        is_open_questions = \
            sec["heading"].lower() == "open questions"
        is_subplans = sec["heading"].lower() == "subplans"
        is_critical_files = \
            sec["heading"].lower() == "critical files"
        if is_open_questions:
            open_questions.extend(
                _extract_open_questions(body_lines))
        if is_subplans:
            subplans.extend(
                _extract_subplans(body_lines))
        if is_critical_files:
            critical_files.extend(
                _extract_critical_files(body_lines))
        out_sections.append({
            "heading": sec["heading"],
            "level": sec["level"],
            "raw": "\n".join(sec["lines"]),
            "blocks": _split_fences(body_lines),
            "is_rulings": sec["heading"].lower() == "rulings",
            "is_steps": bool(sec_steps),
            "is_open_questions": is_open_questions,
            "is_subplans": is_subplans,
            "is_critical_files": is_critical_files,
        })
    conforming = status_raw is not None
    return {
        "path": path,
        "title": title,
        "fields": fields,
        "status_raw": status_raw,
        "status_bucket": status_bucket(status_raw),
        "conforming": conforming,
        "header_raw": "\n".join(header_lines),
        "sections": out_sections,
        "steps": steps,
        "step_count": len(steps),
        "open_questions": open_questions,
        "open_questions_count": len(open_questions),
        "subplans": subplans,
        "critical_files": critical_files,
        "mermaid_count": sum(
            1 for s in out_sections for b in s["blocks"]
            if b["type"] == "mermaid"),
        "markdown": text,
    }


def reconstruct(doc: dict) -> str:
    """header_raw + section raws, in order — the losslessness
    invariant: this must equal the source (modulo a trailing
    newline)."""
    parts = [doc["header_raw"]]
    parts.extend(s["raw"] for s in doc["sections"])
    return "\n".join(parts)


def _summary(doc: dict, rel: str, archived: bool,
             mtime: float) -> dict:
    return {
        "path": rel,
        "title": doc["title"],
        "status_raw": doc["status_raw"],
        "status_bucket": status_bucket(doc["status_raw"],
                                       archived=archived),
        "conforming": doc["conforming"],
        "step_count": doc["step_count"],
        "open_questions_count": doc["open_questions_count"],
        "subplans_count": len(doc["subplans"]),
        "mermaid_count": doc["mermaid_count"],
        "archived": archived,
        "modified": mtime,
    }


def list_plans(plans_dir) -> list:
    """Summaries for a project's plans dir: top-level *.md
    plus finished/*.md (archived). Other subdirectories are
    working files, not plans, and are not listed."""
    plans_dir = Path(plans_dir)
    out = []
    if not plans_dir.is_dir():
        return out
    for f in sorted(plans_dir.glob("*.md")):
        doc = parse_plan(f.read_text(encoding="utf-8"),
                         path=f.name)
        out.append(_summary(doc, f.name, False,
                            f.stat().st_mtime))
    finished = plans_dir / "finished"
    if finished.is_dir():
        for f in sorted(finished.glob("*.md")):
            doc = parse_plan(f.read_text(encoding="utf-8"),
                             path=f"finished/{f.name}")
            out.append(_summary(doc, f"finished/{f.name}",
                                True, f.stat().st_mtime))
    return out


def load_plan(plans_dir, rel: str) -> dict:
    """Parse one plan file, confined to the plans dir."""
    plans_dir = Path(plans_dir).resolve()
    target = (plans_dir / rel).resolve()
    if plans_dir not in target.parents or target.suffix != ".md":
        raise ValueError(f"plan path escapes the plans dir: "
                         f"{rel!r}")
    doc = parse_plan(target.read_text(encoding="utf-8"),
                     path=rel)
    archived = rel.startswith("finished/")
    doc["status_bucket"] = status_bucket(doc["status_raw"],
                                         archived=archived)
    doc["archived"] = archived
    return doc
