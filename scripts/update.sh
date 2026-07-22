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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DB_STASHED=0
if [[ -f "$DATABASE_PATH" ]] && ! git -C "$ROOT_DIR" diff --quiet -- "$DATABASE_PATH"; then
  git -C "$ROOT_DIR" stash push --quiet --include-untracked -- "$DATABASE_PATH"
  DB_STASHED=1
fi

(cd "$ROOT_DIR" && git pull && cargo fetch --manifest-path "$BACKEND_DIR/Cargo.toml")

if [[ "$DB_STASHED" -eq 1 ]]; then
  git -C "$ROOT_DIR" checkout stash@{0} -- "$DATABASE_PATH"
  git -C "$ROOT_DIR" stash drop --quiet
fi

(cd "$ROOT_DIR" && git submodule update --init frontend)
(cd "$FRONTEND_DIR" && yarn install)

"$SCRIPT_DIR/build.sh"
