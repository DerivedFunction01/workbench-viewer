#!/usr/bin/env bash
# Create the staging project if it does not exist yet.
#
# Staging is a separate workbench project with its own git repo
# (SPEC section 2.1); it is NOT part of this repository. This repo
# carries only its seed files, under templates/staging/, so a fresh
# clone of the harness has everything needed to recreate it:
#
#   bash ops/bootstrap-staging.sh [target-dir]
#
# The default target is the "staging" directory beside this repo.
# The script is idempotent: when the target already holds a staging
# project (its manifest is present) it does nothing. When the target
# exists but is not a staging project, it refuses rather than
# overwriting unknown content. On creation it copies the seed files,
# initializes the target's own git repo with a founding commit, and
# creates the workbench registry when this repo's venv is available.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
seed_dir="$repo_root/templates/staging"
target="$(realpath -m "${1:-$repo_root/../staging}")"

if [[ -f "$target/workbench.yaml" ]]; then
    echo "staging already exists at $target — nothing to do"
    exit 0
fi
if [[ -e "$target" ]]; then
    echo "error: $target exists but is not a staging project" >&2
    echo "(no workbench.yaml); refusing to overwrite it" >&2
    exit 1
fi

mkdir -p "$target"
cp "$seed_dir/workbench.yaml" "$seed_dir/README.md" \
   "$seed_dir/GRADUATIONS.md" "$seed_dir/.gitignore" "$target/"

git -C "$target" init -b main
git -C "$target" add .gitignore GRADUATIONS.md README.md workbench.yaml
git -C "$target" -c user.name=DL -c user.email= \
    commit -m "Found the staging project (seeded from the harness templates)"

if [[ -x "$repo_root/.venv/bin/python" ]]; then
    (cd "$target" && "$repo_root/.venv/bin/python" "$repo_root/wb" init)
else
    echo "note: harness venv not built; run 'wb init' inside" >&2
    echo "$target after building it (python3 init_venv.py)" >&2
fi

echo "staging created at $target"
