#!/usr/bin/env python3
"""
Last check before deploying the database to a kiosk.

Blocking errors (exit code 1):
  - a media file used by an artwork is missing from assets/;
  - an artwork has no vector (compute_embeddings.py was not run): the kiosk
    server does not start if a single vector is missing.
Warnings:
  - artwork without a title or description in one of the three languages;
  - object type without a translation;
  - files in assets/ that no artwork uses.

Usage:
    python check_collection.py --db pp1_collection.db --images ../assets
"""
import argparse
import sqlite3
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--db', required=True)
ap.add_argument('--images', required=True, help='the repository assets/ folder')
a = ap.parse_args()

if not Path(a.images).is_dir():
    raise SystemExit(f'media folder not found: {a.images}')
if not Path(a.db).is_file():
    raise SystemExit(f'database not found: {a.db}')
files = {p.name for p in Path(a.images).iterdir() if p.is_file()}
con = sqlite3.connect(a.db)
errors = 0

missing, used = [], set()
for aid, mu, th in con.execute('SELECT id, media_url, thumbnail_url FROM artworks'):
    for m in [x.strip() for x in (mu or '').split(',') if x.strip()] + ([th] if th else []):
        used.add(m)
        if m not in files and (aid, m) not in missing:
            missing.append((aid, m))
no_media = [r[0] for r in con.execute("SELECT id FROM artworks WHERE media_url IS NULL OR media_url = ''")]
print(f'missing media files: {len(missing)}')
for aid, m in missing:
    print(f'    artwork {aid}: {m}')
errors += len(missing)
if no_media:
    print(f'artworks without any media: {no_media}')

no_vec = [r[0] for r in con.execute('SELECT id FROM artworks WHERE description_vector IS NULL')]
print(f'artworks without a vector: {len(no_vec)}' + (f' {no_vec[:20]} → run compute_embeddings.py' if no_vec else ''))
errors += len(no_vec)

untranslated = [r[0] for r in con.execute('''
    SELECT id FROM artworks
    WHERE coalesce(title_fr, '') = '' OR coalesce(title_nl, '') = '' OR coalesce(title_en, '') = ''
       OR coalesce(description_fr, '') = '' OR coalesce(description_nl, '') = '' OR coalesce(description_en, '') = '' ''')]
print(f'{"⚠ " if untranslated else ""}artworks without a title or description in all 3 languages: {len(untranslated)}'
      + (f' {untranslated[:20]} → run translate_collection.py, then import_translations.py' if untranslated else ''))
types = [r[0] for r in con.execute('''SELECT name FROM types_of_object
    WHERE coalesce(name_fr, '') = '' OR coalesce(name_nl, '') = '' OR coalesce(name_en, '') = '' ''')]
if types:
    print(f'⚠ object types without a translation: {types}')

unused = sorted(f for f in files - used if not f.startswith('.'))
print(f'{"⚠ " if unused else ""}files in assets/ that no artwork uses: {len(unused)}')
for o in unused[:30]:
    print('   ', o)
if len(unused) > 30:
    print(f'    … and {len(unused) - 30} more')

print('\nDATABASE READY TO DEPLOY' if not errors else f'\n{errors} BLOCKING ERROR(S): do not deploy this database')
raise SystemExit(1 if errors else 0)
