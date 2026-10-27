#!/usr/bin/env python3
"""
Fusionne les données collectées sur un kiosque (visiteurs, témoignages,
consultations, résumés) dans une nouvelle version de la base de référence.

Contexte : la base du kiosque et celle du repo divergent — le kiosque détient
les données du public, le repo détient la collection à jour (230 œuvres).
`update.sh` conserve toujours la base locale du kiosque : les nouvelles œuvres
n'arrivent donc jamais en production sans cette fusion.

Le script NE MODIFIE NI L'UNE NI L'AUTRE des bases fournies : il écrit une
troisième base, à déployer ensuite sur le kiosque.

Points traités :
  - collision d'ids : sur un kiosque antérieur à la V8, les témoignages
    visiteurs sont numérotés à partir de 1, or ces ids appartiennent désormais
    aux interviews. Les témoignages visiteurs reçoivent de nouveaux ids ;
    `summaries.visitor_id` et `visitor_artwork_views` suivent (ils référencent
    le visiteur, pas le témoignage).
  - œuvres disparues : une consultation pointant vers une œuvre absente de la
    nouvelle base (l'œuvre 15, retirée en V7) est ignorée ; un témoignage dans
    ce cas est exporté dans `temoignages_orphelins.csv` pour rattachement
    manuel — jamais supprimé silencieusement.
  - les interviews de la nouvelle base ne sont jamais touchées.

Usage :
    python merge_kiosk_data.py <kiosk.db> <nouvelle.db> <sortie.db>
"""
import shutil
import sqlite3
import sys


def table_exists(cur, name):
    return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (name,)).fetchone() is not None


def columns(cur, table):
    return [r[1] for r in cur.execute(f'PRAGMA table_info({table})')]


def main(kiosk_path, new_path, out_path):
    shutil.copy(new_path, out_path)
    out = sqlite3.connect(out_path)
    out.execute('PRAGMA foreign_keys = OFF')
    cur = out.cursor()
    cur.execute("ATTACH DATABASE ? AS kiosk", (kiosk_path,))
    report, warn = [], []

    valid_artworks = {r[0] for r in cur.execute('SELECT id FROM artworks')}

    # ── garde-fou : la base de sortie ne doit contenir aucune donnée publique ──
    for t in ('visitors', 'visitor_artwork_views', 'summaries'):
        n = cur.execute(f'SELECT COUNT(*) FROM main.{t}').fetchone()[0]
        if n:
            raise SystemExit(f'ABORTED: the reference database already has {n} row(s) in {t} '
                             '(risk of duplicates).')

    # ── 1. visiteurs ──
    kiosk_cols = [r[1] for r in cur.execute('PRAGMA kiosk.table_info(visitors)')]
    cols = [c for c in columns(cur, 'visitors') if c in kiosk_cols]
    cur.execute(f"INSERT INTO main.visitors ({','.join(cols)}) SELECT {','.join(cols)} FROM kiosk.visitors")
    report.append(f'visitors kept: {cur.rowcount}')

    # ── 2. consultations ──
    rows = cur.execute('SELECT visitor_id, artwork_id, viewed_at FROM kiosk.visitor_artwork_views').fetchall()
    kept = dropped = 0
    for vid, aid, seen in rows:
        if aid not in valid_artworks:
            warn.append(f'view of artwork {aid} (not in the new database): ignored')
            dropped += 1
            continue
        cur.execute('INSERT INTO main.visitor_artwork_views (visitor_id, artwork_id, viewed_at) VALUES (?,?,?)',
                    (vid, aid, seen))
        kept += 1
    report.append(f'artwork views kept: {kept}' + (f', ignored: {dropped}' if dropped else ''))

    # ── 3. témoignages visiteurs (nouveaux ids) ──
    k_cols = columns(cur, 'testimonies')            # colonnes de la base cible
    src_cols = [r[1] for r in cur.execute('PRAGMA kiosk.table_info(testimonies)')]
    shared = [c for c in k_cols if c in src_cols and c != 'id']
    # sur un kiosque pré-V8, testimonies ne contient que des témoignages visiteurs ;
    # sur un kiosque V8+, on ne reprend que ceux qui ont un visitor_id.
    where = 'WHERE visitor_id IS NOT NULL'
    rows = cur.execute(f"SELECT {','.join(shared)} FROM kiosk.testimonies {where}").fetchall()
    next_id = (cur.execute('SELECT COALESCE(MAX(id), 0) FROM main.testimonies').fetchone()[0]) + 1
    moved = orphan = 0
    a_idx = shared.index('artwork_id') if 'artwork_id' in shared else None
    orphans = []
    for row in rows:
        values = list(row)
        if a_idx is not None and values[a_idx] not in valid_artworks:
            # artwork_id est NOT NULL : impossible de l'insérer sans référence valide.
            # Le témoignage est mis de côté dans un CSV plutôt que perdu ou corrompu.
            orphans.append(dict(zip(shared, values)))
            orphan += 1
            continue
        cur.execute(f"INSERT INTO main.testimonies (id,{','.join(shared)}) VALUES ({','.join(['?'] * (len(shared) + 1))})",
                    [next_id] + values)
        next_id += 1
        moved += 1
    if orphans:
        import csv
        from pathlib import Path
        csv_path = Path(out_path).with_name('temoignages_orphelins.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=shared)
            w.writeheader()
            w.writerows(orphans)
        warn.append(f'{len(orphans)} testimony(ies) about an artwork missing from the new database: '
                    f'NOT imported, saved to {csv_path.name} to be attached to another artwork by hand')
    report.append(f'visitor testimonies kept: {moved} (new ids from {next_id - moved})'
                  + (f', {orphan} set aside (see the CSV)' if orphan else ''))

    # ── 4. résumés ──
    if table_exists(cur, 'summaries'):
        cur.execute('INSERT INTO main.summaries (visitor_id, content, created_at) '
                    'SELECT visitor_id, content, created_at FROM kiosk.summaries')
        report.append(f'visit summaries kept: {cur.rowcount}')

    # ── 5. modérateurs éventuels ──
    if table_exists(cur, 'staff'):
        n = cur.execute('SELECT COUNT(*) FROM kiosk.staff').fetchone()[0]
        if n:
            cur.execute('INSERT OR IGNORE INTO main.staff SELECT * FROM kiosk.staff')
            report.append(f'staff accounts kept: {n}')

    out.commit()

    # ── contrôles finaux ──
    interviews = cur.execute('SELECT COUNT(*) FROM main.testimonies WHERE visitor_id IS NULL').fetchone()[0]
    visiteurs = cur.execute('SELECT COUNT(*) FROM main.testimonies WHERE visitor_id IS NOT NULL').fetchone()[0]
    artworks = cur.execute('SELECT COUNT(*) FROM main.artworks').fetchone()[0]
    report.append(f'result: {artworks} artworks, {interviews} interviews, {visiteurs} visitor testimonies')
    broken = cur.execute('''SELECT COUNT(*) FROM main.testimonies t
                            LEFT JOIN main.artworks a ON a.id = t.artwork_id
                            WHERE t.artwork_id IS NOT NULL AND a.id IS NULL''').fetchone()[0]
    report.append(f'broken artwork references: {broken}')

    # vectors come from the reference database (artworks is never changed
    # here). Without them the kiosk server does not start: blocking.
    vec = cur.execute('SELECT COUNT(description_vector) FROM main.artworks').fetchone()[0]
    report.append(f'embedding vectors: {vec}/{artworks}')

    cur.execute('DETACH DATABASE kiosk')
    out.close()
    print('\n'.join('  • ' + r for r in report))
    for w in dict.fromkeys(warn):
        print('  ⚠ ' + w)
    if vec < artworks:
        raise SystemExit(f'ABORTED: {artworks - vec} artwork(s) without a vector in the repository database: '
                         'the kiosk server would not start. Nothing was changed. Run compute_embeddings.py '
                         'on the work computer, push, then run update.sh and this script again.')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
