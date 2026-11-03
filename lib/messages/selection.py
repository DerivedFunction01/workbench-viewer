"""Annotation selection validation (spec §12).

One slice of lib/messages (see the package docstring):
the selection-payload rules, enforced on the one create
path in lifecycle.py — quote + context is the anchor;
raw offsets are refused outright.
"""

from .constants import (CONTEXT_CAP, OFFSET_KEYS,
                        QUOTE_CAP, MessageError)

def _validate_selection(anchor_type, anchor_ref, selection,
                        parent_id):
    """The selection-payload rules (spec §12 + the
    annotation plan's anchor design), enforced on the one
    create path:

      - required iff anchor_type is text/component,
        forbidden otherwise (and on replies — the thread
        root holds the anchor; replies inherit it for
        display);
      - kind must match the anchor type;
      - text: component_id + quote (<= QUOTE_CAP) required,
        prefix/suffix <= CONTEXT_CAP;
      - component: component_id required (the manifest id,
        verbatim);
      - any offset-shaped key is refused outright: quote
        + context is the anchor, raw offsets are too
        fragile across edits.
    Returns the payload to store (or None)."""
    if anchor_type not in ("text", "component"):
        if selection is not None:
            raise MessageError(
                "selection payload requires anchor_type "
                "'text' or 'component' (got "
                f"{anchor_type!r})")
        return None
    if parent_id is not None:
        raise MessageError(
            "replies carry no selection payload — the "
            "thread root holds the anchor")
    if not anchor_ref:
        raise MessageError(
            f"anchor_type {anchor_type!r} requires "
            "anchor_ref (the plan path for text, the entry "
            "id for component)")
    if selection is None:
        raise MessageError(
            f"annotation (anchor_type {anchor_type!r}) "
            "requires a selection payload")
    if not isinstance(selection, dict):
        raise MessageError("selection must be an object")
    bad = sorted(OFFSET_KEYS & selection.keys())
    if bad:
        raise MessageError(
            f"selection must not carry raw offsets "
            f"(key {bad[0]!r}): quote + context is the "
            "anchor (spec §12)")
    kind = selection.get("kind")
    if kind != anchor_type:
        raise MessageError(
            f"selection kind {kind!r} does not match "
            f"anchor_type {anchor_type!r}")
    component_id = selection.get("component_id")
    if not isinstance(component_id, str) \
            or not component_id.strip():
        raise MessageError(
            "selection requires a component_id (the "
            "enclosing component's data-anchor id)")
    label = selection.get("component_label")
    if label is not None and not isinstance(label, str):
        raise MessageError(
            "selection component_label must be a string")
    if anchor_type == "text":
        quote = selection.get("quote")
        if not isinstance(quote, str) or not quote:
            raise MessageError(
                "text selection requires a quote (the "
                "selected text, verbatim)")
        if len(quote) > QUOTE_CAP:
            raise MessageError(
                f"selection quote is {len(quote)} chars; "
                f"the cap is {QUOTE_CAP} — select a "
                "shorter passage")
        for key in ("prefix", "suffix"):
            value = selection.get(key)
            if value is not None:
                if not isinstance(value, str):
                    raise MessageError(
                        f"selection {key} must be a string")
                if len(value) > CONTEXT_CAP:
                    raise MessageError(
                        f"selection {key} is {len(value)} "
                        f"chars; the cap is {CONTEXT_CAP}")
        heading = selection.get("section_heading")
        if heading is not None \
                and not isinstance(heading, str):
            raise MessageError(
                "selection section_heading must be a "
                "string")
    else:
        entry_id = selection.get("entry_id")
        if entry_id is not None \
                and not isinstance(entry_id, str):
            raise MessageError(
                "selection entry_id must be a string")
    return selection
