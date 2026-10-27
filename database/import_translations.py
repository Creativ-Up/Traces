#!/usr/bin/env python3
"""
Importe dans la base les textes du classeur de relecture (review_translations.xlsx).

Le classeur est la source de vérité de tous les textes affichés aux visiteurs
en FR / NL / EN. Ce script se relance autant de fois que nécessaire :
  - après translate_collection.py, pour charger les traductions automatiques ;
  - après chaque retour de relecture des partenaires, pour charger leurs
    corrections.

Feuilles lues (une feuille absente est simplement ignorée) :
  Types d'objets, Questions, Descriptions, Description - Key words, Emotions,
  Transcriptions, Transcriptions Explications, Témoignages, Titres.

Une cellule vide ne remplace jamais un texte déjà présent en base : vider une
cellule du classeur ne supprime rien.

Usage :
    python import_translations.py <db> <review_translations.xlsx>
Idempotent : relancé sur le même classeur, il ne change rien.

(Anciennement migrate_v3.py, débarrassé de ses opérations ponctuelles déjà
appliquées : ajout de colonnes, retraits de juillet 2026, etc.)
"""
import re
import sqlite3
import sys

from openpyxl import load_workbook


def clean(value):
    """Le texte de la cellule tel quel, ou None si elle est vide."""
    if value is None or not str(value).strip():
        return None
    return value if isinstance(value, str) else str(value)


def import_lang_sheet(cur, wb, sheet, sql, report, label, source_sql=None):
    """Feuilles au format id | source | fr | nl | en.

    source_sql : requête qui renvoie le texte source actuel en base. Si la
    colonne « source » du classeur ne lui correspond plus (le musée a corrigé
    son texte depuis la traduction), la ligne est laissée de côté : il faut
    d'abord relancer translate_collection.py, sinon d'anciennes traductions
    écraseraient le nouveau texte.
    """
    if sheet not in wb.sheetnames:
        report.append(f'{label} : feuille « {sheet} » absente, ignorée')
        return
    n = miss = 0
    stale = []
    for row in wb[sheet].iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        i, src, fr, nl, en = (list(row) + [None] * 5)[:5]
        if source_sql:
            current = cur.execute(source_sql, (int(i),)).fetchone()
            if current and str(current[0] or '').strip() != str(src or '').strip():
                stale.append(int(i))
                continue
        r = cur.execute(sql, (clean(fr), clean(nl), clean(en), int(i)))
        if r.rowcount:
            n += 1
        else:
            miss += 1
    report.append(f'{label} : {n} ligne(s) importée(s)' + (f', {miss} id(s) sans correspondance' if miss else ''))
    if stale:
        report.append(f'⚠ {label} : {len(stale)} ligne(s) laissée(s) de côté car le texte source a changé '
                      f'depuis la traduction {stale[:10]} → relancer translate_collection.py')


def main(db_path, xlsx_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    wb = load_workbook(xlsx_path, data_only=True)
    report = []

    # La colonne « source » du classeur (cellules grises) sert de référence aux
    # relecteurs : elle n'est jamais réécrite en base.
    import_lang_sheet(cur, wb, "Types d'objets", '''
        UPDATE types_of_object SET name_fr = COALESCE(?, name_fr), name_nl = COALESCE(?, name_nl), name_en = COALESCE(?, name_en)
        WHERE id = ?''', report, "types d'objets", 'SELECT name FROM types_of_object WHERE id = ?')

    import_lang_sheet(cur, wb, 'Questions', '''
        UPDATE questions SET content_fr = COALESCE(?, content_fr), content_nl = COALESCE(?, content_nl),
            content_en = COALESCE(?, content_en)
        WHERE id = ?''', report, 'questions')

    import_lang_sheet(cur, wb, 'Descriptions', '''
        UPDATE artworks SET description_fr = COALESCE(?, description_fr), description_nl = COALESCE(?, description_nl),
            description_en = COALESCE(?, description_en)
        WHERE id = ?''', report, 'descriptions', 'SELECT description FROM artworks WHERE id = ?')

    import_lang_sheet(cur, wb, 'Description - Key words', '''
        UPDATE artworks SET keywords_fr = COALESCE(?, keywords_fr), keywords_nl = COALESCE(?, keywords_nl),
            keywords_en = COALESCE(?, keywords_en)
        WHERE id = ?''', report, 'mots-clés', 'SELECT keywords FROM artworks WHERE id = ?')

    import_lang_sheet(cur, wb, 'Titres', '''
        UPDATE artworks SET title_fr = COALESCE(?, title_fr), title_nl = COALESCE(?, title_nl),
            title_en = COALESCE(?, title_en)
        WHERE id = ?''', report, 'titres', 'SELECT title FROM artworks WHERE id = ?')

    # Transcriptions : clé = artwork_id
    import_lang_sheet(cur, wb, 'Transcriptions', '''
        UPDATE transcriptions SET translation_fr = COALESCE(?, translation_fr), translation_nl = COALESCE(?, translation_nl),
            translation_en = COALESCE(?, translation_en)
        WHERE artwork_id = ?''', report, 'transcriptions (traductions)',
        'SELECT coalesce(translation, transcription) FROM transcriptions WHERE artwork_id = ?')

    import_lang_sheet(cur, wb, 'Transcriptions Explications', '''
        UPDATE transcriptions SET explanation_fr = COALESCE(?, explanation_fr), explanation_nl = COALESCE(?, explanation_nl),
            explanation_en = COALESCE(?, explanation_en)
        WHERE artwork_id = ?''', report, 'transcriptions (explications)',
        'SELECT explanation FROM transcriptions WHERE artwork_id = ?')

    # Émotions : référentiel clé -> libellés (format source | fr | nl | en)
    if 'Emotions' in wb.sheetnames:
        n = 0
        for row in wb['Emotions'].iter_rows(min_row=2, values_only=True):
            src, fr, nl, en = (list(row) + [None] * 4)[:4]
            key = clean(src) and clean(src).strip()
            if not key or not (clean(fr) and clean(nl) and clean(en)):
                continue
            cur.execute('INSERT OR REPLACE INTO emotions (emotion, name_fr, name_nl, name_en) VALUES (?,?,?,?)',
                        (key.lower(), clean(fr).strip(), clean(nl).strip(), clean(en).strip()))
            n += 1
        report.append(f'émotions : {n} ligne(s) importée(s)')
    missing = [m[0] for m in cur.execute('''
        SELECT DISTINCT lower(trim(ae.emotion)) FROM artwork_emotions ae
        LEFT JOIN emotions e ON e.emotion = lower(trim(ae.emotion)) WHERE e.emotion IS NULL''')]
    if missing:
        report.append(f'⚠ émotions utilisées sans traduction : {missing}')

    # Témoignages enregistrés (interviews) : la colonne H porte l'id du
    # témoignage en base. Les témoignages ne sont plus repérés par le prénom de
    # la personne interviewée.
    if 'Témoignages' in wb.sheetnames:
        ws = wb['Témoignages']
        if str(ws.cell(1, 8).value or '').strip().lower() != 'id':
            raise SystemExit('Feuille Témoignages : la colonne H doit s’appeler « id » (id du témoignage). '
                             'Ancien format avec fichier_source : utiliser le classeur à jour du repo.')
        n = miss = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            _q, _city, date, src_lang, fr, nl, en, tid = (list(row) + [None] * 8)[:8]
            if tid is None:
                continue
            lang = (clean(src_lang) or 'fr').lower()
            content = clean({'fr': fr, 'nl': nl, 'en': en}.get(lang, fr))
            created = date.date().isoformat() if hasattr(date, 'date') else (str(date)[:10] if date else None)
            r = cur.execute('''
                UPDATE testimonies SET content = COALESCE(?, content),
                    content_fr = COALESCE(?, content_fr), content_nl = COALESCE(?, content_nl),
                    content_en = COALESCE(?, content_en), created_at = COALESCE(?, created_at)
                WHERE id = ? AND visitor_id IS NULL''',
                (content, clean(fr), clean(nl), clean(en), created, int(tid)))
            if r.rowcount:
                n += 1
            else:
                miss += 1
        report.append(f'témoignages : {n} ligne(s) importée(s)' + (f', {miss} id(s) sans correspondance' if miss else ''))

    # Contrôle final : œuvres encore incomplètes
    incomplete = [r[0] for r in cur.execute('''
        SELECT id FROM artworks
        WHERE description_fr IS NULL OR description_nl IS NULL OR description_en IS NULL
           OR title_fr IS NULL OR title_nl IS NULL OR title_en IS NULL''')]
    if incomplete:
        report.append(f'⚠ {len(incomplete)} œuvre(s) sans titre ou description dans les 3 langues : '
                      f'{incomplete[:15]}{" …" if len(incomplete) > 15 else ""} '
                      '(lancer translate_collection.py)')

    con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in report))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
