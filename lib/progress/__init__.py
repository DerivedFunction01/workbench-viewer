"""Derived progress and its scheduler entries.

The package form of the former flat pair: the derived
progress report (cadence, checkpoints, stall verdict —
computed at read time, never stored) lives in
report.py; the scheduler-registry entry write path
lives in schedule.py. This __init__ re-exports both
public surfaces so `import lib.progress` and every
current importer keep working unchanged; entry
importers name lib.progress.schedule directly.
"""

from .report import (CHECKPOINT_PREFIX,
                     STALL_MISSED_CHECKS, last_checkpoint,
                     project_progress, todo_progress)
from .schedule import (CHECK_TIMEOUT_SECS, ENTRY_PREFIX,
                       REPO_ROOT, STOP_STATUSES, check_todo,
                       entry_id, entry_migrated, is_armed,
                       jobs_dir, parse_entry_todo_id,
                       render_entry, scheduled_ids, sync_all,
                       sync_todo)

__all__ = ["CHECKPOINT_PREFIX", "STALL_MISSED_CHECKS",
           "last_checkpoint", "project_progress",
           "todo_progress", "REPO_ROOT", "ENTRY_PREFIX",
           "STOP_STATUSES", "CHECK_TIMEOUT_SECS",
           "jobs_dir", "entry_id", "is_armed",
           "entry_migrated", "scheduled_ids",
           "render_entry", "sync_todo", "sync_all",
           "parse_entry_todo_id", "check_todo"]
