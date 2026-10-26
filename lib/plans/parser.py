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
  - Resolvable questions (plan syntax standard): an item in
    an open-questions section may carry a `wb-question`
    sentinel comment with its structured form; well-formed
    sentinels join the payload as `questions` records and
    malformed ones are reported in `sentinel_errors` — the
    question itself still renders as plain markdown, and
    sentinel lines never fold into an item's text.
"""

import hashlib
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


def _is_questions_heading(heading: str) -> bool:
    """The one questions-section rule (plan syntax
    standard): the normalized heading — the partition
    already trimmed it; casefolded here — starts with
    "open questions", so "Open questions for the owner"
    is the questions section and "Plan open questions"
    is not. The section flag and both extractions (sentinel
    questions, task-list open questions) hang off this
    predicate and no other."""
    return heading.casefold().startswith("open questions")


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
    in_sentinel = False
    for line in _unfenced(body_lines):
        if line.strip() == _SENTINEL_OPEN:
            in_sentinel = True
            continue
        if in_sentinel:
            if line.strip() == _SENTINEL_CLOSE:
                in_sentinel = False
            continue
        m = _TASK_ITEM_RE.match(line)
        if m:
            current = {"text": m.group(2).strip(),
                       "checked": m.group(1).lower() == "x"}
            items.append(current)
        elif current is not None and line.strip():
            current["text"] += "\n" + line.strip()
    return items


_SENTINEL_OPEN = "<!-- wb-question"
_SENTINEL_CLOSE = "-->"
_QUESTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_QUESTION_TYPES = ("choice", "toggle", "text")
_QUESTION_FIELDS = {"id", "type", "options", "labels",
                    "recommended", "answer"}
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)[.)]\s+(.*)$")


def _split_values(raw: str) -> list:
    return [v.strip() for v in raw.split("|")]


def _validate_sentinel(fields: dict, *, item, seen_ids: set,
                       sentinel_line: int):
    """Validate one sentinel's field map against the
    grammar (plan syntax standard, Resolvable questions).
    Returns (record | None, errors): every broken rule is
    an error, and any error means no record — the question
    degrades to plain rendering. `fields` maps key → value
    with duplicates already collapsed to a marker error by
    the caller via the `_dupes` key."""
    errors = []

    def err(reason):
        errors.append({"line": sentinel_line,
                       "id": fields.get("id"),
                       "reason": reason})

    for key in fields.get("_dupes", []):
        err(f"duplicate field: {key}")
    for key in fields:
        if not key.startswith("_") \
                and key not in _QUESTION_FIELDS:
            err(f"unknown field: {key}")
    qid = fields.get("id")
    if qid is None:
        err("missing field: id")
    elif not _QUESTION_ID_RE.match(qid):
        err(f"id is not a slug: {qid!r}")
    elif qid in seen_ids:
        err(f"duplicate question id: {qid}")
    qtype = fields.get("type")
    if qtype is None:
        err("missing field: type")
    elif qtype not in _QUESTION_TYPES:
        err(f"unknown question type: {qtype!r}")
    if "answer" not in fields:
        err("missing field: answer")
    answer = fields.get("answer", "")
    options = labels = None
    recommended = fields.get("recommended")
    if qtype == "choice":
        if "options" not in fields:
            err("choice question has no options field")
        else:
            options = _split_values(fields["options"])
            if len(options) < 2:
                err("choice needs at least two options")
            if any(not v for v in options):
                err("options must not contain empty values")
            if len(set(options)) != len(options):
                err("options must not repeat a value")
        if "labels" in fields:
            err("labels is only valid for toggle questions")
        if recommended is not None and options is not None \
                and recommended not in options:
            err("recommended is not one of the options")
        if answer and options is not None \
                and answer not in options:
            err("answer is not one of the options")
    elif qtype == "toggle":
        if "labels" not in fields:
            err("toggle question has no labels field")
        else:
            labels = _split_values(fields["labels"])
            if len(labels) != 2:
                err("toggle needs exactly two labels")
            if any(not v for v in labels):
                err("labels must not be empty")
        if "options" in fields:
            err("options is only valid for choice questions")
        if recommended is not None and labels is not None \
                and recommended not in labels:
            err("recommended is not one of the labels")
        if answer and labels is not None \
                and answer not in labels:
            err("answer is not one of the labels")
    elif qtype == "text":
        for key in ("options", "labels", "recommended"):
            if key in fields:
                err(f"{key} is not valid for text questions")
    if item["kind"] == "task":
        if item["checked"] != bool(answer):
            err("checkbox and answer disagree: a checked "
                "item needs a recorded answer, an answered "
                "item must be checked")
    if errors:
        return None, errors
    seen_ids.add(qid)
    record = {
        "id": qid,
        "type": qtype,
        "text": item["text"],
        "detail": "\n".join(item["detail"]),
        "options": options,
        "labels": labels,
        "recommended": recommended,
        "answer": answer,
        "checked": item["checked"] if item["kind"] == "task"
                   else bool(answer),
        "item_kind": item["kind"],
        "line": item["line"],
        "sentinel_line": sentinel_line,
        "answer_line": fields["_answer_line"],
    }
    return record, []


def _extract_questions(body_lines, line_offset: int,
                       seen_ids: set):
    """Sentinel-bearing questions of one open-questions
    section (plan syntax standard, Resolvable questions).
    An item is a task-list item in the canonical form;
    numbered and plain-bullet items are the tolerated
    legacy attachment. Items sit at the section's first
    item's indentation — deeper list lines are the item's
    own continuation and fold into its detail. Fenced
    regions are examples: no items, no sentinels. A
    sentinel validates the moment it closes; a valid one
    appends its question record, a broken one appends
    sentinel_errors and the question stays plain.
    Returns (questions, sentinel_errors, covered):
    covered is the set of absolute line numbers a valid
    question item consumed — its first line, the detail
    lines folded in before its sentinel, and the
    sentinel's own lines. The caller renders everything
    else in the section as leftover markdown, so a valid
    question renders exactly once (in the Questions
    card) and nothing else is dropped."""
    questions = []
    errors = []
    covered = set()
    current = None
    item_indent = None
    in_fence = False
    i = 0
    while i < len(body_lines):
        line = body_lines[i]
        abs_line = line_offset + i
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        if line.strip() == _SENTINEL_OPEN:
            start = abs_line
            raw_fields = []
            j = i + 1
            closed = False
            while j < len(body_lines):
                inner = body_lines[j]
                if _FENCE_RE.match(inner):
                    break
                if inner.strip() == _SENTINEL_CLOSE:
                    closed = True
                    break
                raw_fields.append(inner)
                j += 1
            sentinel_lines = [line_offset + k
                              for k in range(i, j + 1)] \
                if closed else []
            if current is None:
                errors.append({
                    "line": start, "id": None,
                    "reason": "stray sentinel: no question "
                              "item above it in the section"})
            elif current["sentinel"] is not None:
                errors.append({
                    "line": start,
                    "id": current["sentinel"].get("id"),
                    "reason": "second sentinel on one "
                              "question item"})
            elif not closed:
                errors.append({
                    "line": start, "id": None,
                    "reason": "unterminated sentinel: no "
                              "closing --> line"})
            else:
                fields = {}
                dupes = []
                malformed = None
                for k, raw in enumerate(raw_fields):
                    if not raw.strip():
                        malformed = "blank line inside the " \
                                    "sentinel"
                        break
                    if "=" not in raw:
                        malformed = f"sentinel line is not " \
                                    f"key=value: {raw.strip()!r}"
                        break
                    key, _, value = raw.partition("=")
                    key = key.strip()
                    if key in fields:
                        dupes.append(key)
                    fields[key] = value.strip()
                    if key == "answer":
                        fields["_answer_line"] = \
                            line_offset + i + 1 + k
                if malformed is not None:
                    errors.append({"line": start, "id": None,
                                   "reason": malformed})
                else:
                    if dupes:
                        fields["_dupes"] = dupes
                    current["sentinel"] = fields
                    record, errs = _validate_sentinel(
                        fields, item=current,
                        seen_ids=seen_ids,
                        sentinel_line=start)
                    errors.extend(errs)
                    if record is not None:
                        questions.append(record)
                        covered.update(current["lines"])
                        covered.update(sentinel_lines)
            i = j + 1 if closed else len(body_lines)
            continue
        indent = len(line) - len(line.lstrip())
        task = _TASK_ITEM_RE.match(line)
        numbered = _NUMBERED_ITEM_RE.match(line) \
            if not task else None
        bullet = _BULLET_RE.match(line) \
            if not task and not numbered else None
        is_item = (task or numbered or bullet) is not None \
            and (item_indent is None or indent == item_indent)
        if is_item:
            if item_indent is None:
                item_indent = indent
            if task:
                kind = "task"
                text = task.group(2).strip()
                checked = task.group(1).lower() == "x"
            elif numbered:
                kind = "numbered"
                text = numbered.group(2).strip()
                checked = False
            else:
                kind = "bullet"
                text = bullet.group(1).strip()
                checked = False
            current = {"kind": kind, "text": text,
                       "checked": checked, "detail": [],
                       "line": abs_line, "sentinel": None,
                       "lines": [abs_line]}
            i += 1
            continue
        if current is not None and line.strip():
            current["detail"].append(line.strip())
            current["lines"].append(abs_line)
        i += 1
    return questions, errors, covered


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
    questions = []
    sentinel_errors = []
    seen_question_ids = set()
    questions_section_seen = False
    subplans = []
    critical_files = []
    out_sections = []
    section_offset = len(header_lines)
    for sec in sections:
        body_lines = sec["lines"][1:]
        body_offset = section_offset + 1
        section_offset += len(sec["lines"])
        sec_steps = []
        if _is_steps_heading(sec["heading"]) or any(
                _STEPS_INTRO_RE.match(ln.strip())
                for ln in body_lines):
            sec_steps = _extract_steps(body_lines)
            steps.extend(sec_steps)
        # One questions section per plan: the first
        # section matching the one heading rule is flagged
        # and extracted from; a later match is ordinary.
        is_open_questions = False
        if not questions_section_seen \
                and _is_questions_heading(sec["heading"]):
            is_open_questions = True
            questions_section_seen = True
        is_subplans = sec["heading"].lower() == "subplans"
        is_critical_files = \
            sec["heading"].lower() == "critical files"
        sec_leftover_blocks = None
        if is_open_questions:
            open_questions.extend(
                _extract_open_questions(body_lines))
            sec_questions, sec_errors, sec_covered = \
                _extract_questions(
                    body_lines, body_offset, seen_question_ids)
            questions.extend(sec_questions)
            sentinel_errors.extend(sec_errors)
            leftover_lines = [
                ln for idx, ln in enumerate(body_lines)
                if body_offset + idx not in sec_covered]
            sec_leftover_blocks = _split_fences(
                leftover_lines)
        if is_subplans:
            subplans.extend(
                _extract_subplans(body_lines))
        if is_critical_files:
            critical_files.extend(
                _extract_critical_files(body_lines))
        out_section = {
            "heading": sec["heading"],
            "level": sec["level"],
            "raw": "\n".join(sec["lines"]),
            "blocks": _split_fences(body_lines),
            "is_rulings": sec["heading"].lower() == "rulings",
            "is_steps": bool(sec_steps),
            "is_open_questions": is_open_questions,
            "is_subplans": is_subplans,
            "is_critical_files": is_critical_files,
        }
        if sec_leftover_blocks is not None:
            # The reader renders these in place of `blocks`
            # when the Questions card shows, so a valid
            # question renders once and nothing else in
            # the section is dropped.
            out_section["leftover_blocks"] = \
                sec_leftover_blocks
        out_sections.append(out_section)
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
        "questions": questions,
        "sentinel_errors": sentinel_errors,
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
        "questions": doc["questions"],
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
    raw = target.read_bytes()
    doc = parse_plan(raw.decode("utf-8"), path=rel)
    archived = rel.startswith("finished/")
    doc["status_bucket"] = status_bucket(doc["status_raw"],
                                         archived=archived)
    doc["archived"] = archived
    doc["file_sha256"] = hashlib.sha256(raw).hexdigest()
    return doc


def apply_answers(text: str, answers: dict) -> str:
    """Compose a resolution into plan source: for each
    {question id: answer}, fill the sentinel's `answer`
    field and — for a task-list item — check its box.
    Every other byte is preserved: the edit replaces whole
    lines located by a fresh parse of the given text, and
    split/join on "\\n" is the identity. Raises ValueError
    naming the problem (unknown id, an answer the
    question's type refuses, an empty answer) and changes
    nothing — the caller writes only on success."""
    if not isinstance(answers, dict) or not answers:
        raise ValueError("answers must be a non-empty map "
                         "of question id to answer")
    doc = parse_plan(text)
    by_id = {q["id"]: q for q in doc["questions"]}
    lines = text.split("\n")
    edits = {}
    for qid, answer in answers.items():
        q = by_id.get(qid)
        if q is None:
            raise ValueError(f"unknown question id: {qid!r}")
        if not isinstance(answer, str) \
                or not answer.strip():
            raise ValueError(
                f"answer for {qid} must be non-empty text")
        if "\n" in answer:
            raise ValueError(
                f"answer for {qid} must be a single line")
        answer = answer.strip()
        if q["type"] == "choice" \
                and answer not in q["options"]:
            raise ValueError(
                f"answer for {qid} must be one of its "
                f"options, got {answer!r}")
        if q["type"] == "toggle" \
                and answer not in q["labels"]:
            raise ValueError(
                f"answer for {qid} must be one of its "
                f"labels, got {answer!r}")
        aline = q["answer_line"]
        raw = lines[aline]
        indent = raw[:len(raw) - len(raw.lstrip())]
        edits[aline] = f"{indent}answer={answer}"
        if q["item_kind"] == "task":
            iline = q["line"]
            item_line = lines[iline]
            m = re.match(r"^(\s*- \[)([ xX])(\])", item_line)
            if m is None:
                raise ValueError(
                    f"question {qid}: its item line no "
                    f"longer parses as a task item")
            edits[iline] = item_line[:m.start(2)] + "x" \
                + item_line[m.end(2):]
    for idx, new_line in edits.items():
        lines[idx] = new_line
    return "\n".join(lines)
