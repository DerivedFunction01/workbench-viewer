#!/usr/bin/env python3
"""The one settings seam for the workbench-viewer server.

Every machine- or deployment-specific value is read through
here. Precedence:  WB_VIEWER_* env var  >  config.json  >
built-in default.

Bootstrap (the only assumptions this module itself makes):
config.json lives at the repo root (REPO_ROOT) unless
WB_VIEWER_CONFIG names another file. server.py and
healthcheck.py import load() from here and read nothing else
directly — no literals in the callers.

The traps this encodes (from the git repo viewer, the pattern
donor): under systemd HOME=/root, so the workspace is derived
from THIS FILE's location, never Path.home(); the port is
8792 because 8791 is the git viewer's.
"""

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent  # repo root: config.json, state/, run.py

DEFAULTS = {
    # null -> derive: the workspace is the parent of the repo
    # root. NEVER Path.home() (systemd runs with HOME=/root).
    "workspace_root": None,
    "host": "127.0.0.1",
    "port": 8792,  # 8791 is the git repo viewer's
    # null -> [workspace_root]
    "sweep_roots": None,
    "sweep_manifest": "workbench.yaml",
    "sweep_max_depth": 3,
    "sweep_prune": [".git", ".venv", ".venv311", "node_modules",
                    "__pycache__", "var", ".artifacts"],
    "sweep_ttl_s": 15,
    # Guarded file saves are OFF unless a deployment turns
    # them on: a fresh clone of this server cannot write.
    "file_editing_enabled": False,
    # Peek/save caps are enforced in lib/files.py
    # (PEEK_MAX_BYTES / PEEK_MAX_LINES, same values); they are
    # listed here so /config reports the whole surface.
    "peek_max_bytes": 200 * 1024,
    "peek_max_lines": 2000,
    # Per-project feed lock budget: a locked project DB
    # degrades only its own payload. Enforcement is lib/'s
    # connect_readonly busy_timeout (250 ms); this key
    # records the value for the /config surface.
    "feed_lock_timeout_ms": 250,
    # Relative paths resolve against the repo root.
    "state_dir": "state",
    "lock_file": "server.lock",
    "health_file": "health.json",
    "edit_backups_dir": "edit-backups",
}


def _coerce(raw: str, default):
    if isinstance(default, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    if isinstance(default, list):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return raw


def config_path() -> Path:
    raw = os.environ.get("WB_VIEWER_CONFIG")
    return Path(raw) if raw else REPO_ROOT / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.is_file():
        file_cfg = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(file_cfg, dict):
            raise ValueError(f"{path}: config must be an object")
        for key, value in file_cfg.items():
            if key.startswith("_"):
                continue  # comments in config.example.json
            if key not in DEFAULTS:
                raise ValueError(f"{path}: unknown config key "
                                 f"{key!r}")
            cfg[key] = value
    for key, default in DEFAULTS.items():
        env = os.environ.get("WB_VIEWER_" + key.upper())
        if env is not None:
            cfg[key] = _coerce(env, default)
    # Derived values, resolved once here so callers never
    # re-derive them (the systemd HOME trap lives here).
    if not cfg["workspace_root"]:
        cfg["workspace_root"] = str(REPO_ROOT.parent)
    if not cfg["sweep_roots"]:
        cfg["sweep_roots"] = [cfg["workspace_root"]]
    return cfg


def config_hash(cfg: dict) -> str:
    blob = json.dumps(cfg, sort_keys=True,
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def state_dir(cfg: dict) -> Path:
    p = Path(cfg["state_dir"])
    return p if p.is_absolute() else REPO_ROOT / p


def state_file(cfg: dict, key: str) -> Path:
    return state_dir(cfg) / cfg[key]


def sweep_roots(cfg: dict) -> list:
    return [Path(r) for r in cfg["sweep_roots"]]
