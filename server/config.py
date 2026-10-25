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
    # Repo-home (spec §5/§6): the viewer-tied message store.
    # messages_db resolves against state_dir unless absolute.
    "messages_db": "messages.db",
    "messages_draft_ttl_days": 7,
    "messages_done_archive_days": 30,
    "messages_archive_ttl_days": 90,
    "messages_awaiting_badge_days": 14,
    "messages_per_project_cap": 1000,
    # Repo-home §15.1: optional generic notify targets for
    # new outbox rows, fired by the server maintenance loop.
    # null = not configured (the outbox table alone is the
    # interface). The command receives the event JSON on
    # stdin; the webhook receives it as a POST body.
    "messages_notify_webhook": None,
    "messages_notify_command": None,
    "messages_notify_poll_s": 30,
    # Repo-home §6: a worktree untouched this many days (or
    # merged into its base) derives the "likely done" flag.
    "worktree_stale_days": 14,
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


def messages_db_path(cfg: dict) -> Path:
    """The viewer-tied message store (repo-home spec D9):
    state_dir/messages_db unless the key is absolute."""
    p = Path(cfg["messages_db"])
    return p if p.is_absolute() else state_dir(cfg) / p


def notify_targets(cfg: dict) -> dict:
    """Watcher notify targets (repo-home spec §15.1),
    assembled from the seam for lib/notify.fire_targets."""
    return {"webhook": cfg["messages_notify_webhook"],
            "command": cfg["messages_notify_command"]}


def messages_policy(cfg: dict) -> dict:
    """Cleanup policy for lib/messages.cleanup, assembled
    from the seam so lib/ never reads config itself."""
    return {
        "draft_ttl_days": cfg["messages_draft_ttl_days"],
        "done_archive_days": cfg["messages_done_archive_days"],
        "archive_ttl_days": cfg["messages_archive_ttl_days"],
        "awaiting_badge_days":
            cfg["messages_awaiting_badge_days"],
        "per_project_cap": cfg["messages_per_project_cap"],
    }
