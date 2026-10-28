#!/usr/bin/env bash
# Render the systemd unit from its template (@ROOT@ -> the repo
# root derived from this script's location, @PYTHON@ -> the venv
# interpreter when .venv exists, else the system python3) and
# install it. The rendered workbench-viewer-server.service is a
# machine-local artefact (gitignored, like config.json); the
# template is the tracked source, so a fresh clone works under
# any home dir. systemd here is the SYSTEM instance
# (systemctl --user has no bus on this VM).
set -eu
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON="/usr/bin/python3"; fi
sed -e "s|@ROOT@|$ROOT|g" -e "s|@PYTHON@|$PYTHON|g" \
    "$DIR/workbench-viewer-server.service.template" \
    > "$DIR/workbench-viewer-server.service"
cp "$DIR/workbench-viewer-server.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable workbench-viewer-server
echo "installed workbench-viewer-server.service for ROOT=$ROOT PYTHON=$PYTHON"
