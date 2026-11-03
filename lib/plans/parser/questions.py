"""Resolvable questions: the wb-question sentinel grammar.

One slice of lib/plans/parser (see the package
docstring): sentinel field validation against the plan
syntax standard and the extraction of sentinel-bearing
question items from an open-questions section — a valid
question renders exactly once (in the Questions card);
a broken one degrades to plain rendering plus a
sentinel_errors entry.
"""

from .grammar import (_BULLET_RE, _FENCE_RE,
                      _NUMBERED_ITEM_RE, _QUESTION_FIELDS,
                      _QUESTION_ID_RE, _QUESTION_TYPES,
                      _SENTINEL_CLOSE, _SENTINEL_OPEN,
                      _TASK_ITEM_RE)

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
