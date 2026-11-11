#!/usr/bin/env python3
"""probe-targets.py — scanner rule 2 of the 2026-11-10 entries
critic pass: the rendered target-size sweep.

Drives the probe-served client (the harness pattern: the built
client served beside the real action modules and the real
companion) in headless Chromium and measures every interactive
element's rendered bounding box on the Entries routes.

The bars (ui-context + the critic's rule):
  - a commit-class control (a <button> that is not a pressable
    chip, not a segmented label, not a whole-row opener) under
    38px tall fails; 44px under the coarse-pointer pass.
  - ANY measured target under 24px fails.
  - a visible label wrapping a visually hidden input is
    measured instead of the input (the SegmentedControl idiom:
    the native radio is sr-only by design, its label is the
    target); a pressable Chip's button box is its target (the
    pill inside keeps its own 24px contract height).

Run on the venue, with the probe stack up and playwright +
a chromium available to python3:
  PROBE_BASE=http://127.0.0.1:8900 python3 viewer/tools/probe-targets.py
Exit 1 on any failure. Sibling probes: probe-dom.py (rules
6+7), probe-axe.py (rule 8).
"""
import os
import sys

sys.path.insert(0, os.environ.get("PROBE_PYLIBS", ""))
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get("PROBE_BASE", "http://127.0.0.1:8900")

MEASURE_JS = r"""
() => {
  const out = [];
  const sels = 'button, a[href], input, select, textarea, [role="switch"], label';
  for (const el of document.querySelectorAll(sels)) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    // A label wrapping a visually hidden input IS the target
    // (segmented idiom); the input itself is never measured.
    if (el.tagName === 'INPUT' && el.closest('label')) continue;
    out.push({
      tag: el.tagName,
      type: el.getAttribute('type') || el.getAttribute('role') || '',
      label: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60),
      w: Math.round(r.width * 10) / 10,
      h: Math.round(r.height * 10) / 10,
      commit: el.tagName === 'BUTTON' && !el.hasAttribute('aria-pressed'),
    });
  }
  return out;
}
"""

failures = 0
measured = 0


def judge(pass_name, targets, bar):
    global failures, measured
    for t in targets:
        measured += 1
        problems = []
        if t["h"] < 24:
            problems.append(f"under the 24px floor ({t['h']}px)")
        if t["commit"] and t["h"] < bar:
            problems.append(f"commit-class under {bar}px ({t['h']}px)")
        if problems:
            failures += 1
            print(f"FAIL {pass_name} {t['tag']} \"{t['label']}\" — {'; '.join(problems)}")


def capture(browser, name, route, width, height, bar, mobile=False):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        is_mobile=mobile, has_touch=mobile)
    ctx.add_init_script(
        "localStorage.setItem('wb-viewer.appearance', "
        "JSON.stringify({mode:'light',palette:'olive',density:'comfortable'}))")
    page = ctx.new_page()
    page.goto(BASE + "/#" + route, wait_until="networkidle")
    page.wait_for_timeout(1200)
    targets = page.evaluate(MEASURE_JS)
    judge(name, targets, bar)
    print(f"probe-targets: {name} — {len(targets)} targets measured")
    ctx.close()


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        capture(browser, "list 1440 fine", "/p/steampowernj/entries", 1440, 900, 38)
        capture(browser, "detail 1440 fine",
                "/p/workbench-viewer/entries/choice-kit-open-questions", 1440, 900, 38)
        capture(browser, "list 390 coarse", "/p/steampowernj/entries", 390, 844, 44, mobile=True)
        capture(browser, "detail 390 coarse",
                "/p/workbench-viewer/entries/choice-kit-open-questions", 390, 844, 44, mobile=True)
        browser.close()
    print(f"probe-targets: {measured} targets, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
