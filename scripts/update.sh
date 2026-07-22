#!/bin/bash
#
# Pulls latest backend/frontend changes and rebuilds. Needs connectivity
# (git + potentially new deps) — unlike build.sh/run.sh, which stay offline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

(cd "$BACKEND_DIR" && git checkout "$BACKEND_BRANCH" && git pull && cargo fetch)
(cd "$FRONTEND_DIR" && git checkout "$FRONTEND_BRANCH" && git pull && yarn install)

"$SCRIPT_DIR/build.sh"
