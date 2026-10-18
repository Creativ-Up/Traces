#!/bin/bash
#
# Applies the repo's reference database (new artworks, translations, media)
# to this kiosk WITHOUT losing the data collected on site.
#
# update.sh always keeps the kiosk's local db over origin's — the right call
# for code updates, but it means a new collection never reaches production.
# This script is the deliberate, manual exception: run it only when the
# collection itself has changed (new museum, new artworks).
#
# RUN IT RIGHT AFTER update.sh: after the pull, HEAD holds the new reference
# db while the working copy still holds the kiosk's live db (restored by
# update.sh). This script merges the two.
#
# What it does, in order:
#   1. stops the backend (it holds the db open)
#   2. backs the live db up to the Desktop (SQLite backup API, not a raw cp)
#   3. merges the kiosk's dynamic data (visitors, testimonies, views,
#      summaries) into the reference db taken from HEAD
#   4. swaps it in, after printing the report for a human to read
#
# It deliberately does NOT call sync-db.sh: the repo is public, and the live
# db contains visitors' testimonies. They must not be pushed to GitHub.
#
# The backend is NOT restarted: reboot the Mac mini once done.
# Offline-safe: needs no connectivity (update.sh already fetched everything).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

MERGE_SCRIPT="$SCRIPT_DIR/merge_kiosk_data.py"
STAMP="$(date '+%Y%m%d-%H%M')"
BACKUP="$HOME/Desktop/kiosk_db_backup_$STAMP.db"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/traces_merge.XXXXXX")"
NEW_DB="$WORK_DIR/reference.db"
MERGED="$WORK_DIR/merged.db"

[[ -f "$DATABASE_PATH" ]] || { echo "database not found: $DATABASE_PATH" >&2; exit 1; }
[[ -f "$MERGE_SCRIPT" ]] || { echo "merge script not found: $MERGE_SCRIPT" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required (xcode-select --install)" >&2; exit 1; }

# Row counts, via python3 (no dependency on the sqlite3 CLI).
count() {  # count <db> <sql>
  python3 -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute(sys.argv[2]).fetchone()[0])" "$1" "$2"
}

# ── 1. stop the backend ────────────────────────────────────────────────
# Cmd+Q only quits Chrome; the backend keeps running and keeps the db open.
# The LaunchAgent has KeepAlive=false, so it won't respawn.
if pids="$(lsof -ti "tcp:$SERVER_PORT" 2>/dev/null)"; then
  echo "Stopping backend (pid $pids)..."
  # shellcheck disable=SC2086
  kill $pids
  sleep 2
fi
if lsof -ti "tcp:$SERVER_PORT" >/dev/null 2>&1; then
  echo "ABORTED: the backend is still running on port $SERVER_PORT." >&2
  exit 1
fi

# ── 2. back up what only exists here ───────────────────────────────────
python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close()" \
  "$DATABASE_PATH" "$BACKUP"
echo "Backup of the live db: $BACKUP"
echo "  -> copy it to a USB key before going further."
echo

BEFORE="$(count "$DATABASE_PATH" "SELECT COUNT(*) FROM testimonies WHERE visitor_id IS NOT NULL")"
KIOSK_ART="$(count "$DATABASE_PATH" "SELECT COUNT(*) FROM artworks")"

# ── 3. merge ───────────────────────────────────────────────────────────
git -C "$ROOT_DIR" show "HEAD:$DATABASE_PATH_NAME" > "$NEW_DB"
REF_ART="$(count "$NEW_DB" "SELECT COUNT(*) FROM artworks")"

echo "Live db (kiosk)      : $KIOSK_ART artworks, $BEFORE visitor testimonies"
echo "Reference db (repo)  : $REF_ART artworks"
if [[ "$REF_ART" -le "$KIOSK_ART" ]]; then
  echo
  echo "WARNING: the reference db has no more artworks than the kiosk." >&2
  echo "Did you run update.sh first? Continue anyway? [y/N]" >&2
  read -r answer
  [[ "$answer" == "y" ]] || { echo "Aborted — nothing was changed."; exit 1; }
fi
echo

python3 "$MERGE_SCRIPT" "$DATABASE_PATH" "$NEW_DB" "$MERGED"
echo

AFTER="$(count "$MERGED" "SELECT COUNT(*) FROM testimonies WHERE visitor_id IS NOT NULL")"
ORPHANS="$(dirname "$MERGED")/temoignages_orphelins.csv"
if [[ -f "$ORPHANS" ]]; then
  cp "$ORPHANS" "$HOME/Desktop/temoignages_orphelins_$STAMP.csv"
  ORPHAN_N=$(( $(wc -l < "$ORPHANS") - 1 ))
  echo "$ORPHAN_N testimony(ies) set aside: $HOME/Desktop/temoignages_orphelins_$STAMP.csv"
else
  ORPHAN_N=0
fi
if [[ $(( AFTER + ORPHAN_N )) -lt "$BEFORE" ]]; then
  echo "ABORTED: merged db has $AFTER visitor testimonies (+$ORPHAN_N set aside), kiosk had $BEFORE." >&2
  echo "Nothing was changed. Backup: $BACKUP" >&2
  exit 1
fi

# ── 4. swap in ─────────────────────────────────────────────────────────
echo "Read the report above. Apply this database to the kiosk? [y/N]"
read -r answer
[[ "$answer" == "y" ]] || { echo "Aborted — nothing was changed. Backup: $BACKUP"; exit 1; }

cp "$MERGED" "$DATABASE_PATH"
rm -f "$DATABASE_PATH-journal"
echo
echo "Done: $REF_ART artworks, $AFTER visitor testimonies kept."
echo "Backup kept at: $BACKUP"
echo "Reboot the Mac mini to restart the kiosk."
