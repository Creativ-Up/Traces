#!/usr/bin/env python3
"""
Migration V5 of pp1_collection.db (PP1/Photomaton)
- Fixes artworks.media_url: migrate_v3.py's normalize_media_name stripped the
  extension's dot along with underscores/spaces (regex `[_.\\s]+` -> '-'),
  leaving entries like 'imadeyou-01-053-jpg' instead of the real filename
  'imadeyou-01-053.jpg'. The V3 docstring expected a separate
  sync_images_local.py to re-append real extensions afterward, but that
  script was never added to this repo, so media_url was committed mid-pipeline.
  This restores the real extension by replacing the last '-' with '.'
  (verified against all 261 files in pictures_data_renamed.zip: exact match,
  0 unresolved). thumbnail_url is untouched: it was already correct.
Usage: python migrate_v5.py <db_path>
"""
import sys
import sqlite3

DB = sys.argv[1] if len(sys.argv) > 1 else 'pp1_collection.db'


def fix_media_name(name: str) -> str:
    # Already has a real extension (from a previous run, or was never broken) -> leave alone.
    if name.endswith('.jpg'):
        return name
    i = name.rfind('-')
    return name[:i] + '.' + name[i + 1:] if i != -1 else name


def fix_media_url(value):
    if not value:
        return value
    parts = [fix_media_name(p.strip()) for p in str(value).split(',')]
    return ', '.join(parts)


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    report = []

    changed = 0
    already_ok = 0
    for aid, mu in cur.execute('SELECT id, media_url FROM artworks WHERE media_url IS NOT NULL').fetchall():
        fixed = fix_media_url(mu)
        if fixed == mu:
            already_ok += 1
            continue
        cur.execute('UPDATE artworks SET media_url=? WHERE id=?', (fixed, aid))
        changed += 1
    report.append(f'media_url fixed (dash -> dot extension): {changed} rows, {already_ok} already correct')

    con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in report))


if __name__ == '__main__':
    main()
