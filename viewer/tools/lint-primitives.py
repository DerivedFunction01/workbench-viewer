#!/usr/bin/env python3
"""lint-primitives.py — scanner rule 3 of the 2026-11-10
entries critic pass: no raw form primitives under the
ENTRIES section (viewer/client/src/sections/entries/).

Scope note, recorded plainly: the critic's rule text says
sections/**, but the finding (F4) names only the entries
surfaces — LifecycleCard and the Entries filter bar.
Other sections (plans, inbox, settings, repos, todos)
still carry pre-existing raw primitives of their own;
widening this lint to them is a separate migration, not
this pass. The lint therefore enforces the rule where
the finding lives and says so, rather than claiming a
sweep it does not perform.

A raw <select>, <input>, or <textarea> in an entries file
means a form control bypassed the kit (Fields'
Select/Input, SegmentedControl, Toggle) and with it the
appearance, sizing, and labelling contracts. Components
under components/ are the kit itself and are not scanned.

The allowlist is per file and each entry states its
reason; a new raw primitive in an allowlisted file still
fails unless the file's allowed set covers its tag.
  - FilePanel.tsx <textarea>: the guarded file editor —
    its content is the entry file itself, edited as a
    document, not a form field; it carries the peek/save
    sha contract and its own aria-label.
  - Annotations.tsx <textarea>: the composer and reply
    boxes — free-form message bodies anchored to a text
    selection, styled by the annotation surface's own
    fieldStyle; message composition is not a form field.
    (The two remaining Annotations textareas are the
    composer body and the reply body.)

Run from anywhere: python3 viewer/tools/lint-primitives.py
Exit 1 on any violation. Wired into tools/check.sh.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = ROOT / "viewer" / "client" / "src" / "sections" / "entries"
TAGS = ("select", "input", "textarea")

ALLOWLIST = {
    "FilePanel.tsx": {"textarea"},
    "Annotations.tsx": {"textarea"},
}

failures = 0
for path in sorted(SECTIONS.rglob("*.tsx")):
    rel = str(path.relative_to(SECTIONS))
    text = path.read_text(encoding="utf-8")
    allowed = ALLOWLIST.get(rel, set())
    for match in re.finditer(r"<(select|input|textarea)[\s/>]", text):
        tag = match.group(1)
        if tag in allowed:
            continue
        line = text.count("\n", 0, match.start()) + 1
        failures += 1
        print(
            f"FAIL {rel}:{line} raw <{tag}> — sections render kit fields "
            "(Fields Select/Input, SegmentedControl, Toggle); a raw "
            "primitive needs an allowlist entry with its reason in "
            "lint-primitives.py"
        )
print(f"lint-primitives: {failures} violation(s)")
sys.exit(1 if failures else 0)
