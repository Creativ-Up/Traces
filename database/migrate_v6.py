#!/usr/bin/env python3
"""
Migration V6 de pp1_collection.db (PP1/Photomaton)
Implémente l'option 3 validée par Mathilde (juillet 2026) : chaque témoignage
enregistré est associé à UNE œuvre parmi celles liées à sa question, en
répartition équilibrée (cf. Répartition_témoignages_sources.xlsx).

- Ajoute recorded_testimonies.artwork_id (FK artworks, nullable)
- Attribue chaque témoignage sans œuvre à l'œuvre la moins chargée de sa
  question (départage aléatoire à seed fixe : reproductible). Les
  attributions existantes ne sont jamais modifiées (curation manuelle
  possible ensuite).
- Recrée la vue artwork_published_testimonies : la branche 'recorded' joint
  désormais sur artwork_id (1 témoignage = 1 œuvre) au lieu de question_id
  (qui dupliquait chaque témoignage sous toutes les œuvres de la question).

Usage : python migrate_v6.py <db_path>
Idempotent : un second passage n'attribue rien (0 NULL restant).
"""
import random
import sys
import sqlite3

DB = sys.argv[1] if len(sys.argv) > 1 else 'pp1_collection.db'
SEED = 2026  # fixe -> répartition reproductible


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rng = random.Random(SEED)
    report = []

    # ── 1. colonne artwork_id ───────────────────────────────────────────
    cols = [r[1] for r in cur.execute('PRAGMA table_info(recorded_testimonies)')]
    if 'artwork_id' not in cols:
        cur.execute('ALTER TABLE recorded_testimonies ADD COLUMN artwork_id INTEGER REFERENCES artworks(id)')
        report.append('recorded_testimonies.artwork_id ajoutée')
    else:
        report.append('recorded_testimonies.artwork_id déjà présente')

    # ── 2. répartition équilibrée par question ──────────────────────────
    assigned = 0
    for (q,) in cur.execute('SELECT DISTINCT question_id FROM recorded_testimonies ORDER BY 1').fetchall():
        artworks = [r[0] for r in cur.execute(
            'SELECT id FROM artworks WHERE question_id=? ORDER BY id', (q,))]
        if not artworks:
            report.append(f'⚠ question {q} : aucune œuvre liée, témoignages non attribués')
            continue
        # charge existante (attributions déjà faites, p.ex. curation manuelle)
        load = {a: 0 for a in artworks}
        for a, n in cur.execute('''SELECT artwork_id, COUNT(*) FROM recorded_testimonies
                                   WHERE question_id=? AND artwork_id IS NOT NULL
                                   GROUP BY artwork_id''', (q,)):
            if a in load:
                load[a] = n
        todo = [r[0] for r in cur.execute('''SELECT id FROM recorded_testimonies
                                             WHERE question_id=? AND artwork_id IS NULL
                                             ORDER BY id''', (q,))]
        rng.shuffle(todo)  # l'ordre d'attribution ne suit pas l'ordre des ids
        for tid in todo:
            mn = min(load.values())
            candidates = [a for a, n in load.items() if n == mn]
            target = rng.choice(candidates)
            cur.execute('UPDATE recorded_testimonies SET artwork_id=? WHERE id=?', (target, tid))
            load[target] += 1
            assigned += 1
        dist = sorted(load.values(), reverse=True)
        report.append(f'question {q:2} : {sum(dist)} témoignages sur {len(artworks)} œuvre(s) '
                      f'(par œuvre : max {dist[0]}, min {dist[-1]})')
    report.append(f'attributions effectuées ce passage : {assigned}')
    left = cur.execute('SELECT COUNT(*) FROM recorded_testimonies WHERE artwork_id IS NULL').fetchone()[0]
    report.append(f'témoignages sans œuvre restants : {left}')

    # ── 3. vue : 1 témoignage = 1 œuvre ─────────────────────────────────
    cur.executescript("""
DROP VIEW IF EXISTS artwork_published_testimonies;
CREATE VIEW artwork_published_testimonies AS
SELECT
    rt.artwork_id   AS artwork_id,
    'recorded'      AS kind,
    rt.id           AS source_id,     -- id dans recorded_testimonies
    rt.city         AS city,          -- identification du témoignage : ville…
    rt.created_at   AS created_at,    -- …et date (anonymisation V3.1)
    rt.source_lang  AS source_lang,
    rt.content_fr   AS content_fr,
    rt.content_nl   AS content_nl,
    rt.content_en   AS content_en
FROM recorded_testimonies rt
WHERE rt.artwork_id IS NOT NULL     -- V6 : liaison directe (option 3), plus de duplication par question
UNION ALL
SELECT
    t.artwork_id    AS artwork_id,
    'visitor'       AS kind,
    t.id            AS source_id,     -- id dans testimonies
    t.city          AS city,          -- ville du site d'installation (renseignée par le backend)
    t.created_at    AS created_at,
    t.source_lang   AS source_lang,
    t.content_fr    AS content_fr,
    t.content_nl    AS content_nl,
    t.content_en    AS content_en
FROM testimonies t
WHERE t.status = 'validated'
  AND t.consent_given = 1;
""")
    report.append('vue artwork_published_testimonies recréée (liaison directe artwork_id)')

    con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in report))


if __name__ == '__main__':
    main()
