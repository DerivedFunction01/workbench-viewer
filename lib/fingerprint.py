"""Per-project content fingerprint (cache-refresh plan,
2026-11-05): a sha256 over the stat shape of the file
corpus a project's file-derived feeds are built from —
every file under the project's `.plans/` tree plus its
`workbench.yaml` manifest.

Stat-only (relpath, size, mtime_ns per file, sorted by
relpath): no file is ever opened, so the walk stays
cheap enough to ride the discovery sweep. Any write in
the corpus — a todo move, a plan edit, a new bundle —
moves a size or an mtime and so moves the fingerprint;
an untouched corpus fingerprints identically forever,
which is what lets the server's keyed feed caches serve
without a TTL. A missing `.plans/` (or manifest) is not
an error: the fingerprint covers whatever exists.
"""

import hashlib
from pathlib import Path


def project_fingerprint(root) -> str:
    """The fingerprint of one project root (see module
    note). Files that vanish mid-walk are skipped — the
    next walk settles on the new shape."""
    root = Path(root)
    paths = [root / "workbench.yaml"]
    plans = root / ".plans"
    if plans.is_dir():
        paths.extend(p for p in plans.rglob("*")
                     if p.is_file())
    rows = []
    for path in paths:
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append((path.relative_to(root).as_posix(),
                     st.st_size, st.st_mtime_ns))
    h = hashlib.sha256()
    for rel, size, mtime_ns in sorted(rows):
        h.update(f"{rel}\0{size}\0{mtime_ns}\n"
                 .encode("utf-8"))
    return h.hexdigest()
