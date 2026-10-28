#!/usr/bin/env bash
# tools/check.sh — THE repo gate (Subplan 03). One command, four legs,
# fail-fast with the failing leg named:
#
#   1. python-unittest   repo venv, tests/ (stdlib unittest)
#   2. biome-check       viewer/ — lint + format + assist (pinned Biome)
#   3. typecheck         viewer/ — strict tsc, client + server
#   4. client-build      viewer/ — server bundle + client bundle
#
# The repo root is resolved from THIS script's location, never a
# hardcoded path, so the gate runs identically from a fresh worktree
# or clone. After `bun install` (in viewer/) and the venv build
# (`python3 init_venv.py`), every leg runs offline.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIEWER="$ROOT/viewer"
TOTAL=4
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

leg_python() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "check.sh: repo venv missing at .venv/ — build it: python3 init_venv.py" >&2
    return 1
  fi
  (cd "$ROOT" && .venv/bin/python -m unittest discover -s tests -v)
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

echo "workbench-viewer gate — repo root: $ROOT"
run_leg "python-unittest" leg_python
run_leg "biome-check" leg_biome
run_leg "typecheck" leg_typecheck
run_leg "client-build" leg_build

echo
echo "GATE PASS — all $TOTAL legs green"
