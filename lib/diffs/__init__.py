"""Plan/worktree diffs (repo-home spec §18, phase B2).

One mechanism under every view: the triple (repo, base,
target, paths), resolved here from an anchor — a worktree,
a plan bundle, or a commit (§18.1). Diffs exist ONLY
anchored (decision D10): a request that cannot name its
anchor is refused. Absorption amendment (absorption plan,
2026-10-28-git-viewer-absorption): a repo anchor (repo +
path) is a first-class anchor for a single file's peek and
diff against HEAD, served by lib/files; arbitrary revision
browsing stays out of scope.

Read-only by construction, like lib/worktrees: every git
invocation runs with GIT_OPTIONAL_LOCKS=0 and --no-ext-diff,
and revisions are validated before they reach a command
line (nothing starting with "-" is ever a revision or a
path — paths ride behind "--" regardless).

Modes (§18.3) are presets of the same triple:
  working      working state vs merge-base (the default,
               §18.2 — committed-since-fork AND uncommitted)
  uncommitted  working state vs HEAD
  committed    HEAD vs merge-base
  range        base..target (two caller-picked commits)
  commit       <id>^..<id> (one commit's own change)
A bundle anchor narrows the paths to the plan's declared
`files:` lists intersected with the changed set, unless
widened back with all_files (§18.3).

Per-file entries carry `legs` (committed / staged /
unstaged) whenever the mode has a working-state leg, so
the §18.2 staged/unstaged split is a client grouping over
this data, not a second engine.

Untracked and ignored files are never in the diff (§18.4):
untracked files get their own group, each renderable as a
new-file (all-additions) diff under the peek caps and the
peek secret policy (lib/files — the one policy, reused,
not reinvented); ignored files are listed only when
recently changed (mtime newer than the worktree's HEAD
commit time), peekable the same way, and NEVER diffed —
no baseline exists. A plan-declared file that is
git-ignored earns a warning entry: it will not be
committed.

Vanished references are states, not errors: a repo
with no commits yet diffs against the empty tree
(everything renders as additions, payload marked
`base_kind: "empty-tree"` + a note); a worktree whose
directory was deleted returns a typed `gone` payload;
a bundle whose plan document no longer loads falls
back to the un-narrowed working-state diff with a
note; a declared path that exists nowhere simply
contributes nothing. Error text that can reach a
payload comes from a small label vocabulary — raw
git stderr never renders.

The module is a package now (800-line cap split): git
plumbing, declared-files/bundle anchors, and the public
builders live in the submodules; this __init__
re-exports the existing public surface so
`import lib.diffs` and every current importer keep
working unchanged.
"""

from ..plans import parser as plan_parser

from .anchors import declared_files
from .builders import get_diff, peek_file, render_new_file
from .git_plumbing import (IGNORED_GROUP_CAP, MAX_BYTES,
                           MAX_LINES, MODES, DiffError)
