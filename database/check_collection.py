#!/usr/bin/env python3
"""
Dernier contrôle avant de déployer la base sur un kiosque.

Erreurs bloquantes (code de sortie 1) :
  - un média cité par une œuvre est absent du dossier assets/ ;
  - une œuvre n'a pas de vecteur (compute_embeddings.py non relancé) : le
    serveur du kiosque ne démarre pas s'il manque un seul vecteur.
Avertissements :
  - œuvre sans titre ou sans description dans l'une des trois langues ;
  - type d'objet sans traduction ;
  - fichiers de assets/ qu'aucune œuvre ne cite.

Usage :
    python check_collection.py --db pp1_collection.db --images ../assets
"""
import argparse
import sqlite3
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--db', required=True)
ap.add_argument('--images', required=True, help='dossier assets/ du repo')
a = ap.parse_args()

if not Path(a.images).is_dir():
    raise SystemExit(f'dossier de médias introuvable : {a.images}')
if not Path(a.db).is_file():
    raise SystemExit(f'base introuvable : {a.db}')
files = {p.name for p in Path(a.images).iterdir() if p.is_file()}
con = sqlite3.connect(a.db)
errors = 0

missing, refd = [], set()
for aid, mu, th in con.execute('SELECT id, media_url, thumbnail_url FROM artworks'):
    for m in [x.strip() for x in (mu or '').split(',') if x.strip()] + ([th] if th else []):
        refd.add(m)
        if m not in files and (aid, m) not in missing:
            missing.append((aid, m))
no_media = [r[0] for r in con.execute("SELECT id FROM artworks WHERE media_url IS NULL OR media_url = ''")]
print(f'médias manquants : {len(missing)}')
for m in missing:
    print('   ', m)
errors += len(missing)
if no_media:
    print(f'œuvres sans média : {no_media}')

no_vec = [r[0] for r in con.execute('SELECT id FROM artworks WHERE description_vector IS NULL')]
print(f'œuvres sans vecteur : {len(no_vec)}' + (f' {no_vec[:20]} → lancer compute_embeddings.py' if no_vec else ''))
errors += len(no_vec)

untranslated = [r[0] for r in con.execute('''
    SELECT id FROM artworks
    WHERE coalesce(title_fr, '') = '' OR coalesce(title_nl, '') = '' OR coalesce(title_en, '') = ''
       OR coalesce(description_fr, '') = '' OR coalesce(description_nl, '') = '' OR coalesce(description_en, '') = '' ''')]
print(f'{"⚠ " if untranslated else ""}œuvres sans titre ou description dans les 3 langues : {len(untranslated)}'
      + (f' {untranslated[:20]} → translate_collection.py puis import_translations.py' if untranslated else ''))
types = [r[0] for r in con.execute('''SELECT name FROM types_of_object
    WHERE coalesce(name_fr, '') = '' OR coalesce(name_nl, '') = '' OR coalesce(name_en, '') = '' ''')]
if types:
    print(f'⚠ types d’objets sans traduction : {types}')

orphans = sorted(f for f in files - refd if not f.startswith('.'))
print(f'{"⚠ " if orphans else ""}fichiers de assets/ qu’aucune œuvre ne cite : {len(orphans)}')
for o in orphans[:30]:
    print('   ', o)
if len(orphans) > 30:
    print(f'    … et {len(orphans) - 30} autres')

print('\nBASE PRÊTE À DÉPLOYER' if not errors else f'\n{errors} ERREUR(S) BLOQUANTE(S) : ne pas déployer cette base')
raise SystemExit(1 if errors else 0)
