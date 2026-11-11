#!/usr/bin/env python3
"""probe-dom.py — scanner rules 6+7 of the 2026-11-10
entries critic pass, checked against the rendered detail
route.

Rule 6 (duplicate frame titles): the entry detail renders
exactly ONE <figure> — the stage — and no two figures may
share a title. F5 was two frames both titled with the
entry's title stacked in the stage column.

Rule 7 (no controls in a frame header line): no figure's
figcaption on the detail route may contain a button,
fieldset, select, or input. F5's second half was the
summary frame's mode toggle living in its header line,
restyling only its own frame.

Scope, recorded: the rules are enforced where the
findings live — the detail stage column. Storyboard LIST
frames keep their per-frame mode toggle by a ui-context
fundamental (each frame previews its entry in its own
mode), and the detail's own "back" header line is shell
navigation, not a frame header; neither is probed here.

Run on the venue with the probe stack up:
  PROBE_BASE=http://127.0.0.1:8900 python3 viewer/tools/probe-dom.py
Exit 1 on any failure. Sibling probes: probe-targets.py
(rule 2), probe-axe.py (rule 8).
"""
import os
import sys

sys.path.insert(0, os.environ.get("PROBE_PYLIBS", ""))
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get("PROBE_BASE", "http://127.0.0.1:8900")
DETAIL = "/p/workbench-viewer/entries/choice-kit-open-questions"

PROBE_JS = r"""
() => {
  const figures = [...document.querySelectorAll('figure')];
  return figures.map((fig) => {
    const caption = fig.querySelector('figcaption');
    const titleSpan = caption ? caption.querySelector('span') : null;
    return {
      title: titleSpan ? titleSpan.textContent.trim() : '',
      headerControls: caption
        ? caption.querySelectorAll('button, fieldset, select, input').length
        : 0,
    };
  });
}
"""


def main() -> int:
    failures = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(
            "localStorage.setItem('wb-viewer.appearance', "
            "JSON.stringify({mode:'light',palette:'olive',density:'comfortable'}))")
        page.goto(BASE + "/#" + DETAIL, wait_until="networkidle")
        page.wait_for_timeout(1200)
        figures = page.evaluate(PROBE_JS)
        browser.close()
    if len(figures) != 1:
        failures += 1
        print(f"FAIL rule 6: detail route renders {len(figures)} figure(s), expected exactly 1 (the stage)")
    titles = [f["title"] for f in figures]
    if len(set(titles)) != len(titles):
        failures += 1
        print(f"FAIL rule 6: duplicate figure titles on the detail route: {titles}")
    for fig in figures:
        if fig["headerControls"]:
            failures += 1
            print(f"FAIL rule 7: figure '{fig['title']}' carries {fig['headerControls']} control(s) in its header line")
    print(f"probe-dom: {len(figures)} figure(s) on the detail route, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
