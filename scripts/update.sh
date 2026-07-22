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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

(cd "$ROOT_DIR" && git pull && cargo fetch --manifest-path "$BACKEND_DIR/Cargo.toml")
(cd "$ROOT_DIR" && git submodule update --init frontend)
(cd "$FRONTEND_DIR" && yarn install)

"$SCRIPT_DIR/build.sh"
