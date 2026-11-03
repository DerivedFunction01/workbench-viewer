"""Plan parsing: the document builder and file access.

One slice of lib/plans/parser (see the package
docstring): parse_plan (the partition of source lines
into header + sections with every structured view
derived from it), the losslessness reconstruction, and
the file-level access — list/load — plus apply_answers,
the sentinel-answer composition.
"""

import hashlib
import re
from pathlib import Path

from .document import (_extract_critical_files,
                       _extract_open_questions,
                       _extract_steps, _extract_subplans,
                       _is_questions_heading,
                       _is_steps_heading, _parse_fields,
                       _split_fences)
from .grammar import _HEADING_RE, _STEPS_INTRO_RE, \
    status_bucket
from .questions import _extract_questions

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
