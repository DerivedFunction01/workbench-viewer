#!/usr/bin/env python3
"""check-viewport.py — scanner rule 5 of the 2026-11-10
entries critic pass: the client document never disables
user scaling.

F8 was `user-scalable=no` in the viewport meta — axe's
meta-viewport rule fired on every route. The check is a
source read of viewer/client/index.html: a viewport meta
carrying user-scalable=no, or a maximum-scale below 2,
fails. (maximum-scale=1 also disables zoom on some
browsers and is treated the same way.)

Run from anywhere: python3 viewer/tools/check-viewport.py
Exit 1 on violation. Wired into tools/check.sh.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "viewer" / "client" / "index.html"


def main() -> int:
    text = HTML.read_text(encoding="utf-8")
    match = re.search(r'name="viewport"\s+content="([^"]+)"', text)
    if not match:
        print("FAIL no viewport meta found in viewer/client/index.html")
        return 1
    content = match.group(1)
    failures = 0
    if "user-scalable=no" in content.replace(" ", ""):
        failures += 1
        print("FAIL viewport meta disables user scaling (user-scalable=no)")
    scale = re.search(r"maximum-scale=([0-9.]+)", content)
    if scale and float(scale.group(1)) < 2:
        failures += 1
        print(f"FAIL viewport maximum-scale {scale.group(1)} caps zoom below 2x")
    print(f"check-viewport: viewport '{content}' — {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
