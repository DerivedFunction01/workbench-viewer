#!/usr/bin/env python3
"""Workbench Viewer server — root entry point.

The server modules live in server/ and import each other
flat; this launcher puts that directory on sys.path and
calls server.main(). systemd (via ops/install-unit.sh) and
ops/watchdog.sh start the server through here, so the module
layout can change without the unit or the watchdog changing
again.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent
                       / "server"))

from server import main  # noqa: E402  (server/server.py)

if __name__ == "__main__":
    raise SystemExit(main())
