#!/usr/bin/env python3
"""probe-axe.py — scanner rule 8 of the 2026-11-10 entries
critic pass, promoted to a standing probe under ruling
q5 (standing-leg): axe-core WCAG 2.2 AA over the Entries
routes.

Matrix: the entries list and the entry detail at 1440
light, 1440 dark, and 390 light. Any serious or critical
violation fails the probe. The drive pattern follows the
critic pass's preserved drive (axe-playwright-python over
the probe-served client: the built client beside the real
action modules and the real companion).

check.sh's offline legs cannot drive a browser, so the
standing leg is this probe set, run on the venue as part
of the gate flow for UI changes — see run-probes.sh.

Run on the venue with the probe stack up:
  PROBE_BASE=http://127.0.0.1:8900 python3 viewer/tools/probe-axe.py
Exit 1 on any serious/critical violation.
"""
import json
import os
import sys

sys.path.insert(0, os.environ.get("PROBE_PYLIBS", ""))
from axe_playwright_python.sync_playwright import Axe  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get("PROBE_BASE", "http://127.0.0.1:8900")
AXE_OPTIONS = {
    "runOnly": {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
    }
}

CASES = [
    ("list 1440 light", "/p/steampowernj/entries", 1440, 900, "light"),
    ("detail 1440 light", "/p/workbench-viewer/entries/choice-kit-open-questions", 1440, 900, "light"),
    ("list 1440 dark", "/p/steampowernj/entries", 1440, 900, "dark"),
    ("detail 1440 dark", "/p/workbench-viewer/entries/choice-kit-open-questions", 1440, 900, "dark"),
    ("list 390 light", "/p/steampowernj/entries", 390, 844, "light"),
    ("detail 390 light", "/p/workbench-viewer/entries/choice-kit-open-questions", 390, 844, "light"),
]


def main() -> int:
    axe = Axe()
    failures = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, route, width, height, mode in CASES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.add_init_script(
                "localStorage.setItem('wb-viewer.appearance', "
                f"JSON.stringify({{mode:'{mode}',palette:'olive',density:'comfortable'}}))")
            page.goto(BASE + "/#" + route, wait_until="networkidle")
            page.wait_for_timeout(1200)
            results = axe.run(page, options=AXE_OPTIONS)
            bad = [v for v in results.response["violations"]
                   if v["impact"] in ("serious", "critical")]
            for v in bad:
                failures += 1
                print(f"FAIL {name} {v['id']} ({v['impact']}) — {len(v['nodes'])} node(s): {v['help']}")
            print(f"probe-axe: {name} — {len(results.response['violations'])} violation(s), {len(bad)} serious/critical")
            page.close()
        browser.close()
    print(f"probe-axe: {failures} serious/critical failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
