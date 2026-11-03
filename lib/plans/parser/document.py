"""Plan document model: blocks, fields, steps, sections.

One slice of lib/plans/parser (see the package
docstring): the lossless partition helpers — fenced-
block splitting, header-field parsing, step extraction
in both house shapes, the section predicates, and the
structural extractions (open questions, subplans,
critical files) that hang off them.
"""

from .grammar import (_BACKTICK_RE, _BULLET_RE,
                      _FIELD_RE, _FENCE_RE, _LABEL_RE,
                      _SENTINEL_CLOSE, _SENTINEL_OPEN,
                      _STEP_HEAD_RE, _STEP_ITEM_RE,
                      _STEPS_INTRO_RE, _TASK_ITEM_RE)

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
