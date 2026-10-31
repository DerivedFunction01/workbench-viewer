#!/usr/bin/env bash
# Workbench Viewer watchdog: healthcheck -> revive -> re-check.
# Silent (exit 0) when the server is healthy or was revived.
# Prints diagnostics and exits 1 only when every recovery path
# failed.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
# Repo automation runs under the repo's own venv when it exists
# (the owner's venv rule); the healthcheck itself is stdlib-only.
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="python3"; fi

# After a restart the server can take several seconds to answer
# (interpreter start + sweep, slower under load); a single check
# right after the restart races that startup and brands a
# successful revival as failed (observed 2026-10-30 and
# 2026-10-31). Poll for a bounded window instead.
wait_healthy() {
  local tries="${1:-30}"
  local i
  for ((i = 0; i < tries; i++)); do
    if "$PY" "$ROOT/server/healthcheck.py" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if "$PY" "$ROOT/server/healthcheck.py" >/dev/null; then
  exit 0
fi

echo "watchdog: healthcheck failed, attempting revival" >&2

# 1) systemd: reinstall the unit if /etc lost it (VM replacements
#    wipe /etc) — install-unit.sh renders it from the tracked
#    template — then restart.
if [ ! -f /etc/systemd/system/workbench-viewer-server.service ]; then
  bash "$DIR/install-unit.sh" 2>/dev/null \
    && systemctl enable --now workbench-viewer-server 2>/dev/null
fi
systemctl restart workbench-viewer-server 2>/dev/null
if wait_healthy 30; then
  echo "watchdog: revived via systemd" >&2
  exit 0
fi

# 2) Fallback: start directly (lock file keeps this
#    single-instance).
nohup "$PY" "$ROOT/run.py" >> "$ROOT/state/server.log" 2>&1 &
if wait_healthy 30; then
  echo "watchdog: revived via direct start" >&2
  exit 0
fi

echo "watchdog: FAILED to revive workbench-viewer-server" >&2
exit 1
