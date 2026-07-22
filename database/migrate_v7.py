#!/usr/bin/env python3
"""
Migration V7 de pp1_collection.db (PP1/Photomaton)
Retire l'œuvre 15 (MSK_1199) : aucune photo n'existe pour elle (ni référence
dans l'Excel du musée, ni fichier dans le dossier d'images) — retrait validé.
C'était aussi la seule œuvre sans question associée.

- Supprime ses lignes dépendantes (artwork_emotions), puis l'œuvre.
- Garde-fou : refuse la suppression si des données runtime (témoignages
  visiteurs, vues) y sont rattachées.

Usage : python migrate_v7.py <db_path> — idempotent.
"""
import sys
import sqlite3

DB = sys.argv[1] if len(sys.argv) > 1 else 'pp1_collection.db'
ARTWORK_ID = 15


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    report = []

    exists = cur.execute('SELECT COUNT(*) FROM artworks WHERE id=?', (ARTWORK_ID,)).fetchone()[0]
    if not exists:
        print(f'  • œuvre {ARTWORK_ID} déjà absente : rien à faire')
        return

    # garde-fou : données runtime rattachées ?
    runtime = cur.execute('''SELECT
        (SELECT COUNT(*) FROM testimonies WHERE artwork_id=:a) +
        (SELECT COUNT(*) FROM visitor_artwork_views WHERE artwork_id=:a) +
        (SELECT COUNT(*) FROM recorded_testimonies WHERE artwork_id=:a)''',
        {'a': ARTWORK_ID}).fetchone()[0]
    if runtime:
        raise SystemExit(f'⚠ {runtime} enregistrement(s) rattaché(s) à l’œuvre {ARTWORK_ID} — suppression refusée, réattribuer d’abord.')

    for table in ('artwork_emotions', 'transcriptions'):
        n = cur.execute(f'DELETE FROM {table} WHERE artwork_id=?', (ARTWORK_ID,)).rowcount
        if n:
            report.append(f'{table} : {n} ligne(s) supprimée(s)')
    cur.execute('DELETE FROM artworks WHERE id=?', (ARTWORK_ID,))
    report.append(f'œuvre {ARTWORK_ID} (MSK_1199, sans média) supprimée — {cur.execute("SELECT COUNT(*) FROM artworks").fetchone()[0]} œuvres restantes')

    con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in report))


if __name__ == '__main__':
    main()
