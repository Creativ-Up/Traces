#!/bin/bash
#
# Unregisters the TRACES LaunchAgent so it no longer starts at login.
# Does not remove backend/, frontend/, assets/, or any built artifacts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PLIST_NAME="com.pp1.traces.plist"
DEST_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

if launchctl list | grep -q "com.pp1.traces"; then
  launchctl unload "$DEST_PLIST" 2>/dev/null || true
fi

rm -f "$DEST_PLIST"

echo "TRACES will no longer start at login."
