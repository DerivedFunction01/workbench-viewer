#!/usr/bin/env bash
# wb doctor --post runner (wb-doctor plan): the periodic
# consistency sweep over every swept project. Invoked by
# the Muse cron workbench-viewer-doctor every 15
# minutes. This VM has no unix cron (no crontab binary,
# no daemon), so the Muse cron is the scheduler, in
# the same shape as the healthcheck beside it.
#
# wb's exit code is propagated: 0 = clean, 1 = findings
# (both normal — a changed finding set is delivered by
# the doctor itself as a digest through the outbox);
# anything above 1 is a crash. Output appends to
# state/doctor.log (runtime state, untracked).
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p "$ROOT/state"
LOG="$ROOT/state/doctor.log"
{
  echo "== $(date -Is) wb doctor --post"
  (cd "$ROOT" && "$PY" wb doctor --post)
  rc=$?
  echo "exit=$rc"
  exit "$rc"
} >> "$LOG" 2>&1
