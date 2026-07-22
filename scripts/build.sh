#!/bin/bash
#
# Builds backend + frontend, offline (see install.sh for the one-time setup
# that populates the caches this relies on).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if ! command -v cargo >/dev/null 2>&1 && [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.cargo/env"
fi

command -v cargo >/dev/null 2>&1 || { echo "cargo not found; run install.sh first." >&2; exit 1; }
command -v yarn >/dev/null 2>&1 || { echo "yarn not found." >&2; exit 1; }

(cd "$BACKEND_DIR" && cargo build --release --offline)
[[ -x "$BACKEND_BINARY" ]] || { echo "Backend build failed: $BACKEND_BINARY not found." >&2; exit 1; }

[[ -d "$FRONTEND_DIR/node_modules" ]] || { echo "node_modules missing; run install.sh with connectivity first." >&2; exit 1; }
(cd "$FRONTEND_DIR" && yarn build)
[[ -f "$FRONTEND_BUILD_DIR/index.html" ]] || { echo "Frontend build failed: index.html not found." >&2; exit 1; }

echo "Build succeeded."
