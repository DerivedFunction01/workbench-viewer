#!/usr/bin/env python3
"""End-to-end link probe for the workbench-viewer system.

Classifies the companion side of the published artifact's
link (artifact -> bridge -> companion server on loopback)
into the classes the auto-recovery machinery acts on:

    up_supervised    /api/health answers ok AND the
                     answering process is the systemd
                     unit's MainPID, with the unit file
                     present in /etc — the durable end
                     state. A fallback process answering
                     the port is NOT recovery: it dies
                     with whatever session started it
                     (the 2026-10-31 lesson).
    up_unsupervised  health answers ok but supervision
                     does not hold (unit file wiped,
                     service inactive, or the answering
                     PID is not the unit's MainPID).
    down             /api/health does not answer ok.

    python3 linkprobe.py   # exit 0 up_supervised,
                           # 1 down, 2 up_unsupervised

The space-side leg (the artifact's own build and bridge)
cannot be exercised from this machine: nothing here can
invoke the published actions, so no script can prove that
leg. It is classified agent-side through the scheduler
escalation instead — companion up_supervised here while a
published read action fails there is the link_broken
class, whose repair is a republish pass. The result JSON
says so in its `link` field rather than letting a green
companion read as a green link.

Read-only except its own state file (state/link.json,
written with healthcheck.py's discipline: a bookkeeping
write failure never changes the verdict). Host, port,
paths and the unit name come from config.py — no literals
here beyond the systemd system-unit directory, a platform
fact the installer (ops/install-unit.sh) shares.
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfgmod  # noqa: E402

CFG = cfgmod.load()
STATE = cfgmod.state_dir(CFG)
UNIT_DIR = Path("/etc/systemd/system")

UP_SUPERVISED = "up_supervised"
UP_UNSUPERVISED = "up_unsupervised"
DOWN = "down"
EXIT_CODES = {UP_SUPERVISED: 0, DOWN: 1, UP_UNSUPERVISED: 2}


def fetch_health() -> dict | None:
    # A 10s budget, not healthcheck.py's 3s: under load a
    # healthy server can take ~4s to answer /api/health
    # (measured 2026-11-03), and a probe timeout reads as
    # down. The bridge's own budget is 20s; a health
    # answer slower than 10s is operationally down.
    url = f"http://{CFG['host']}:{CFG['port']}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return None


def read_lock_pid() -> int | None:
    try:
        lock = json.loads((STATE / CFG["lock_file"]).read_text()
                          .strip().splitlines()[0])
        pid = int(lock["pid"])
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def parse_systemd_show(text: str) -> dict:
    """`systemctl show` key=value lines -> the fields the
    classification reads. MainPID is an int (0 when the
    unit has no running main process)."""
    fields = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    try:
        main_pid = int(fields.get("MainPID") or 0) or None
    except ValueError:
        main_pid = None
    return {"active_state": fields.get("ActiveState") or None,
            "load_state": fields.get("LoadState") or None,
            "main_pid": main_pid}


def systemd_state(unit: str) -> dict:
    """The unit's on-disk + runtime state. Never raises: a
    missing systemctl or an unknown unit reads as absent,
    which the classification treats as unsupervised."""
    state = {"unit_file": (UNIT_DIR / f"{unit}.service").is_file(),
             "active_state": None, "load_state": None,
             "main_pid": None, "error": None}
    try:
        out = subprocess.run(
            ["systemctl", "show", f"{unit}.service",
             "-p", "MainPID", "-p", "ActiveState",
             "-p", "LoadState"],
            capture_output=True, text=True, timeout=10)
        state.update(parse_systemd_show(out.stdout))
    except Exception as e:
        state["error"] = f"systemctl show: {e}"
    return state


def classify(health_ok: bool, lock_pid: int | None,
             sd: dict) -> tuple[str, list[str]]:
    """Pure classification over the probed facts."""
    if not health_ok:
        return DOWN, ["health_not_ok"]
    reasons = []
    if not sd.get("unit_file"):
        reasons.append("unit_file_missing")
    if sd.get("load_state") != "loaded":
        reasons.append("unit_not_loaded")
    if sd.get("active_state") != "active":
        reasons.append("service_not_active")
    if sd.get("main_pid") is None:
        reasons.append("no_main_pid")
    elif lock_pid is None:
        reasons.append("lock_pid_missing")
    elif sd["main_pid"] != lock_pid:
        reasons.append("main_pid_mismatch")
    if reasons:
        return UP_UNSUPERVISED, reasons
    return UP_SUPERVISED, []


def probe(fetch=fetch_health, lock_pid_of=read_lock_pid,
          systemd_of=systemd_state) -> dict:
    health = fetch()
    health_ok = bool(health and health.get("ok"))
    lock_pid = lock_pid_of()
    sd = systemd_of(CFG["systemd_unit"])
    klass, reasons = classify(health_ok, lock_pid, sd)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "class": klass,
        "ok": klass == UP_SUPERVISED,
        "reasons": reasons,
        "server_pid": lock_pid,
        "version": health.get("version") if health else None,
        "commit": health.get("commit") if health else None,
        "systemd": {"unit": CFG["systemd_unit"],
                    "unit_file": sd.get("unit_file"),
                    "active_state": sd.get("active_state"),
                    "load_state": sd.get("load_state"),
                    "main_pid": sd.get("main_pid"),
                    "error": sd.get("error")},
        # The space-side leg is not exercisable from this
        # machine; see the module docstring.
        "link": "not_checked_by_script",
    }


def main() -> int:
    result = probe()
    link_path = cfgmod.state_file(CFG, "link_file")
    try:
        link_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = link_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2) + "\n")
        tmp.replace(link_path)
    except OSError as e:
        # Bookkeeping only — same discipline as
        # healthcheck.py: a denied write must not change
        # the verdict the watchdog acts on.
        print(f"linkprobe: could not write {link_path}: {e}",
              file=sys.stderr)
    print(json.dumps(result))
    return EXIT_CODES[result["class"]]


if __name__ == "__main__":
    sys.exit(main())
