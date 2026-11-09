#!/usr/bin/env bash
# Workbench Viewer watchdog: healthcheck -> link probe ->
# auto-repair. Silent (exit 0) when the server is up AND
# systemd-supervised, or was repaired back to that state.
# Prints diagnostics and exits 1 only when the repair cap
# is exhausted — the scheduler surfaces just that case.
#
# The verdict is supervision, not an answering port: a
# fallback process dies with whatever session started it,
# so "something answered" is not recovery (2026-10-31).
# The probe (server/linkprobe.py) classifies down /
# up-unsupervised / up-supervised; the repair ladder
# (server/autorepair.py) restores the wiped unit from its
# tracked template, clears a stray unsupervised copy of
# run.py, and restarts the unit, capped at 3 rounds.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
# Repo automation runs under the repo's own venv when it exists
# (the owner's venv rule); the probe and repair are stdlib-only.
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="python3"; fi

# The plain healthcheck keeps state/health.json fresh (the
# escalation body and the scheduler entry's state record
# read it); its verdict is subsumed by the probe's. The leg
# runs under a hard bound (survival-contract rung 5, the
# scheduler keeper probe's discipline): the healthcheck's
# own read deadlines hold only while the box schedules the
# checker, and an unbounded leg that overruns the scheduler
# job's timeout gets the job killed mid-leg — the probe
# and the repair ladder then never run, exactly when the
# box is loaded enough to wedge the server (the 2026-11-09
# 19:19Z episode: the previous instance sat hard-wedged
# through eight watchdog cycles that all exited 0 without
# one repair attempt). The bound kills the leg alone; the
# probe that follows classifies from its own bounded fetch.
timeout -s KILL "${WB_HEALTHCHECK_TIMEOUT_S:-30}" \
  "$PY" "$ROOT/server/healthcheck.py" >/dev/null 2>&1 \
  || echo "watchdog: healthcheck leg exceeded its bound or failed; continuing to the link probe" >&2

if "$PY" "$ROOT/server/linkprobe.py" >/dev/null; then
  exit 0
fi

echo "watchdog: link probe not green, attempting auto-repair" >&2
exec "$PY" "$ROOT/server/autorepair.py"
