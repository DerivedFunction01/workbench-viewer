#!/usr/bin/env python3
"""Read-only health probe for the workbench-viewer server.

Answers "is it up right now" from GET /api/health plus the
lock file's PID. Changes nothing except the configured
health file. Safe to run any time.

    python3 healthcheck.py        # exit 0 = healthy, 1 = not

The watchdog (ops/watchdog.sh, invoked by the cron) runs this
and acts on the exit code; a human can run it by hand the
same way. Host, port and paths come from config.py — no
literals here.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfgmod  # noqa: E402

CFG = cfgmod.load()
STATE = cfgmod.state_dir(CFG)


def fetch_health(path: str) -> dict:
    url = f"http://{CFG['host']}:{CFG['port']}{path}"
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())


def main() -> int:
    checked_at = datetime.now(timezone.utc).isoformat()
    result = {"checked_at": checked_at, "ok": False,
              "server_pid": None, "uptime_s": None,
              "version": None, "last_error": None}
    try:
        lock = json.loads((STATE / CFG["lock_file"]).read_text()
                          .strip().splitlines()[0])
        pid = int(lock["pid"])
        os.kill(pid, 0)
        result["server_pid"] = pid
    except Exception as e:
        result["last_error"] = f"lock/pid: {e}"
    health = None
    try:
        health = fetch_health("/api/health")
    except Exception as e:
        result["last_error"] = f"health http: {e}"
    if health is not None:
        if health.get("ok"):
            result["ok"] = True
            result["uptime_s"] = health.get("uptime_s")
            result["version"] = health.get("version")
            result["projects_count"] = health.get(
                "projects_count")
            result["config_hash"] = health.get("config_hash")
            result["last_error"] = None
        else:
            result["last_error"] = \
                "health endpoint returned ok=false"
    health_path = cfgmod.state_file(CFG, "health_file")
    try:
        health_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = health_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2) + "\n")
        tmp.replace(health_path)
    except OSError as e:
        # The health file is bookkeeping; the verdict rides
        # on the probe above. This environment intermittently
        # denies writes to agent-domain processes (EPERM
        # windows, first observed 2026-10-26); a bookkeeping
        # failure must not fail the check — the watchdog
        # restarts the server on any non-zero exit, so
        # crashing here would bounce a healthy server.
        print(f"healthcheck: could not write "
              f"{health_path}: {e}", file=sys.stderr)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
