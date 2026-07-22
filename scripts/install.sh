#!/bin/bash
#
# One-time setup, run with internet connectivity: toolchains, deps, first
# build, and the login LaunchAgent. Safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/../.env" ]]; then
  cp "$SCRIPT_DIR/../.env.example" "$SCRIPT_DIR/../.env"
  echo "Created .env from .env.example — edit it if your layout differs."
fi

source "$SCRIPT_DIR/common.sh"

if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend project not found: $BACKEND_DIR" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR" ]] || [[ -z "$(ls -A "$FRONTEND_DIR" 2>/dev/null)" ]]; then
  echo "Frontend submodule not initialized; running 'git submodule update --init'..."
  (cd "$ROOT_DIR" && git submodule update --init frontend)
fi

if ! command -v yarn >/dev/null 2>&1; then
  echo "yarn not found; install Node.js + yarn before running this script." >&2
  exit 1
fi

# ---- Xcode Command Line Tools -----------------------------------------------

if ! xcode-select -p >/dev/null 2>&1; then
  echo "Installing Xcode Command Line Tools..."
  xcode-select --install
  echo "Re-run this script after that installation finishes."
  exit 1
fi

# ---- Rust toolchain --------------------------------------------------------

if ! command -v cargo >/dev/null 2>&1 && [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Installing Rust via rustup..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  # shellcheck disable=SC1091
  source "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo still not found on PATH; open a new shell and re-run this script." >&2
  exit 1
fi

# ---- Deps + first build ------------------------------------------------------

[[ -d "$FRONTEND_DIR/node_modules" ]] || (cd "$FRONTEND_DIR" && yarn install)
(cd "$BACKEND_DIR" && cargo fetch)

"$SCRIPT_DIR/build.sh"

# Downloads the Qwen3-ASR speech model (backend/models/, ~1.8GB) here, while
# connectivity is available — otherwise it'd download on the first run.sh
# launch instead, risking a timeout on run.sh's READY_TIMEOUT_SECS. No-op
# if already cached, so safe to re-run.
(cd "$BACKEND_DIR" && cargo run --release --example fetch_model --offline)

# ---- LaunchAgent -------------------------------------------------------------

PLIST_NAME="com.pp1.traces.plist"
TEMPLATE_PLIST="$SCRIPT_DIR/$PLIST_NAME.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

if [[ ! -x "$CHROME_BIN" ]]; then
  echo "WARNING: Google Chrome not found at: $CHROME_BIN" >&2
  echo "  Install it, then re-run this script to register TRACES." >&2
  exit 0
fi

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"

if launchctl list | grep -q "com.pp1.traces"; then
  launchctl unload "$DEST_PLIST" 2>/dev/null || true
fi

sed -e "s#__ROOT_DIR__#$ROOT_DIR#g" -e "s#__LOG_DIR__#$LOG_DIR#g" "$TEMPLATE_PLIST" > "$DEST_PLIST"
launchctl load "$DEST_PLIST"

echo "Installed. The kiosk will now start automatically at login."
