#!/bin/zsh
#
# Starts the backend, waits for it to be ready, opens Chrome in kiosk mode.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${0:A}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SERVER_LOG="$LOG_DIR/server.log"
SERVER_URL="http://127.0.0.1:${SERVER_PORT}/api"
KIOSK_URL="http://127.0.0.1:${SERVER_PORT}/"
READY_TIMEOUT_SECS=120

mkdir -p "$LOG_DIR"

if PREV_PID=$(lsof -ti "tcp:$SERVER_PORT" 2>/dev/null); then
  kill $PREV_PID 2>/dev/null || true
  sleep 1
fi
pkill -f "user-data-dir=$CHROME_KIOSK_PROFILE" 2>/dev/null || true

[[ -x "$BACKEND_BINARY" ]] || { echo "$(date) FATAL: server binary not found: $BACKEND_BINARY" | tee -a "$SERVER_LOG" >&2; exit 1; }
[[ -x "$CHROME_BIN" ]] || { echo "$(date) FATAL: Chrome not found: $CHROME_BIN" | tee -a "$SERVER_LOG" >&2; exit 1; }
[[ -d "$FRONTEND_BUILD_DIR" ]] || { echo "$(date) FATAL: frontend build not found: $FRONTEND_BUILD_DIR" | tee -a "$SERVER_LOG" >&2; exit 1; }
[[ -d "$ASSETS_DIR" ]] || { echo "$(date) FATAL: assets not found: $ASSETS_DIR" | tee -a "$SERVER_LOG" >&2; exit 1; }
[[ -f "$DATABASE_PATH" ]] || { echo "$(date) FATAL: database not found: $DATABASE_PATH" | tee -a "$SERVER_LOG" >&2; exit 1; }

export SERVER_FRONTEND_DIR_VAR="$FRONTEND_BUILD_DIR"
export SERVER_ASSETS_DIR_VAR="$ASSETS_DIR"
export SERVER_DATABASE_PATH_VAR="$DATABASE_PATH"
export ROCKET_PROFILE
export ROCKET_PORT="$SERVER_PORT"

cd "$BACKEND_DIR"

echo "$(date) starting server binary: $BACKEND_BINARY" >> "$SERVER_LOG"
"$BACKEND_BINARY" >> "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

elapsed=0
until curl --silent --fail --max-time 2 "$SERVER_URL" >/dev/null 2>&1; do
  kill -0 "$SERVER_PID" 2>/dev/null || { echo "$(date) server process died before becoming ready" >> "$SERVER_LOG"; exit 1; }
  if [ "$elapsed" -ge "$READY_TIMEOUT_SECS" ]; then
    echo "$(date) timed out waiting for server after ${READY_TIMEOUT_SECS}s" >> "$SERVER_LOG"
    exit 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

echo "$(date) server ready after ${elapsed}s" >> "$SERVER_LOG"

mkdir -p "$CHROME_KIOSK_PROFILE"

"$CHROME_BIN" \
  --user-data-dir="$CHROME_KIOSK_PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  --kiosk \
  --autoplay-policy=no-user-gesture-required \
  --disable-session-crashed-bubble \
  --disable-infobars \
  --noerrdialogs \
  --overscroll-history-navigation=0 \
  --remote-debugging-port="$CHROME_REMOTE_DEBUGGING_PORT" \
  "$KIOSK_URL" \
  >/dev/null 2>&1 &
CHROME_PID=$!

# Nudge the OS cursor once the window is up so the kiosk CSS (cursor: none)
# actually takes effect, instead of leaving a stale visible cursor on screen
# until a visitor touches the input device. Move-only (no click) to avoid
# triggering any on-screen control. 300,300 avoids the top-left corner,
# where the menu bar can intercept a 0,0 move.
if command -v cliclick >/dev/null 2>&1; then
  (sleep 3 && cliclick m:300,300) &
else
  echo "$(date) WARNING: cliclick not found, cursor may stay visible until first input" | tee -a "$SERVER_LOG" >&2
fi

wait "$SERVER_PID" "$CHROME_PID"
