#!/usr/bin/env python3
"""Contrôle d'intégrité DB <-> dossier d'images (PP1).
Usage: python check_images.py --db pp1_collection.db --images <dossier>"""
import argparse, sqlite3
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--db', required=True); ap.add_argument('--images', required=True)
a = ap.parse_args()
files = {p.name for p in Path(a.images).iterdir() if p.is_file()}
con = sqlite3.connect(a.db)
missing, refd = [], set()
for aid, mu, th in con.execute("SELECT id, media_url, thumbnail_url FROM artworks WHERE media_url IS NOT NULL"):
    for m in [x.strip() for x in mu.split(',')] + ([th] if th else []):
        refd.add(m)
        if m not in files: missing.append((aid, m))
no_img = [r[0] for r in con.execute("SELECT id FROM artworks WHERE media_url IS NULL")]
orphans = sorted(files - refd)
print(f'références manquantes : {len(missing)}'); [print('  ', m) for m in missing]
print(f'œuvres sans image : {no_img}')
print(f'fichiers non référencés : {len(orphans)}'); [print('  ', o) for o in orphans]
raise SystemExit(1 if missing else 0)
