#!/usr/bin/env python3
"""Create this repo's virtualenv and install its declared dependencies.

The machine pattern: a uv-managed CPython 3.11 venv at .venv/,
built by uv (never system python — system-site installs do not
survive VM replacement, and a missing system package is a sign
the launch path is wrong, not something to repair in place).
lib/ and server/ are stdlib-only, so requirements.txt installs
nothing today; the venv exists so the interpreter is pinned and
the launch path is uniform (systemd unit, watchdog, tests all
go through .venv/bin/python).

Usage:  python3 init_venv.py [--recreate]
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
PYTHON_SPEC = "3.11"


def find_uv() -> str:
    uv = shutil.which("uv")
    if uv:
        return uv
    candidate = Path.home() / ".local" / "bin" / "uv"
    if candidate.exists():
        return str(candidate)
    raise SystemExit("init_venv: uv not found on PATH or at "
                     "~/.local/bin/uv — install uv first")


def main() -> int:
    uv = find_uv()
    if "--recreate" in sys.argv and VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    if not VENV_DIR.exists():
        subprocess.run([uv, "venv", "--python", PYTHON_SPEC,
                        str(VENV_DIR)], check=True)
        print(f"init_venv: created {VENV_DIR} (uv, Python "
              f"{PYTHON_SPEC})")
    python = VENV_DIR / "bin" / "python"
    req = ROOT / "requirements.txt"
    subprocess.run([uv, "pip", "install", "--python", str(python),
                    "-r", str(req)], check=True)
    version = subprocess.run([str(python), "-c",
                              "import sys; print(sys.version.split()[0])"],
                             capture_output=True, text=True).stdout.strip()
    print(f"init_venv: dependencies installed from {req.name} "
          f"(stdlib only — nothing to install today)")
    print(f"init_venv: interpreter: {python} (Python {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
