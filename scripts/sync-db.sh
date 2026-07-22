#!/bin/bash
#
# Pushes the kiosk's live db (visitors, testimonies, summaries collected
# since the last sync) to origin/main. Run manually every so often —
# there's no timer wired up for this, same as the other scripts here.
#
# Needs connectivity. Does NOT pull first: update.sh is what reconciles
# with origin (and always keeps the local db over origin's, see the note
# there), so this script only ever commits + pushes forward.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

[[ -f "$DATABASE_PATH" ]] || { echo "database not found: $DATABASE_PATH" >&2; exit 1; }

if git -C "$ROOT_DIR" diff --quiet -- "$DATABASE_PATH" && git -C "$ROOT_DIR" diff --cached --quiet -- "$DATABASE_PATH"; then
  echo "No local db changes to sync."
  exit 0
fi

git -C "$ROOT_DIR" add -- "$DATABASE_PATH"
git -C "$ROOT_DIR" commit -m "Sync db from $(hostname -s) ($(date '+%Y-%m-%d %H:%M'))"
git -C "$ROOT_DIR" push

echo "Pushed db changes to origin."
