#!/usr/bin/env python3
"""
Prepares the FR / NL / EN translations of new artworks with DeepL and writes
them into the review workbook (review_translations.xlsx).

This script does not change the database. It translates, from their original
language:
  - artwork titles, descriptions and keywords;
  - new object types;
  - transcriptions and their explanations;
that do not have all three languages yet, or whose source text changed since
the last translation. An existing translation (possibly already reviewed) is
never overwritten.

In the workbook, each machine translation is written in a yellow cell with
the comment "Machine translation (DeepL), to review". The original text is in
a grey cell.

Next steps:
  1. python import_translations.py <db> review_translations.xlsx
     (loads the machine translations: the kiosk can be used right away)
  2. have the translations reviewed in the workbook;
  3. run import_translations.py again with the reviewed workbook.

DeepL key: DEEPL_AUTH_KEY environment variable, or --auth-key.
New DeepL accounts get the free "Developer" plan: a one-time credit of
1,000,000 characters that never renews. Older accounts may still have the
former "API Free" plan (500,000 characters per month). The script shows the
credit DeepL reports for your key and stops before exceeding it.

Usage:
    python translate_collection.py <db> <review_translations.xlsx> [--dry-run]
           [--ids 235-260] [--keep-titles] [--auth-key KEY]

  --dry-run      list what would be translated and the number of characters,
                 without calling DeepL or changing the workbook (no key needed)
  --ids          only these artworks (e.g. 235-260 or 240,241)
  --keep-titles  copy titles unchanged into the 3 languages (proper names,
                 film titles…) instead of translating them

Requirements: pip install deepl openpyxl
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
COMMENT = 'Machine translation (DeepL), to review / Traduction automatique (DeepL), à relire'
FREE_CREDIT = 1_000_000      # free "Developer" plan for new accounts: one-time credit

# Context sent to DeepL to guide the translation (not translated, not billed)
CONTEXT = {
    'title': "Title of a museum object shown in TRACES, an exhibition about childhood memories.",
    'description': "Description of a museum object, read by visitors of TRACES, "
                   "an exhibition about childhood memories.",
    'keywords': "Comma-separated list of keywords describing a museum object.",
    'type': "Category of a museum object (object type).",
    'transcription': "Text written on an old museum object (document, letter, picture).",
    'explanation': "Explanation, for visitors, of the text written on an old museum object.",
}


@dataclass
class Item:
    """A text to translate and the workbook row where it goes."""
    kind: str                       # title, description, keywords, type, transcription, explanation
    sheet: str
    key: int                        # workbook row id
    source: str                     # original text
    lang: str | None                # original language, if known
    current: dict                   # language -> existing text (database or workbook)
    stale: bool = False             # the source text changed: translate everything again
    out: dict = field(default_factory=dict)   # language -> new translation

    def targets(self):
        if self.stale:
            return [l for l in LANGS if l != self.lang]
        return [l for l in LANGS if l != self.lang and not self.current.get(l)]


# ── reading the workbook ────────────────────────────────────────────────────
def sheet_rows(wb, sheet):
    """id -> (row number, source, {fr, nl, en}) for a sheet laid out as id | source | fr | nl | en."""
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
    """1000000 -> '1,000,000'"""
    return f'{n:,}'


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


# ── what is left to translate ─────────────────────────────────
def collect(con, wb, ids, keep_titles):
    items = []
    sheets = {s: sheet_rows(wb, s) for s in
              ('Titres', 'Descriptions', 'Description - Key words', "Types d'objets",
               'Transcriptions', 'Transcriptions Explications')}

    def merged(db_vals, sheet, key):
        """Known values: database OR workbook (a review not yet loaded counts)."""
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
        # language of the artwork: the column where the description appears unchanged
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
        # source = the modern translation provided by the museum if any, otherwise the text on the object
        src = translation or transcription
        if filled(src):
            current = merged({'fr': tr_fr, 'nl': tr_nl, 'en': tr_en}, 'Transcriptions', aid)
            item = Item('transcription', 'Transcriptions', aid, src, None, current,
                        is_stale('Transcriptions', aid, src))
            if item.targets() == list(LANGS) or aid not in sheets['Transcriptions'] or item.stale:
                items.append(item)                     # never translated, or text changed
        if filled(explanation):
            current = merged({'fr': ex_fr, 'nl': ex_nl, 'en': ex_en}, 'Transcriptions Explications', aid)
            stale = is_stale('Transcriptions Explications', aid, explanation)
            lang = source_lang(explanation, current)
            item = Item('explanation', 'Transcriptions Explications', aid, explanation, lang, current, stale)
            if item.targets() or aid not in sheets['Transcriptions Explications'] or stale:
                items.append(item)
    return items


# ── translation ────────────────────────────────────────────────────────────
class DeepLEngine:
    def __init__(self, auth_key):
        import deepl
        self.deepl = deepl
        self.translator = deepl.Translator(auth_key)

    def remaining(self):
        try:
            usage = self.translator.get_usage().character
        except self.deepl.exceptions.AuthorizationException:
            sys.exit('DeepL refused the key: copy it again from your DeepL account (DEEPL_AUTH_KEY)')
        except self.deepl.exceptions.ConnectionException as exc:
            sys.exit(f'cannot reach DeepL ({exc}): check the internet connection')
        if usage.valid:
            return usage.limit - usage.count
        return None

    def translate(self, texts, src, tgt, context):
        """-> list of (translation, detected source language); src=None: automatic detection."""
        try:
            results = self._translate(texts, src, tgt, context)
        except self.deepl.exceptions.QuotaExceededException:
            sys.exit('DeepL credit used up: switch to a paid plan, then run the command again '
                     '(the workbook was not changed)')
        if not isinstance(results, list):
            results = [results]
        return [(r.text, r.detected_source_lang) for r in results]

    def _translate(self, texts, src, tgt, context):
        return self.translator.translate_text(
            texts, source_lang=DEEPL_SOURCE[src] if src else None, target_lang=DEEPL_TARGET[tgt],
            context=context, preserve_formatting=True,
            formality='prefer_more' if tgt == 'fr' else None)       # "vous" in French


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
    # 1. unknown original language: DeepL detects it while translating into English.
    #    Descriptions first: their language also applies to the title and keywords
    #    of the same artwork (short texts are hard to detect).
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
                    warnings.append(f'{it.sheet} {it.key}: detected language "{det}", translated from that language')
                    it.lang = None
                    if 'en' in it.targets():
                        it.out['en'] = txt
                else:
                    it.lang = lang
                    if lang != 'en' and 'en' in it.targets():
                        it.out['en'] = txt
    # 2. translations into each missing language
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


# ── writing the workbook ─────────────────────────────────────────────
def write_items(wb, items):
    stats = {'rows added': 0, 'rows updated': 0, 'cells translated': 0}
    by_sheet = {}
    for it in items:
        by_sheet.setdefault(it.sheet, []).append(it)
    for sheet, its in by_sheet.items():
        if sheet not in wb.sheetnames:                        # missing sheet: create it
            ws = wb.create_sheet(sheet)
            for c, h in enumerate(('id', 'source', 'fr', 'nl', 'en'), 1):
                ws.cell(1, c, h)
        ws = wb[sheet]
        rows = {int(ws.cell(r, 1).value): r for r in range(2, ws.max_row + 1)
                if str(ws.cell(r, 1).value or '').strip().isdigit()}
        model = ws.max_row                                    # model row for cell styles
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
                stats['rows added'] += 1
            else:
                stats['rows updated'] += 1
            ws.cell(r, 1).fill = GREY
            ws.cell(r, 2, it.source).fill = GREY
            for i, lang in enumerate(LANGS):
                cell = ws.cell(r, 3 + i)
                if lang == it.lang:
                    cell.value, cell.fill, cell.comment = it.source, GREY, None
                elif lang in it.out:
                    cell.value, cell.fill = it.out[lang], YELLOW
                    cell.comment = Comment(COMMENT, 'TRACES')
                    stats['cells translated'] += 1
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

    for path, what in ((args.db, 'database'), (args.xlsx, 'workbook')):
        if not os.path.isfile(path):
            sys.exit(f'{what} not found: {path} (run the command from the database/ folder)')
    con = sqlite3.connect(args.db)
    wb = load_workbook(args.xlsx)
    items = collect(con, wb, parse_ids(args.ids), args.keep_titles)
    con.close()
    todo = [it for it in items if it.targets()]
    chars = sum(len(it.source) * len(it.targets()) for it in todo)

    by_kind = {}
    for it in todo:
        by_kind[it.kind] = by_kind.get(it.kind, 0) + 1
    print(f'  • texts to translate: {len(todo)} {by_kind or ""}')
    print(f'  • volume: about {fmt(chars)} characters '
          f'(free DeepL "Developer" plan: {fmt(FREE_CREDIT)} in total)')
    stale = [f'{it.sheet} {it.key}' for it in todo if it.stale]
    if stale:
        print(f'  • source texts changed since the last translation (translated again): {stale[:10]}')

    if args.dry_run:
        for it in todo[:30]:
            print(f'    {it.sheet} {it.key} ({it.lang or "language to detect"} → {", ".join(it.targets())}): '
                  f'{it.source[:60]!r}')
        if len(todo) > 30:
            print(f'    … and {len(todo) - 30} more')
        print('  DRY RUN (--dry-run): DeepL was not called, the workbook is unchanged')
        return
    if not items:
        print('  nothing to translate: the workbook is up to date')
        print(f'  → next step: python import_translations.py {args.db} {args.xlsx}')
        return
    if todo and not args.auth_key:
        sys.exit('missing DeepL key: set the DEEPL_AUTH_KEY environment variable or pass --auth-key')
    try:                         # fail now rather than after spending DeepL credit
        open(args.xlsx, 'r+b').close()
    except PermissionError:
        sys.exit(f'cannot write {args.xlsx}: close it in Excel and run the command again')

    warnings = []
    if todo:
        engine = DeepLEngine(args.auth_key)
        left = engine.remaining()
        if left is not None:
            print(f'  • DeepL credit left: {fmt(left)} characters')
            if left < chars:
                sys.exit(f'not enough DeepL credit: {fmt(left)} characters left, ~{fmt(chars)} needed '
                         '(switch to a paid plan, or translate in smaller batches with --ids)')
        warnings = translate_all(todo, engine)
    stats = write_items(wb, items)
    wb.save(args.xlsx)
    print('  • workbook updated: ' + ', '.join(f'{k} {v}' for k, v in stats.items()))
    for w in warnings:
        print('  ⚠ ' + w)
    print(f'  → next step: python import_translations.py {args.db} {args.xlsx}')


if __name__ == '__main__':
    main()
