#!/usr/bin/env bash
# tools/check.sh — THE repo gate (Subplan 03). One command, nine legs,
# fail-fast with the failing leg named:
#
#   1. length-scan       tools/length.py — the 800-line cap
#   2. python-unittest   repo venv, tests/ (stdlib unittest)
#   3. biome-check       viewer/ — lint + format + assist (pinned Biome)
#   4. typecheck         viewer/ — strict tsc, client + server
#   5. client-build      viewer/ — server bundle + client bundle
#   6. contrast          viewer/tools/verify-contrast.mjs — status text
#                        + content tokens against every surface
#                        (both palettes x both modes; scanner rule 1)
#   7. primitives-lint   viewer/tools/lint-primitives.py — no raw
#                        form primitives in the entries section
#                        (scanner rule 3)
#   8. arm-guard         viewer/tools/check-arm-guard.py — every
#                        lifecycle commit routes through the
#                        ArmConfirm guard (scanner rule 4)
#   9. viewport          viewer/tools/check-viewport.py — the
#                        viewport meta never disables user
#                        scaling (scanner rule 5)
#
# The repo root is resolved from THIS script's location, never a
# hardcoded path, so the gate runs identically from a fresh worktree
# or clone. After `bun install` (in viewer/) and the venv build
# (`python3 init_venv.py`), every leg runs offline.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIEWER="$ROOT/viewer"
TOTAL=9
leg=0

run_leg() {
  local name="$1"
  shift
  leg=$((leg + 1))
  echo
  echo "==> [$leg/$TOTAL] $name"
  if "$@"; then
    echo "-- PASS: $name"
  else
    local rc=$?
    echo "-- FAIL: $name (exit $rc) — gate stops here" >&2
    exit "$rc"
  fi
}

leg_length() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "check.sh: repo venv missing at .venv/ — build it: python3 init_venv.py" >&2
    return 1
  fi
  (cd "$ROOT" && .venv/bin/python tools/length.py)
}

leg_python() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "check.sh: repo venv missing at .venv/ — build it: python3 init_venv.py" >&2
    return 1
  fi
  (cd "$ROOT" && .venv/bin/python -m unittest discover -s tests -t . -v)
}

leg_biome() {
  if [ ! -x "$VIEWER/node_modules/.bin/biome" ]; then
    echo "check.sh: viewer dependencies missing — install them: (cd viewer && bun install)" >&2
    return 1
  fi
  (cd "$VIEWER" && bun x biome check .)
}

leg_typecheck() {
  (cd "$VIEWER" && bun run typecheck)
}

leg_build() {
  (cd "$VIEWER" && bun run build)
}

leg_contrast() {
  (cd "$VIEWER" && bun tools/verify-contrast.mjs)
}

leg_primitives() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "check.sh: repo venv missing at .venv/ — build it: python3 init_venv.py" >&2
    return 1
  fi
  (cd "$ROOT" && .venv/bin/python viewer/tools/lint-primitives.py)
}

leg_arm_guard() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "check.sh: repo venv missing at .venv/ — build it: python3 init_venv.py" >&2
    return 1
  fi
  (cd "$ROOT" && .venv/bin/python viewer/tools/check-arm-guard.py)
}

leg_viewport() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "check.sh: repo venv missing at .venv/ — build it: python3 init_venv.py" >&2
    return 1
  fi
  (cd "$ROOT" && .venv/bin/python viewer/tools/check-viewport.py)
}

echo "workbench-viewer gate — repo root: $ROOT"
run_leg "length-scan" leg_length
run_leg "python-unittest" leg_python
run_leg "biome-check" leg_biome
run_leg "typecheck" leg_typecheck
run_leg "client-build" leg_build
run_leg "contrast" leg_contrast
run_leg "primitives-lint" leg_primitives
run_leg "arm-guard" leg_arm_guard
run_leg "viewport" leg_viewport

echo
echo "GATE PASS — all $TOTAL legs green"
