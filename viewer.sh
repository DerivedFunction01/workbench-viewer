#!/usr/bin/env bash
# viewer.sh — keep the Workbench Viewer artifact's source canonical
# in THIS repo (viewer/) and deploy it to its runtime location.
#
#   viewer.sh status           drift report (repo viewer/ vs runtime);
#                              exit 3 on drift
#   viewer.sh pull             runtime -> repo (after builder-driven
#                              changes)
#   viewer.sh deploy [--force] repo -> runtime: drift guard, backup,
#                              copy
#
# Runtime dir defaults to the workbench-viewer folder under the
# workspace's ts-spaces dir and can be overridden with
# VIEWER_RUNTIME_DIR (restore tests use a scratch dir).
#
# The sync set is the viewer/ tree's source files only: node_modules,
# dist, *.db*, .bun-cache and other runtime/build artefacts are NEVER
# synced. Publishing is a separate builder pass over the runtime
# tree (the artifact build itself belongs to the viewer build steps;
# this script only moves source).
#
# The exclusions below apply at ANY depth: the tree's build output
# lives at client/dist + server/dist (hashed names churn every
# build), and *.tsbuildinfo.* is local typecheck state — neither is
# source, and the builder regenerates dist in the runtime tree.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_VIEWER="$HERE/viewer"
RUNTIME="${VIEWER_RUNTIME_DIR:-../ts-spaces/workbench-viewer}"

manifest() {  # $1 = base dir; prints "sha256  relpath" lines, sorted
    local base="$1"
    [ -d "$base" ] || return 0
    ( cd "$base" || exit 0
      find . -type f \
        -not -path '*/node_modules/*' -not -path '*/dist/*' \
        -not -path '*/.bun-cache/*' -not -name '*.db*' \
        -not -name '*.tsbuildinfo.*' \
        -not -name 'app.db*' | sed 's|^\./||' ) | sort \
      | while IFS= read -r rel; do
        printf '%s  %s\n' "$(sha256sum < "$base/$rel" | cut -d' ' -f1)" "$rel"
    done
}

drift() {  # prints one line per drifted file: kind + path
    local repo_f rt_f
    repo_f="$(mktemp)"; rt_f="$(mktemp)"
    manifest "$REPO_VIEWER" | awk 'NF==2 {print $2, $1}' | sort > "$repo_f"
    manifest "$RUNTIME" | awk 'NF==2 {print $2, $1}' | sort > "$rt_f"
    comm -13 <(cut -d' ' -f1 "$repo_f") <(cut -d' ' -f1 "$rt_f") \
        | sed 's/^/runtime-only  /'
    comm -23 <(cut -d' ' -f1 "$repo_f") <(cut -d' ' -f1 "$rt_f") \
        | sed 's/^/repo-only     /'
    join "$repo_f" "$rt_f" | awk '$2 != $3 {print "differ        " $1}'
    rm -f "$repo_f" "$rt_f"
}

sync_tree() {  # $1 = src, $2 = dst
    local src="$1" dst="$2"
    mkdir -p "$dst"
    ( cd "$src" && find . -type f \
        -not -path '*/node_modules/*' -not -path '*/dist/*' \
        -not -path '*/.bun-cache/*' -not -name '*.db*' \
        -not -name '*.tsbuildinfo.*' \
        -not -name 'app.db*' -print0 ) \
      | while IFS= read -r -d '' rel; do
          rel="${rel#./}"
          mkdir -p "$dst/$(dirname "$rel")"
          cp "$src/$rel" "$dst/$rel"
        done
}

cmd="${1:-status}"
case "$cmd" in
  status)
    out="$(drift)"
    if [ -n "$out" ]; then
      echo "$out"
      echo "viewer.sh: drift detected" >&2
      exit 3
    fi
    echo "viewer.sh: repo viewer/ and runtime are in sync"
    ;;
  pull)
    sync_tree "$RUNTIME" "$REPO_VIEWER"
    echo "viewer.sh: pulled runtime -> repo"
    ;;
  deploy)
    if [ "${2:-}" != "--force" ]; then
      out="$(drift)"
      if [ -n "$out" ]; then
        echo "$out" >&2
        echo "viewer.sh: refusing to deploy over drift (use --force, or pull first)" >&2
        exit 3
      fi
    fi
    if [ -d "$RUNTIME" ]; then
      backup="$RUNTIME.bak-$(date +%Y%m%d%H%M%S)"
      cp -a "$RUNTIME" "$backup"
      echo "viewer.sh: previous runtime backed up to $backup"
    fi
    sync_tree "$REPO_VIEWER" "$RUNTIME"
    echo "viewer.sh: deployed repo -> runtime"
    ;;
  *)
    echo "usage: viewer.sh [status|pull|deploy [--force]]" >&2
    exit 2
    ;;
esac
