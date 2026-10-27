#!/usr/bin/env python3
"""
Prépare les traductions FR / NL / EN des nouvelles œuvres avec DeepL, et les
écrit dans le classeur de relecture (review_translations.xlsx).

Ce script ne modifie pas la base. Il traduit, depuis leur langue d'origine :
  - les titres, descriptions et mots-clés des œuvres ;
  - les nouveaux types d'objets ;
  - les transcriptions et leurs explications ;
qui n'ont pas encore leurs trois langues, ou dont le texte source a changé
depuis la dernière traduction. Une traduction déjà présente (et peut-être déjà
relue) n'est jamais écrasée.

Dans le classeur, chaque traduction automatique est écrite en cellule jaune,
avec un commentaire « Traduction automatique (DeepL) — à relire ». La
version d'origine est en cellule grise.

Étapes suivantes :
  1. python import_translations.py <db> review_translations.xlsx
     (charge les traductions en base : le kiosque est utilisable tout de suite)
  2. envoyer le classeur aux partenaires pour relecture ;
  3. au retour, relancer import_translations.py avec le classeur corrigé.

Clé DeepL : variable d'environnement DEEPL_AUTH_KEY, ou --auth-key.
Le plan gratuit de DeepL (« Developer ») offre un crédit unique de 1 000 000 de
caractères, qui ne se renouvelle pas ; au-delà, il faut un plan payant. Le
script affiche le crédit restant et s'arrête avant de le dépasser.

Usage :
    python translate_collection.py <db> <review_translations.xlsx> [--dry-run]
           [--ids 121-234] [--keep-titles] [--auth-key CLE]

  --dry-run      liste ce qui serait traduit et le nombre de caractères, sans
                 appeler DeepL ni modifier le classeur (pas besoin de clé)
  --ids          limiter à certaines œuvres (ex. 121-234 ou 240,241)
  --keep-titles  recopier les titres tels quels dans les 3 langues (noms
                 propres, titres de films…) au lieu de les traduire

Prérequis : pip install deepl openpyxl
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill
from copy import copy

LANGS = ('fr', 'nl', 'en')
DEEPL_SOURCE = {'fr': 'FR', 'nl': 'NL', 'en': 'EN'}
DEEPL_TARGET = {'fr': 'FR', 'nl': 'NL', 'en': 'EN-GB'}
GREY = PatternFill('solid', fgColor='FFECEFF1')
YELLOW = PatternFill('solid', fgColor='FFFFF9C4')
COMMENT = 'Traduction automatique (DeepL) — à relire'
FREE_CREDIT = 1_000_000      # plan gratuit « Developer » : crédit unique, non renouvelé

CONTEXT = {
    'title': "Titre d'un objet de musée, dans TRACES, une exposition sur les souvenirs d'enfance.",
    'description': "Texte de présentation d'un objet de musée, lu par les visiteurs de TRACES, "
                   "une exposition sur les souvenirs d'enfance.",
    'keywords': "Liste de mots-clés, séparés par des virgules, qui décrivent un objet de musée.",
    'type': "Catégorie d'objet de musée (type d'objet).",
    'transcription': "Texte écrit sur un objet de musée ancien (document, lettre, image).",
    'explanation': "Explication, pour les visiteurs, du texte écrit sur un objet de musée ancien.",
}


@dataclass
class Item:
    """Un texte à traduire et la ligne du classeur où l'écrire."""
    kind: str                       # title, description, keywords, type, transcription, explanation
    sheet: str
    key: int                        # id de la ligne du classeur
    source: str                     # texte d'origine
    lang: str | None                # langue d'origine si connue
    current: dict                   # langue -> texte déjà présent (base ou classeur)
    stale: bool = False             # le texte source a changé : tout retraduire
    out: dict = field(default_factory=dict)   # langue -> traduction produite

    def targets(self):
        if self.stale:
            return [l for l in LANGS if l != self.lang]
        return [l for l in LANGS if l != self.lang and not self.current.get(l)]


# ── lecture du classeur ────────────────────────────────────────────────────
def sheet_rows(wb, sheet):
    """id -> (n° de ligne, source, {fr, nl, en}) pour une feuille id | source | fr | nl | en."""
    rows = {}
    if sheet not in wb.sheetnames:
        return rows
    for r, row in enumerate(wb[sheet].iter_rows(min_row=2, values_only=True), start=2):
        if not row or row[0] is None or not str(row[0]).strip().isdigit():
            continue
        vals = (list(row) + [None] * 5)[:5]
        rows[int(vals[0])] = (r, vals[1], {l: vals[2 + i] for i, l in enumerate(LANGS)})
    return rows


def fmt(n):
    """1000000 -> '1 000 000'"""
    return f'{n:,}'.replace(',', ' ')


def filled(v):
    return v is not None and str(v).strip() != ''


def same(a, b):
    return str(a or '').strip() == str(b or '').strip()


def parse_ids(spec):
    if not spec:
        return None
    ids = set()
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-', 1)
            ids.update(range(int(a), int(b) + 1))
        elif part.strip():
            ids.add(int(part))
    return ids


# ── inventaire de ce qui reste à traduire ─────────────────────────────────
def collect(con, wb, ids, keep_titles):
    items = []
    sheets = {s: sheet_rows(wb, s) for s in
              ('Titres', 'Descriptions', 'Description - Key words', "Types d'objets",
               'Transcriptions', 'Transcriptions Explications')}

    def merged(db_vals, sheet, key):
        """Valeurs déjà connues : base OU classeur (une relecture pas encore importée compte)."""
        row = sheets[sheet].get(key)
        return {l: db_vals[l] if filled(db_vals[l]) else (row[2][l] if row and filled(row[2][l]) else None)
                for l in LANGS}

    def source_lang(src, vals):
        for l in LANGS:
            if filled(vals[l]) and same(vals[l], src):
                return l
        return None

    for row in con.execute('''SELECT id, title, title_fr, title_nl, title_en,
                                     description, description_fr, description_nl, description_en,
                                     keywords, keywords_fr, keywords_nl, keywords_en FROM artworks ORDER BY id'''):
        aid = row[0]
        if ids and aid not in ids:
            continue
        groups = {'title': row[1:5], 'description': row[5:9], 'keywords': row[9:13]}
        sheet_of = {'title': 'Titres', 'description': 'Descriptions', 'keywords': 'Description - Key words'}
        # langue de l'œuvre : celle où la description figure telle quelle
        d = groups['description']
        art_lang = source_lang(d[0], dict(zip(LANGS, d[1:])))
        for kind, (src, *vals) in groups.items():
            if not filled(src):
                continue
            sheet = sheet_of[kind]
            current = merged(dict(zip(LANGS, vals)), sheet, aid)
            lang = source_lang(src, current) or art_lang
            wb_row = sheets[sheet].get(aid)
            stale = bool(wb_row and filled(wb_row[1]) and not same(wb_row[1], src))
            if kind == 'title' and keep_titles:
                lang = lang or 'en'
                current = {l: current[l] or src for l in LANGS}
            item = Item(kind, sheet, aid, str(src), lang, current, stale)
            if item.targets() or not wb_row or stale:
                items.append(item)

    def is_stale(sheet, key, src):
        row = sheets[sheet].get(key)
        return bool(row and filled(row[1]) and not same(row[1], src))

    for tid, name, fr, nl, en in con.execute('SELECT id, name, name_fr, name_nl, name_en FROM types_of_object'):
        current = merged({'fr': fr, 'nl': nl, 'en': en}, "Types d'objets", tid)
        item = Item('type', "Types d'objets", tid, name, source_lang(name, current), current,
                    is_stale("Types d'objets", tid, name))
        if item.targets() or tid not in sheets["Types d'objets"] or item.stale:
            items.append(item)

    for (aid, transcription, translation, tr_fr, tr_nl, tr_en,
         explanation, ex_fr, ex_nl, ex_en) in con.execute('''
            SELECT artwork_id, transcription, translation, translation_fr, translation_nl, translation_en,
                   explanation, explanation_fr, explanation_nl, explanation_en FROM transcriptions'''):
        if ids and aid not in ids:
            continue
        # source = la traduction moderne fournie par le musée s'il y en a une, sinon le texte de l'objet
        src = translation or transcription
        if filled(src):
            current = merged({'fr': tr_fr, 'nl': tr_nl, 'en': tr_en}, 'Transcriptions', aid)
            item = Item('transcription', 'Transcriptions', aid, src, None, current,
                        is_stale('Transcriptions', aid, src))
            if item.targets() == list(LANGS) or aid not in sheets['Transcriptions'] or item.stale:
                items.append(item)                     # jamais traduite, ou texte modifié
        if filled(explanation):
            current = merged({'fr': ex_fr, 'nl': ex_nl, 'en': ex_en}, 'Transcriptions Explications', aid)
            stale = is_stale('Transcriptions Explications', aid, explanation)
            lang = source_lang(explanation, current)
            item = Item('explanation', 'Transcriptions Explications', aid, explanation, lang, current, stale)
            if item.targets() or aid not in sheets['Transcriptions Explications'] or stale:
                items.append(item)
    return items


# ── traduction ────────────────────────────────────────────────────────────
class DeepLEngine:
    def __init__(self, auth_key):
        import deepl
        self.deepl = deepl
        self.translator = deepl.Translator(auth_key)

    def remaining(self):
        usage = self.translator.get_usage().character
        if usage.valid:
            return usage.limit - usage.count
        return None

    def translate(self, texts, src, tgt, context):
        """-> liste de (traduction, langue source détectée) ; src=None : détection automatique."""
        results = self.translator.translate_text(
            texts, source_lang=DEEPL_SOURCE[src] if src else None, target_lang=DEEPL_TARGET[tgt],
            context=context, preserve_formatting=True,
            formality='prefer_more' if tgt == 'fr' else None)       # « vous » en français
        if not isinstance(results, list):
            results = [results]
        return [(r.text, r.detected_source_lang) for r in results]


def batches(items, size=40, max_chars=60_000):
    batch, chars = [], 0
    for it in items:
        if batch and (len(batch) >= size or chars + len(it.source) > max_chars):
            yield batch
            batch, chars = [], 0
        batch.append(it)
        chars += len(it.source)
    if batch:
        yield batch


def translate_all(items, engine):
    warnings = []
    # 1. langue d'origine inconnue : DeepL la détecte en traduisant vers l'anglais.
    #    Les descriptions d'abord : leur langue vaut pour le titre et les mots-clés de
    #    la même œuvre (un texte court se détecte mal).
    for kind in ('description', 'title', 'keywords', 'type', 'transcription', 'explanation'):
        if kind in ('title', 'keywords'):
            detected = {it.key: it.lang for it in items if it.kind == 'description' and it.lang}
            for it in items:
                if it.kind == kind and it.lang is None and it.key in detected:
                    it.lang = detected[it.key]
        unknown = [it for it in items if it.kind == kind and it.lang is None and it.targets()]
        for batch in batches(unknown):
            for it, (txt, det) in zip(batch, engine.translate([b.source for b in batch], None, 'en', CONTEXT[kind])):
                lang = str(det or '').lower()[:2]
                if lang not in LANGS:
                    warnings.append(f'{it.sheet} {it.key} : langue détectée « {det} », traitée comme une '
                                    'traduction depuis cette langue')
                    it.lang = None
                    if 'en' in it.targets():
                        it.out['en'] = txt
                else:
                    it.lang = lang
                    if lang != 'en' and 'en' in it.targets():
                        it.out['en'] = txt
    # 2. traductions vers chaque langue manquante
    for kind in CONTEXT:
        for src in LANGS + (None,):
            for tgt in LANGS:
                todo = [it for it in items if it.kind == kind and it.lang == src
                        and tgt in it.targets() and tgt not in it.out]
                for batch in batches(todo):
                    for it, (txt, _det) in zip(batch, engine.translate([b.source for b in batch], src, tgt,
                                                                      CONTEXT[kind])):
                        it.out[tgt] = txt
    return warnings


# ── écriture dans le classeur ─────────────────────────────────────────────
def write_items(wb, items):
    stats = {'lignes ajoutées': 0, 'lignes mises à jour': 0, 'cellules traduites': 0}
    by_sheet = {}
    for it in items:
        by_sheet.setdefault(it.sheet, []).append(it)
    for sheet, its in by_sheet.items():
        if sheet not in wb.sheetnames:                        # feuille absente : on la crée
            ws = wb.create_sheet(sheet)
            for c, h in enumerate(('id', 'source', 'fr', 'nl', 'en'), 1):
                ws.cell(1, c, h)
        ws = wb[sheet]
        rows = {int(ws.cell(r, 1).value): r for r in range(2, ws.max_row + 1)
                if str(ws.cell(r, 1).value or '').strip().isdigit()}
        model = ws.max_row                                    # ligne modèle pour les styles
        for it in sorted(its, key=lambda i: i.key):
            r = rows.get(it.key)
            if r is None:
                r = ws.max_row + 1
                for c in range(1, 6):
                    src_cell, dst = ws.cell(model, c), ws.cell(r, c)
                    if src_cell.has_style:
                        dst.font, dst.border, dst.alignment = copy(src_cell.font), copy(src_cell.border), copy(src_cell.alignment)
                if ws.row_dimensions[model].height:
                    ws.row_dimensions[r].height = ws.row_dimensions[model].height
                ws.cell(r, 1, it.key)
                rows[it.key] = r
                stats['lignes ajoutées'] += 1
            else:
                stats['lignes mises à jour'] += 1
            ws.cell(r, 1).fill = GREY
            ws.cell(r, 2, it.source).fill = GREY
            for i, lang in enumerate(LANGS):
                cell = ws.cell(r, 3 + i)
                if lang == it.lang:
                    cell.value, cell.fill, cell.comment = it.source, GREY, None
                elif lang in it.out:
                    cell.value, cell.fill = it.out[lang], YELLOW
                    cell.comment = Comment(COMMENT, 'TRACES')
                    stats['cellules traduites'] += 1
                elif it.current.get(lang) and not filled(cell.value):
                    cell.value, cell.fill = it.current[lang], YELLOW
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db')
    ap.add_argument('xlsx')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--ids')
    ap.add_argument('--keep-titles', action='store_true')
    ap.add_argument('--auth-key', default=os.environ.get('DEEPL_AUTH_KEY'))
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    wb = load_workbook(args.xlsx)
    items = collect(con, wb, parse_ids(args.ids), args.keep_titles)
    con.close()
    todo = [it for it in items if it.targets()]
    chars = sum(len(it.source) * len(it.targets()) for it in todo)

    by_kind = {}
    for it in todo:
        by_kind[it.kind] = by_kind.get(it.kind, 0) + 1
    print(f'  • textes à traduire : {len(todo)} {by_kind or ""}')
    print(f'  • volume : environ {fmt(chars)} caractères '
          f'(crédit gratuit DeepL : {fmt(FREE_CREDIT)} au total, non renouvelé)')
    stale = [f'{it.sheet} {it.key}' for it in todo if it.stale]
    if stale:
        print(f'  • textes source modifiés depuis la dernière traduction (retraduits) : {stale[:10]}')

    if args.dry_run:
        for it in todo[:30]:
            print(f'    {it.sheet} {it.key} ({it.lang or "langue à détecter"} → {", ".join(it.targets())}) : '
                  f'{it.source[:60]!r}')
        if len(todo) > 30:
            print(f'    … et {len(todo) - 30} autres')
        print('  MODE VÉRIFICATION (--dry-run) : DeepL n’a pas été appelé, le classeur est inchangé')
        return
    if not items:
        print('  rien à traduire : le classeur est à jour')
        return
    if todo and not args.auth_key:
        sys.exit('clé DeepL manquante : définir DEEPL_AUTH_KEY ou passer --auth-key')

    warnings = []
    if todo:
        engine = DeepLEngine(args.auth_key)
        left = engine.remaining()
        if left is not None:
            print(f'  • crédit DeepL restant : {fmt(left)} caractères')
            if left < chars:
                sys.exit(f'crédit DeepL insuffisant : {fmt(left)} caractères disponibles, ~{fmt(chars)} '
                         'nécessaires (passer à un plan payant, ou traduire par lots avec --ids)')
        warnings = translate_all(todo, engine)
    stats = write_items(wb, items)
    wb.save(args.xlsx)
    print('  • classeur mis à jour : ' + ', '.join(f'{k} {v}' for k, v in stats.items()))
    for w in warnings:
        print('  ⚠ ' + w)
    print(f'  → étape suivante : python import_translations.py {args.db} {args.xlsx}')


if __name__ == '__main__':
    main()
