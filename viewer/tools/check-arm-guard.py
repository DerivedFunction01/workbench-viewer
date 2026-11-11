#!/usr/bin/env python3
"""check-arm-guard.py — scanner rule 4 of the 2026-11-10
entries critic pass: every lifecycle commit in
LifecycleCard.tsx routes through the ArmConfirm guard.

The check is structural, not a grep for the component
name: it locates every `runAction(` call site and every
`verb:` literal in the file, finds the enclosing JSX
element for each by scanning backwards over tag balance,
and fails unless that element is <ArmConfirm> with the
call inside its onConfirm prop. A commit added outside
the guard — a bare Button onClick, a helper that fires a
verb — fails here even if every existing call is intact.

Run from anywhere: python3 viewer/tools/check-arm-guard.py
Exit 1 on any unguarded commit. Wired into tools/check.sh.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "viewer" / "client" / "src" / "sections" / "entries" / "LifecycleCard.tsx"


def enclosing_element(text: str, pos: int) -> str | None:
    """The JSX tag whose open element encloses pos, found by
    scanning backwards and balancing close tags."""
    depth = 0
    for match in reversed(list(re.finditer(r"</?([A-Z][A-Za-z]*)", text[:pos]))):
        tag = match.group(1)
        if match.group(0).startswith("</"):
            depth += 1
        elif depth == 0:
            return tag
        else:
            depth -= 1
    return None


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    failures = 0
    sites = [m.start() for m in re.finditer(r"runAction\(|verb:", text)]
    if not sites:
        print("FAIL no lifecycle commit sites found — the guard check has nothing to hold")
        return 1
    for pos in sites:
        element = enclosing_element(text, pos)
        line = text.count("\n", 0, pos) + 1
        if element != "ArmConfirm":
            failures += 1
            print(
                f"FAIL LifecycleCard.tsx:{line} lifecycle commit outside ArmConfirm "
                f"(enclosing element: {element or 'none'}) — commits route through "
                "the guard's onConfirm, never a bare control"
            )
        elif "onConfirm" not in text[max(0, pos - 4000):pos].split("<ArmConfirm")[-1]:
            failures += 1
            print(
                f"FAIL LifecycleCard.tsx:{line} commit inside ArmConfirm but not "
                "within its onConfirm prop"
            )
    print(f"check-arm-guard: {len(sites)} commit site(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
