"""Plan grammar: the house-format tokens and status words.

One slice of lib/plans/parser (see the package
docstring): every regex the parser matches with, the
status word lists, the wb-question sentinel constants,
and the two status derivations (declared status, board
bucket) that the rest of the harness shares.
"""

import re

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


_SENTINEL_OPEN = "<!-- wb-question"
_SENTINEL_CLOSE = "-->"
_QUESTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_QUESTION_TYPES = ("choice", "toggle", "text")
_QUESTION_FIELDS = {"id", "type", "options", "labels",
                    "recommended", "answer"}
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)[.)]\s+(.*)$")
