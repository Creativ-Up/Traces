#!/usr/bin/env python3
"""
Importe la collection d'un musée dans pp1_collection.db, depuis un tableur au
format TRACES (template_collection.xlsx). Le classeur historique
PP1-Collection_Database.xlsx a le même format, mais ne doit plus servir qu'en
lecture : la base a évolué depuis (--update est refusé avec ce fichier).

Pour chaque œuvre du tableur :
  - l'œuvre est créée (ou mise à jour avec --update) dans `artworks` ;
  - son type d'objet, sa question et ses émotions sont reliés aux référentiels
    de la base (un type d'objet inconnu est créé, à traduire ensuite) ;
  - ses médias sont retrouvés dans assets/ (images .jpg, vidéos .mp4) ;
  - ses transcriptions éventuelles (feuille « Transcriptions ») sont importées.

Les textes sont enregistrés dans leur langue d'origine. Les traductions dans
les deux autres langues sont produites ensuite par translate_collection.py.

Identification des œuvres :
  - colonne « Database ID » remplie : c'est l'identifiant TRACES de l'œuvre ;
  - sinon, l'œuvre est reconnue par le couple (Origin, Museum ID) et reçoit un
    nouvel identifiant à sa création. Relancer l'import ne crée donc pas de
    doublon.
Une œuvre déjà présente en base n'est jamais modifiée sans --update.

Usage :
    python import_collection.py <db> <tableur.xlsx> --assets ../assets
           [--origin "Nom du musée"] [--lang fr|nl|en] [--update] [--dry-run]

  --assets   dossier des médias préparés (prepare_media.py), pour vérifier
             que chaque fichier cité existe
  --origin   n'importer que les lignes de ce musée
  --lang     langue des textes quand la colonne « Language » est vide
  --update   mettre à jour les œuvres déjà présentes (une valeur non reconnue :
             question, type, émotion, média absent, ne remplace jamais l'existante)
  --dry-run  tout vérifier et afficher le rapport, sans rien écrire
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

LANGS = ('fr', 'nl', 'en')
LANG_ALIASES = {
    'fr': 'fr', 'francais': 'fr', 'french': 'fr', 'frans': 'fr',
    'nl': 'nl', 'nederlands': 'nl', 'neerlandais': 'nl', 'dutch': 'nl', 'vlaams': 'nl',
    'en': 'en', 'anglais': 'en', 'english': 'en', 'engels': 'en',
}
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.tif', '.tiff', '.bmp', '.avif')
VIDEO_EXTS = ('.mp4', '.webm', '.mov')
KNOWN_EXTS = IMAGE_EXTS + VIDEO_EXTS

# En-têtes reconnus (comparés sans accents, ni casse, ni ponctuation)
FIELDS = {
    'id': ('databaseid', 'idtraces'),
    'museum_id': ('museumid', 'inventorynumber', 'numerodinventaire', 'inventaire', 'inventarisnummer'),
    'origin': ('origin', 'institution', 'musee', 'museum'),
    'type': ('typeofobject', 'typedobjet', 'type'),
    'date': ('dateperiod', 'date', 'period', 'periode', 'datering'),
    'title': ('title', 'titre', 'titel'),
    'author': ('author', 'auteur', 'artist', 'artiste', 'maker'),
    'author_name': ('name', 'nom', 'names', 'personnes'),
    'storage': ('storageplace', 'lieudeconservation', 'bewaarplaats'),
    'keywords': ('descriptionkeywords', 'keywords', 'motscles', 'trefwoorden'),
    'emotions': ('pulchikswheelmatch', 'plutchikswheelmatch', 'plutchik', 'emotions', 'emoties'),
    'description': ('explanation', 'description', 'beschrijving'),
    'question': ('question', 'vraag'),
    'media': ('photo', 'photos', 'media', 'medias', 'files', 'fichiers', 'bestanden'),
    'lang': ('language', 'langue', 'taal', 'languedestextes'),
}
TRANSCRIPTION_FIELDS = {
    'id': FIELDS['id'],
    'museum_id': FIELDS['museum_id'],
    'transcription': ('transcriptions', 'transcription', 'transcriptie'),
    'explanation': ('explanation', 'explanations', 'explication', 'explications', 'uitleg'),
    'translation': ('translation', 'traduction', 'vertaling'),
}


def norm(text) -> str:
    s = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', s.lower())


def text(value):
    """Valeur de cellule en texte, None si vide."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def fold(s: str) -> str:
    """Retire les accents (é -> e) : un nom de fichier saisi dans Excel et le même
    nom écrit par macOS (accents décomposés) donnent ainsi le même résultat."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def normalize_media_name(name: str) -> str:
    """Convention de nommage des médias TRACES (identique à prepare_media.py) :
    IMadeYou_01_053.JPG -> imadeyou-01-053.jpg (extension préservée)."""
    s = fold(name.strip().lower())
    ext = ''
    for e in KNOWN_EXTS:
        if s.endswith(e):
            s, ext = s[:-len(e)], e
            break
    s = re.sub(r'[_.\s]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s + ext


ROMAN = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100}


def roman_to_int(s):
    total = 0
    for a, b in zip(s, s[1:] + ' '):
        v = ROMAN[a]
        total += -v if b in ROMAN and ROMAN[b] > v else v
    return total


def parse_years(value):
    """Bornes (année min, année max) d'une date ou période, (None, None) si illisible.
    '1870-1880' -> (1870, 1880) ; '1914-18' -> (1914, 1918) ; 'ca. 1935' -> (1935, 1935) ;
    '19e siècle' ou 'XIXe siècle' -> (1800, 1899) ; 'first half of the 20th century' -> (1900, 1950)."""
    if value is None:
        return None, None
    if hasattr(value, 'year'):
        return value.year, value.year
    s = fold(str(value).lower())
    m = re.search(r'(?<!\d)(1\d{3}|20\d{2})\s*[-/]\s*(\d{2})(?!\d)', s)       # 1914-18, 1950-60
    if m:
        a, b = int(m.group(1)), int(m.group(1)[:2] + m.group(2))
        return min(a, b), max(a, b)
    years = [int(y) for y in re.findall(r'(?<!\d)(1\d{3}|20\d{2})(?!\d)', s)]
    if years:
        return min(years), max(years)                                          # 1890-1880 -> (1880, 1890)
    m = re.search(r'(?<![a-z0-9])(\d{1,2}|[ivxlc]+)\s*(?:st|nd|rd|th|e|eme|er|de|ste)?\s+'
                  r'(?:century|siecle|eeuw)', s)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else roman_to_int(m.group(1))
        start = (n - 1) * 100
        if any(w in s for w in ('first half', 'premiere moitie', 'eerste helft')):
            return start, start + 50
        if any(w in s for w in ('second half', 'seconde moitie', 'deuxieme moitie', 'tweede helft')):
            return start + 50, start + 99
        if any(w in s for w in ('early', 'debut', 'begin')):
            return start, start + 30
        if any(w in s for w in ('late', 'fin ', 'eind')):
            return start + 70, start + 99
        return start, start + 99
    return None, None


def find_header(ws, fields, required):
    """Repère la ligne d'en-têtes (parmi les 6 premières) et la colonne de chaque champ."""
    for r in range(1, min(ws.max_row, 6) + 1):
        cols = {}
        for c in range(1, ws.max_column + 1):
            key = norm(ws.cell(r, c).value)
            for field, aliases in fields.items():
                if key in aliases and field not in cols:
                    cols[field] = c
        if all(f in cols for f in required):
            return r, cols
    return None, None


def pick_sheet(wb):
    for name in ('Œuvres', 'Oeuvres', 'Database', 'Collection'):
        if name in wb.sheetnames:
            return wb[name]
    for ws in wb.worksheets:
        if find_header(ws, FIELDS, ('origin', 'description'))[0]:
            return ws
    raise SystemExit('aucune feuille d’œuvres trouvée (en-têtes « Origin » et « Explanation » attendus)')


class Importer:
    def __init__(self, con, args):
        self.con, self.cur, self.args = con, con.cursor(), args
        self.report, self.warn = [], []
        self.assets = None
        if args.assets:
            folder = Path(args.assets)
            if not folder.is_dir():
                raise SystemExit(f'dossier de médias introuvable : {folder}')
            self.assets = {p.name for p in folder.iterdir() if p.is_file()}
        self.next_id = (self.cur.execute('SELECT COALESCE(MAX(id), 0) FROM artworks').fetchone()[0]) + 1
        self.types = {}
        for tid, *names in self.cur.execute('SELECT id, name, name_fr, name_nl, name_en FROM types_of_object'):
            for n in names:
                if n:
                    self.types.setdefault(norm(n), tid)
        self.questions = {}
        for qid, *contents in self.cur.execute('SELECT id, content, content_fr, content_nl, content_en FROM questions'):
            for c in contents:
                if c:
                    self.questions[norm(c)] = qid
        self.question_ids = {q for q in self.questions.values()}
        self.emotions = {}
        for key, *names in self.cur.execute('SELECT emotion, name_fr, name_nl, name_en FROM emotions'):
            self.emotions[norm(key)] = key
            for n in names:
                if n:
                    self.emotions.setdefault(norm(n), key)
        self.new_types = []
        self.missing = defaultdict(list)   # colonne vide -> œuvres concernées
        self.touched = {}          # museum_id / id -> artwork id, pour les transcriptions

    # ── résolution des référentiels ──────────────────────────────────────
    # Chaque résolution renvoie (valeur, ok) : ok=False signale une valeur
    # fournie mais non reconnue. En mise à jour, la valeur existante est alors
    # conservée plutôt qu'écrasée.
    def resolve_lang(self, value, aid):
        if value:
            lang = LANG_ALIASES.get(norm(value))
            if lang:
                return lang
            self.warn.append(f'œuvre {aid} : langue « {value} » non reconnue (fr, nl ou en)')
        return self.args.lang

    def resolve_type(self, name, lang, aid, create):
        if not name:
            return None, False
        tid = self.types.get(norm(name))
        if tid is not None:
            return tid, True
        if not create:
            self.warn.append(f'œuvre {aid} : type d’objet « {name} » inconnu, type actuel conservé')
            return None, False
        self.cur.execute('INSERT INTO types_of_object (name) VALUES (?)', (name,))
        tid = self.cur.lastrowid
        if lang:
            self.cur.execute(f'UPDATE types_of_object SET name_{lang} = ? WHERE id = ?', (name, tid))
        self.types[norm(name)] = tid
        self.new_types.append(name)
        return tid, True

    def resolve_question(self, value, aid):
        raw = text(value)
        if not raw:
            self.missing['Question'].append(aid)
            return None, True
        m = re.fullmatch(r'(?:question|vraag|q)?\s*(?:n\s*°?|°)?\s*(\d+)', raw.strip().lower())
        if m and int(m.group(1)) in self.question_ids:
            return int(m.group(1)), True
        qid = self.questions.get(norm(raw))
        if qid is None:
            self.warn.append(f'œuvre {aid} : question non reconnue « {raw[:60]} » (numéro 1 à 12 attendu)')
            return None, False
        return qid, True

    def resolve_emotions(self, value, aid):
        keys, ok = [], True
        for token in re.split(r'[;,\n/]+', str(value or '')):
            if not token.strip():
                continue
            key = self.emotions.get(norm(token))
            if key is None:
                self.warn.append(f'œuvre {aid} : émotion « {token.strip()} » hors référentiel, ignorée '
                                 '(voir la feuille « Émotions » du modèle)')
                ok = False
            elif key not in keys:
                keys.append(key)
        return keys, ok

    def resolve_media(self, value, aid):
        files, ok = [], True
        for token in re.split(r'[;,\n]+', str(value or '')):
            if not token.strip():
                continue
            name = normalize_media_name(token)
            stem, ext = (name.rsplit('.', 1)[0], '.' + name.rsplit('.', 1)[1]) if '.' in name else (name, '')
            found = None
            if self.assets is not None:
                if name in self.assets and ext not in ('.tif', '.tiff', '.png', '.mov', '.jpeg'):
                    found = name
                else:
                    for e in ('.jpg', '.mp4', '.webm', '.webp'):
                        if stem + e in self.assets:
                            found = stem + e
                            break
            if found is None:
                # nom attendu après prepare_media.py : vidéos en .mp4, tout le reste en .jpg
                found = stem + ('.mp4' if ext in VIDEO_EXTS else '.jpg')
                if self.assets is not None:
                    self.warn.append(f'œuvre {aid} : média « {token.strip()} » absent de assets/ (attendu : {found})')
                    ok = False
            files.append(found)
        images = [f for f in files if not f.endswith(VIDEO_EXTS)]
        thumb = images[0] if images else (files[0].rsplit('.', 1)[0] + '-thumb.jpg' if files else None)
        if thumb and self.assets is not None and thumb not in self.assets:
            self.warn.append(f'œuvre {aid} : vignette « {thumb} » absente de assets/')
            ok = False
        if not files:
            self.warn.append(f'œuvre {aid} : aucun média')
            ok = False
        return (', '.join(files) or None), thumb, ok

    # ── import des œuvres ────────────────────────────────────────────────
    def import_artworks(self, ws):
        hrow, cols = find_header(ws, FIELDS, ('origin', 'description'))
        if not hrow:
            raise SystemExit(f'feuille « {ws.title} » : en-têtes « Origin » et « Explanation » introuvables')
        get = lambda r, f: ws.cell(r, cols[f]).value if f in cols else None
        inserted, updated, skipped = [], 0, 0
        origin_filter = norm(self.args.origin) if self.args.origin else None
        seen = set()

        for r in range(hrow + 1, ws.max_row + 1):
            origin = text(get(r, 'origin'))
            description = text(get(r, 'description'))
            if not origin and not description:
                continue                                        # ligne vide
            if origin_filter and norm(origin) != origin_filter:
                continue
            raw_id, museum_id = text(get(r, 'id')), text(get(r, 'museum_id'))
            label = f'ligne {r}'
            if not origin or not description:
                self.warn.append(f'{label} : « Origin » et « Explanation » sont obligatoires, ligne ignorée')
                continue

            # identification
            if raw_id:
                try:
                    aid = int(float(raw_id))
                except ValueError:
                    self.warn.append(f'{label} : Database ID « {raw_id} » invalide, ligne ignorée')
                    continue
                row = self.cur.execute('SELECT origin FROM artworks WHERE id = ?', (aid,)).fetchone()
                if row and norm(row[0]) != norm(origin):
                    self.warn.append(f'{label} : l’id {aid} appartient déjà à « {row[0]} », ligne ignorée')
                    continue
                exists = row is not None
                key = ('id', aid)
            elif museum_id:
                # même musée = même nom à la casse, aux accents et à la ponctuation près
                match = [i for i, o in self.cur.execute('SELECT id, origin FROM artworks WHERE museum_id = ?',
                                                        (museum_id,)) if norm(o) == norm(origin)]
                exists = bool(match)
                aid = match[0] if exists else self.next_id
                key = ('museum_id', norm(origin), museum_id)
            else:
                self.warn.append(f'{label} : « Database ID » ou « Museum ID » obligatoire, ligne ignorée')
                continue
            if key in seen:
                self.warn.append(f'{label} : œuvre en double dans le tableur ({museum_id or aid}), ligne ignorée')
                continue
            seen.add(key)
            label = f'œuvre {aid}'
            if exists and not self.args.update:
                skipped += 1
                continue
            old = {}
            if exists:
                old = dict(zip(('question_id', 'media_url', 'thumbnail_url', 'type_of_object_id', 'emotions'),
                               self.cur.execute('''SELECT question_id, media_url, thumbnail_url, type_of_object_id,
                                                          emotions FROM artworks WHERE id = ?''', (aid,)).fetchone()))

            lang = self.resolve_lang(text(get(r, 'lang')), aid)
            if not lang:
                self.missing['Language (détectée par DeepL)'].append(aid)
            type_id, type_ok = self.resolve_type(text(get(r, 'type')), lang, aid, create=not exists)
            if not type_ok:
                if not exists:
                    self.warn.append(f'{label} : type d’objet manquant, ligne ignorée')
                    continue
                type_id = old['type_of_object_id']
            title = text(get(r, 'title'))
            if not title:
                self.missing['Title'].append(aid)
            keywords = text(get(r, 'keywords'))
            if not keywords:
                self.missing['Keywords'].append(aid)
            date_period = get(r, 'date')
            y_min, y_max = parse_years(date_period)
            if hasattr(date_period, 'year'):          # date saisie comme date Excel : l'année suffit
                date_period = str(date_period.year)
            if date_period is None:
                self.missing['Date /period'].append(aid)
            elif y_min is None:
                self.warn.append(f'{label} : date « {date_period} » illisible (sert au choix des œuvres proposées)')
            question_id, q_ok = self.resolve_question(get(r, 'question'), aid)
            media_url, thumb, media_ok = self.resolve_media(get(r, 'media'), aid)
            emotions, emo_ok = self.resolve_emotions(get(r, 'emotions'), aid)
            if not emotions:
                self.warn.append(f'{label} : aucune émotion reconnue (elles servent au choix des œuvres proposées)')

            values = {
                'museum_id': museum_id, 'origin': origin, 'type_of_object_id': type_id,
                'date_period': text(date_period), 'date_year_min': y_min, 'date_year_max': y_max,
                'title': title, 'author': text(get(r, 'author')), 'author_name': text(get(r, 'author_name')),
                'storage_place': text(get(r, 'storage')) or '',        # non nul : lu tel quel par le backend
                'keywords': keywords or '', 'description': description,
                'question_id': question_id, 'media_url': media_url, 'thumbnail_url': thumb,
                'emotions': ', '.join(emotions),                         # non nul : lu tel quel par le backend
            }
            if exists:                 # une valeur non reconnue n'écrase jamais l'existant
                if not q_ok:
                    values['question_id'] = old['question_id']
                if not media_ok:
                    values['media_url'], values['thumbnail_url'] = old['media_url'], old['thumbnail_url']
                    self.warn.append(f'{label} : médias actuels conservés')
                if not emo_ok:
                    values['emotions'] = old['emotions']
                    emotions = [e.strip().lower() for e in (old['emotions'] or '').split(',') if e.strip()]
            if lang:                                   # la version source, dans sa langue
                values.update({f'title_{lang}': title, f'description_{lang}': description,
                               f'keywords_{lang}': keywords})
            if exists:
                sets = ', '.join(f'{c} = ?' for c in values)
                self.cur.execute(f'UPDATE artworks SET {sets} WHERE id = ?', list(values.values()) + [aid])
                updated += 1
            else:
                values.update({'id': aid, 'popularity': 0})
                cols_sql = ', '.join(values)
                self.cur.execute(f'INSERT INTO artworks ({cols_sql}) VALUES ({", ".join("?" * len(values))})',
                                 list(values.values()))
                self.next_id = max(self.next_id, aid + 1)
                inserted.append((museum_id, aid))
            self.cur.execute('DELETE FROM artwork_emotions WHERE artwork_id = ?', (aid,))
            self.cur.executemany('INSERT INTO artwork_emotions (artwork_id, emotion) VALUES (?, ?)',
                                 [(aid, e) for e in emotions])
            self.touched[('id', str(aid))] = (aid, lang)
            if museum_id:
                self.touched[('museum_id', museum_id)] = (aid, lang)

        self.report.append(f'œuvres créées : {len(inserted)}, mises à jour : {updated}, '
                           f'déjà présentes et laissées intactes : {skipped}'
                           + (' (ajouter --update pour les modifier)' if skipped and not self.args.update else ''))
        if inserted:
            ids = [a for _m, a in inserted]
            self.report.append(f'identifiants attribués : {min(ids)}-{max(ids)} (à communiquer au musée '
                               f'pour la relecture ; --ids {min(ids)}-{max(ids)} pour translate_collection.py)')
            for m, a in inserted[:200]:
                self.report.append(f'    {m or "—"} → {a}')
        if self.new_types:
            self.report.append(f'nouveaux types d’objets créés (à traduire) : {self.new_types}')
        for col, ids in self.missing.items():
            self.warn.append(f'colonne « {col} » vide pour {len(ids)} œuvre(s) : {ids[:15]}{" …" if len(ids) > 15 else ""}')

    # ── transcriptions (feuille optionnelle) ─────────────────────────────
    def import_transcriptions(self, wb):
        if 'Transcriptions' not in wb.sheetnames:
            return
        ws = wb['Transcriptions']
        hrow, cols = find_header(ws, TRANSCRIPTION_FIELDS, ('transcription',))
        if not hrow:
            return
        get = lambda r, f: text(ws.cell(r, cols[f]).value) if f in cols else None
        n = 0
        for r in range(hrow + 1, ws.max_row + 1):
            transcription, explanation, translation = get(r, 'transcription'), get(r, 'explanation'), get(r, 'translation')
            if not (transcription or explanation):
                continue
            try:
                key = ('id', str(int(float(get(r, 'id'))))) if get(r, 'id') else ('museum_id', get(r, 'museum_id'))
            except ValueError:
                self.warn.append(f'Transcriptions, ligne {r} : Database ID « {get(r, "id")} » invalide, ligne ignorée')
                continue
            if key not in self.touched:
                continue                                   # œuvre non importée par ce passage
            aid, lang = self.touched[key]
            values = {'transcription': transcription, 'explanation': explanation, 'translation': translation}
            if lang and explanation:
                values[f'explanation_{lang}'] = explanation
            if self.cur.execute('SELECT 1 FROM transcriptions WHERE artwork_id = ?', (aid,)).fetchone():
                sets = ', '.join(f'{c} = ?' for c in values)
                self.cur.execute(f'UPDATE transcriptions SET {sets} WHERE artwork_id = ?', list(values.values()) + [aid])
            else:
                values['artwork_id'] = aid
                self.cur.execute(f'INSERT INTO transcriptions ({", ".join(values)}) VALUES ({", ".join("?" * len(values))})',
                                 list(values.values()))
            n += 1
        if n:
            self.report.append(f'transcriptions importées : {n}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db')
    ap.add_argument('xlsx')
    ap.add_argument('--assets', help='dossier des médias préparés (ex. ../assets)')
    ap.add_argument('--origin', help='n’importer que les lignes de ce musée')
    ap.add_argument('--lang', choices=LANGS, help='langue des textes si la colonne « Language » est vide')
    ap.add_argument('--update', action='store_true', help='mettre à jour les œuvres déjà présentes')
    ap.add_argument('--dry-run', action='store_true', help='vérifier sans rien écrire')
    args = ap.parse_args()

    if not Path(args.db).is_file():
        sys.exit(f'base introuvable : {args.db}')
    wb = load_workbook(args.xlsx, data_only=True)
    if args.update and 'List of questions' in wb.sheetnames:
        sys.exit('PP1-Collection_Database.xlsx ne doit pas servir à mettre à jour les œuvres existantes : la '
                 'base a évolué depuis (vidéos du Fresnoy, types fusionnés, corrections). Utiliser --update '
                 'uniquement avec le tableur du musée concerné.')
    con = sqlite3.connect(args.db)
    imp = Importer(con, args)
    if imp.assets is None:
        imp.warn.append('--assets non fourni : la présence des médias n’a pas été vérifiée')
    imp.import_artworks(pick_sheet(wb))
    imp.import_transcriptions(wb)

    total = con.execute('SELECT COUNT(*) FROM artworks').fetchone()[0]
    imp.report.append(f'collection : {total} œuvres')
    no_vec = con.execute('SELECT COUNT(*) FROM artworks WHERE description_vector IS NULL').fetchone()[0]
    pending = con.execute('''SELECT COUNT(*) FROM artworks WHERE description_fr IS NULL
                             OR description_nl IS NULL OR description_en IS NULL''').fetchone()[0]
    if pending:
        imp.report.append(f'œuvres à traduire : {pending} → python translate_collection.py {args.db} review_translations.xlsx')
    if no_vec:
        imp.report.append(f'œuvres sans vecteur : {no_vec} → compute_embeddings.py, OBLIGATOIRE avant de '
                          'déployer la base (sans vecteur, le serveur du kiosque ne démarre pas)')

    if args.dry_run:
        con.rollback()
        imp.report.insert(0, 'MODE VÉRIFICATION (--dry-run) : rien n’a été écrit')
    else:
        con.commit()
    con.close()
    print('\n'.join('  • ' + r for r in imp.report))
    for w in dict.fromkeys(imp.warn):
        print('  ⚠ ' + w)


if __name__ == '__main__':
    main()
