#!/usr/bin/env python3
"""
Migration V8 de pp1_collection.db (PP1/Photomaton)
Fusionne les témoignages enregistrés (interviews) dans la table `testimonies`,
que le backend lit directement — le kiosk les affiche donc sans changement de
code. La table `recorded_testimonies` est ensuite supprimée (une seule source
de vérité).

Représentation d'une interview dans `testimonies` :
  - visitor_id = NULL            (pas de visiteur : c'est le discriminant)
  - id         = id historique   (préservé -> RECORDED_IDS de migrate_v3.py
                                  reste valable tel quel)
  - content    = texte dans la langue source ; content_fr/nl/en = traductions
  - status     = 'validated', consent_given = 1  (validées par le musée)
  - city / created_at / source_lang / artwork_id : repris tels quels

La vue artwork_published_testimonies est recréée sur la seule table
`testimonies` (kind déduit de visitor_id).

Usage : python migrate_v8.py <db_path> — idempotent (2e passage : rien à faire).
"""
import sys
import sqlite3

DB = sys.argv[1] if len(sys.argv) > 1 else 'pp1_collection.db'


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    report = []

    has_recorded = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='recorded_testimonies'"
    ).fetchone()[0]
    if not has_recorded:
        print('  • recorded_testimonies déjà fusionnée : rien à faire')
        return

    # ── garde-fous ──────────────────────────────────────────────────────
    unassigned = cur.execute(
        'SELECT COUNT(*) FROM recorded_testimonies WHERE artwork_id IS NULL').fetchone()[0]
    if unassigned:
        raise SystemExit(f'⚠ {unassigned} interview(s) sans artwork_id (V6 non appliquée ?) — abandon.')
    collisions = cur.execute('''SELECT COUNT(*) FROM recorded_testimonies rt
                                JOIN testimonies t ON t.id = rt.id''').fetchone()[0]
    if collisions:
        raise SystemExit(f'⚠ {collisions} id(s) en collision avec testimonies — abandon (ids historiques non préservables).')

    # ── transfert (ids préservés) ───────────────────────────────────────
    n = cur.execute('''
        INSERT INTO testimonies (id, visitor_id, artwork_id, content, source_lang,
                                 content_fr, content_nl, content_en,
                                 status, consent_given, created_at, city)
        SELECT id, NULL, artwork_id,
               CASE source_lang WHEN 'nl' THEN content_nl
                                WHEN 'en' THEN content_en
                                ELSE content_fr END,
               source_lang, content_fr, content_nl, content_en,
               'validated', 1, created_at, city
        FROM recorded_testimonies
    ''').rowcount
    report.append(f'{n} interviews transférées dans testimonies (visitor_id NULL, ids historiques préservés)')

    cur.execute('DROP TABLE recorded_testimonies')
    report.append('table recorded_testimonies supprimée')

    # ── vue : une seule source ──────────────────────────────────────────
    cur.executescript("""
DROP VIEW IF EXISTS artwork_published_testimonies;
CREATE VIEW artwork_published_testimonies AS
SELECT
    t.artwork_id    AS artwork_id,
    CASE WHEN t.visitor_id IS NULL THEN 'recorded' ELSE 'visitor' END AS kind,
    t.id            AS source_id,
    t.city          AS city,          -- interviews : ville de collecte ; visiteurs : site d'installation
    t.created_at    AS created_at,
    t.source_lang   AS source_lang,
    t.content_fr    AS content_fr,
    t.content_nl    AS content_nl,
    t.content_en    AS content_en
FROM testimonies t
WHERE t.status = 'validated'
  AND t.consent_given = 1;
""")
    report.append('vue artwork_published_testimonies recréée (source unique : testimonies)')

    con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in report))


if __name__ == '__main__':
    main()
