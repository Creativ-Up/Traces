#!/usr/bin/env python3
"""
Migration V11 de pp1_collection.db (PP1/Photomaton)
Remplace les photos des 4 œuvres du Fresnoy par leur extrait vidéo :
  1 « I made you I kill you », 2 « Isabelle Morra », 3 « Odamado », 4 « Abena ».

- media_url  : remplacé par le nom du fichier vidéo (.mp4, normalisé)
- thumbnail_url : CONSERVÉ tel quel (la vignette reste la photo actuelle,
  le front l'affiche dans la grille ; une vidéo n'y est jamais affichée)

Les vidéos doivent avoir été préparées (prepare_media.py : MP4 H.264, nom
normalisé) et copiées dans assets/ avant de lancer ce script : il refuse de
pointer vers un fichier absent.

Usage :
    python migrate_v11.py <db> <dossier assets> 1=<v1.mp4> 2=<v2.mp4> 3=<v3.mp4> 4=<v4.mp4>
Idempotent : relancé avec les mêmes arguments, il ne change rien.
"""
import re
import sqlite3
import sys
from pathlib import Path

FRESNOY_IDS = {1, 2, 3, 4}


def normalize(name: str) -> str:
    """Même convention que migrate_v3 / prepare_media (extension préservée)."""
    s = name.strip().lower()
    if not s.endswith('.mp4'):
        raise SystemExit(f'« {name} » : une vidéo .mp4 est attendue')
    stem = s[:-4]
    stem = re.sub(r'[_.\s]+', '-', stem)
    stem = re.sub(r'[^a-z0-9-]', '', stem)
    return re.sub(r'-{2,}', '-', stem).strip('-') + '.mp4'


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    db, assets = sys.argv[1], Path(sys.argv[2])
    mapping = {}
    for arg in sys.argv[3:]:
        aid, _, fname = arg.partition('=')
        if not aid.isdigit() or int(aid) not in FRESNOY_IDS or not fname:
            raise SystemExit(f'argument invalide : {arg!r} (attendu 1=…, 2=…, 3=… ou 4=…)')
        mapping[int(aid)] = normalize(fname)

    missing = [f for f in mapping.values() if not (assets / f).is_file()]
    if missing:
        raise SystemExit(f'fichier(s) absent(s) de {assets} : {missing} — '
                         'copier les vidéos préparées dans assets/ d’abord')

    con = sqlite3.connect(db)
    cur = con.cursor()
    for aid, video in sorted(mapping.items()):
        row = cur.execute('SELECT title, media_url, thumbnail_url FROM artworks WHERE id=?',
                          (aid,)).fetchone()
        if row is None:
            raise SystemExit(f'œuvre {aid} introuvable')
        title, old, thumb = row
        if not thumb or thumb.endswith('.mp4'):
            raise SystemExit(f'œuvre {aid} : vignette invalide ({thumb!r}), migration interrompue')
        if old == video:
            print(f'  • {aid} « {title} » : déjà à jour ({video})')
            continue
        cur.execute('UPDATE artworks SET media_url=? WHERE id=?', (video, aid))
        print(f'  • {aid} « {title} » : {video} (vignette conservée : {thumb})')
    con.commit()
    con.close()


if __name__ == '__main__':
    main()
