#!/bin/bash
#
# Pulls the latest monorepo (backend/, database/, scripts/) and checks out
# the frontend/ submodule at whatever commit the monorepo currently pins it
# to, then rebuilds. Needs connectivity (git + potentially new deps) —
# unlike build.sh/run.sh, which stay offline.
#
# Note: this does NOT fetch frontend's latest main — the submodule pin only
# moves when someone bumps it deliberately (normally automatic, via a
# GitHub Actions workflow triggered by a version tag on frontend's own
# repo — see the root README's "The frontend submodule" section). This
# script just syncs the checkout to whatever that pin currently says.
#
# The db (database/pp1_collection.db) is tracked in git but also written
# live by the kiosk (visitors, testimonies, summaries — see sync-db.sh for
# how that gets pushed back). A plain `git pull` would clobber those local
# writes with whatever's in origin, or fail outright if they conflict. So
# the kiosk's local db always wins here: stash it, pull everything else,
# restore it. Origin's version of the db still lands in .git history — it's
# just never applied to the working copy — so a human can `git stash list`
# / diff it in later if a manual merge is ever needed.
#
# The dirty-check compares against HEAD (not a plain worktree `git diff`)
# because sync-db.sh stages the db (`git add`) before committing — a plain
# `git diff` is blind to staged-but-uncommitted changes (e.g. left behind by
# a sync-db.sh run that got interrupted before its commit), which used to
# let update.sh skip the stash and then fail on `git pull` with "local
# changes... would be overwritten by merge".
#
# frontend/public/config.json (and config.dev.json) are similarly editable
# in production (see README's "Editable-in-production files") without a
# rebuild being required until the next one. Uncommitted edits there make
# the submodule dirty, which makes `git submodule update --init` refuse to
# move the checkout — so these get the same stash/restore treatment as the
# db, scoped to the frontend submodule.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DB_STASHED=0
if [[ -f "$DATABASE_PATH" ]] && ! git -C "$ROOT_DIR" diff --quiet HEAD -- "$DATABASE_PATH"; then
  git -C "$ROOT_DIR" stash push --quiet --include-untracked -- "$DATABASE_PATH"
  DB_STASHED=1
fi

(cd "$ROOT_DIR" && git pull && cargo fetch --manifest-path "$BACKEND_DIR/Cargo.toml")

if [[ "$DB_STASHED" -eq 1 ]]; then
  git -C "$ROOT_DIR" checkout stash@{0} -- "$DATABASE_PATH"
  git -C "$ROOT_DIR" stash drop --quiet
fi

FRONTEND_CONFIG_STASHED=0
if [[ -d "$FRONTEND_DIR" ]] && ! git -C "$FRONTEND_DIR" diff --quiet HEAD -- public/config.json public/config.dev.json 2>/dev/null; then
  git -C "$FRONTEND_DIR" stash push --quiet -- public/config.json public/config.dev.json
  FRONTEND_CONFIG_STASHED=1
fi

(cd "$ROOT_DIR" && git submodule update --init frontend)

if [[ "$FRONTEND_CONFIG_STASHED" -eq 1 ]]; then
  git -C "$FRONTEND_DIR" checkout stash@{0} -- public/config.json public/config.dev.json
  git -C "$FRONTEND_DIR" stash drop --quiet
fi

(cd "$FRONTEND_DIR" && yarn install)

"$SCRIPT_DIR/build.sh"
