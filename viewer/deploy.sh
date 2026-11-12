#!/usr/bin/env bash
# viewer/deploy.sh — the checkpoint deploy path for the
# Workbench Viewer artifact (live-work-tracking spec §1:
# a checkpoint is deployed + published THEN, with no manual
# steps; the deploy carries no built-in gate — gating is the
# caller's own step, run separately where it belongs).
#
#   viewer/deploy.sh
#
# Steps, fail-fast — any failure stops before the next step:
#   1. deploy  bash viewer.sh deploy (drift guard, backup,
#              copy repo viewer/ -> runtime space)
#   2. publish the web-artifact builder pass over the
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
RUNTIME="${VIEWER_RUNTIME_DIR:-$HERE/../../ts-spaces/workbench-viewer}"
HATCHLET="${HATCHLET:-hatchlet}"

if [ -n "${1:-}" ]; then
  echo "usage: viewer/deploy.sh" >&2
  exit 2
fi

step() { echo; echo "==> deploy: $1"; }

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
