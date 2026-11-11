#!/usr/bin/env bash
# run-probes.sh — the rendered-probe leg of the gate for UI
# changes (ruling q5, standing-leg, 2026-11-10).
#
# tools/check.sh runs offline and cannot drive a browser,
# so the rendered guards live here: run on the venue with
# the probe stack up (the built client served beside the
# real action modules and the real companion, the harness
# pattern), after check.sh's offline legs pass.
#
#   probe-targets.py   scanner rule 2 — rendered sizes
#   probe-dom.py       scanner rules 6+7 — detail frames
#   probe-axe.py       scanner rule 8 — axe WCAG 2.2 AA
#
# PROBE_BASE names the probe server (default the harness
# port); PROBE_PYLIBS names the python packages carrying
# playwright + axe-playwright-python on the venue.
set -uo pipefail
cd "$(dirname "$0")"
export PROBE_BASE="${PROBE_BASE:-http://127.0.0.1:8900}"
rc=0
for probe in probe-targets.py probe-dom.py probe-axe.py; do
  echo "==> $probe"
  python3 "$probe" || rc=1
done
if [ "$rc" -eq 0 ]; then
  echo "run-probes: all rendered probes green"
else
  echo "run-probes: FAILURES above" >&2
fi
exit "$rc"
