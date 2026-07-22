#!/bin/bash
#
# One-time setup, run with internet connectivity: toolchains, deps, first
# build, and the login LaunchAgent. Safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend project not found: $BACKEND_DIR" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Frontend project not found: $FRONTEND_DIR" >&2
  exit 1
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
