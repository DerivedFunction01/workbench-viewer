#!/usr/bin/env bash
# viewer/deploy.sh — the checkpoint deploy path for the
# Workbench Viewer artifact (live-work-tracking spec §1:
# a gate-green checkpoint is deployed + published THEN, with
# no manual steps; partial or red work never deploys).
#
#   viewer/deploy.sh [--skip-gate]
#
# Steps, fail-fast — any failure stops before the next step,
# and publish never runs on red work:
#   1. gate    bash tools/check.sh (the ONE repo gate)
#   2. deploy  bash viewer.sh deploy (drift guard, backup,
#              copy repo viewer/ -> runtime space)
#   3. publish the web-artifact builder pass over the
#              runtime space, via the hatchlet CLI when it
#              is on PATH (HATCHLET env override). Without a
#              builder CLI this step reports the exact
#              builder request needed and exits 4 — source is
#              deployed but NOT published, and the script
#              says so plainly rather than pretending a
#              manual `bun run build` publishes (it does not;
#              see viewer/SYNC.md).
#
# Paths come from the config seam, never literals: the repo
# root is this script's location; the runtime space is
# VIEWER_RUNTIME_DIR (viewer.sh's seam, same default).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RUNTIME="${VIEWER_RUNTIME_DIR:-../ts-spaces/workbench-viewer}"
HATCHLET="${HATCHLET:-hatchlet}"

SKIP_GATE=0
if [ "${1:-}" = "--skip-gate" ]; then
  SKIP_GATE=1
elif [ -n "${1:-}" ]; then
  echo "usage: viewer/deploy.sh [--skip-gate]" >&2
  exit 2
fi

step() { echo; echo "==> deploy: $1"; }

if [ "$SKIP_GATE" -eq 0 ]; then
  step "gate — bash tools/check.sh"
  if ! bash "$ROOT/tools/check.sh"; then
    echo "deploy: gate is RED — not deploying, not publishing" >&2
    exit 1
  fi
else
  echo "deploy: gate SKIPPED (--skip-gate) — caller owns the green proof"
fi

step "sync — viewer.sh deploy (repo -> runtime)"
if ! bash "$ROOT/viewer.sh" deploy; then
  echo "deploy: sync failed (drift? run viewer.sh status; use pull or --force deliberately)" >&2
  exit 3
fi

step "publish — builder pass over $RUNTIME"
if command -v "$HATCHLET" >/dev/null 2>&1; then
  if ! "$HATCHLET" build --space "$RUNTIME"; then
    echo "deploy: builder build/publish failed — source is deployed, artifact is NOT updated" >&2
    exit 4
  fi
  echo "deploy: checkpoint live — builder published the workbench-viewer artifact"
else
  echo "deploy: no builder CLI ('$HATCHLET') on PATH." >&2
  echo "deploy: source is deployed to $RUNTIME but NOT published." >&2
  echo "deploy: publish by requesting a builder build of the 'workbench-viewer'" >&2
  echo "deploy: artifact (the builder interface is the only publish path)." >&2
  exit 4
fi
