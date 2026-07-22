"""
PP1 Collection Database — Remplissage des colonnes trilingues FR/NL/EN

Traduit avec NLLB-200 tout le contenu affiché aux visiteurs, toujours depuis
la langue source (jamais via un relais anglais) :

    questions.content        -> content_fr / content_nl / content_en
    types_of_object.name     -> name_fr / name_nl / name_en
    artworks.description     -> description_fr / description_nl / description_en
    transcriptions.explanation -> explanation_fr / _nl / _en
    transcriptions.translation -> translation_fr / _nl / _en
        (la traduction EN historique est conservée telle quelle comme
         translation_en ; FR et NL sont générés depuis le texte original
         de l'objet quand sa langue est détectable, sinon depuis l'EN)

Un cache (translations_cache.json) évite de retraduire à chaque rebuild.

Usage :
    pip install transformers sentencepiece torch
    python translate_content.py [chemin_db] [modele_hf]

Modèle par défaut : facebook/nllb-200-1.3B — le même que celui utilisé pour
les traductions des témoignages (transcriptions_clean.csv), pour un style
homogène dans toute la base. Chargé en float16 sur GPU (~2,6 Go de VRAM).

⚠ Après exécution, relire manuellement :
    - questions.content_fr / content_nl : remplacer par les formulations
      officielles utilisées lors des interviews si elles existent ;
    - types_of_object.name_* : 28 libellés courts, NLLB est moins fiable
      sur les libellés hors contexte.
"""

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "pp1_collection.db"
MODEL_NAME = sys.argv[2] if len(sys.argv) > 2 else "facebook/nllb-200-1.3B"
CHUNKING = "v2-sentence"  # bump -> invalide le cache (v1 traduisait par paragraphe :
# NLLB omettait des phrases sur les entrées multi-phrases)
CACHE_PATH = Path("translations_cache.json")

FLORES = {"fr": "fra_Latn", "nl": "nld_Latn", "en": "eng_Latn"}
LANGS = ("fr", "nl", "en")

# ----------------------------------------------------------------
# Détection de langue par stopwords (suffisant pour FR/NL/EN)
# ----------------------------------------------------------------
_STOP = {
    "fr": {
        " le ",
        " la ",
        " les ",
        " des ",
        " une ",
        " est ",
        " dans ",
        " cette ",
        " qui ",
        " pour ",
        " avec ",
        " sur ",
        " été ",
        " aux ",
        " du ",
        " ce ",
    },
    "nl": {
        " de ",
        " het ",
        " een ",
        " van ",
        " en ",
        " dat ",
        " met ",
        " voor ",
        " zijn ",
        " naar ",
        " deze ",
        " wordt ",
        " werd ",
        " bij ",
        " ik ",
    },
    "en": {
        " the ",
        " of ",
        " and ",
        " is ",
        " this ",
        " with ",
        " was ",
        " for ",
        " from ",
        " his ",
        " her ",
        " are ",
        " which ",
        " has ",
        " that ",
    },
}


def detect_lang(text: str, default: str = "fr") -> str:
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    scores = {lang: sum(t.count(w) for w in words) for lang, words in _STOP.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else default


# ----------------------------------------------------------------
# Traduction NLLB avec découpage en phrases et cache
# ----------------------------------------------------------------
print(f"Chargement du modèle {MODEL_NAME}…")
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, torch_dtype=dtype).to(device)
print(f"Modèle chargé sur {device} ({dtype}).")

cache: dict[str, str] = (
    json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
)
# Découpage en phrases : ponctuation finale (éventuellement suivie d'un guillemet
# ou d'une parenthèse fermante), puis espace, puis majuscule/chiffre/guillemet ouvrant
# Les lookbehinds négatifs évitent de couper après les abréviations courantes
_SENT_RE = re.compile(
    r"(?:(?<=[.!?…])|(?<=[.!?…][\"»”')\]]))"
    r"(?<!\bM\.)(?<!\bMr\.)(?<!\bDr\.)(?<!\bSt\.)(?<!\bJr\.)(?<!\bcf\.)"
    r"\s+(?=[A-ZÀ-Ý0-9\"'«(])"
)
BATCH_SIZE = 8


def _translate_sentences(sentences: list[str], src: str, tgt: str) -> list[str]:
    """Traduit une liste de phrases par lots. NLLB est entraîné au niveau de
    la phrase : lui donner un paragraphe entier provoque des omissions."""
    tokenizer.src_lang = FLORES[src]
    out = []
    for i in range(0, len(sentences), BATCH_SIZE):
        batch = sentences[i : i + BATCH_SIZE]
        inputs = tokenizer(
            batch, return_tensors="pt", padding=True, truncation=True, max_length=512
        ).to(device)
        generated = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(FLORES[tgt]),
            max_length=512,
        )
        out.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
    return out


def translate(text: str, src: str, tgt: str) -> str:
    """Traduit en préservant les paragraphes, phrase par phrase."""
    if src == tgt:
        return text
    key = hashlib.sha1(
        f"{MODEL_NAME}|{CHUNKING}|{src}|{tgt}|{text}".encode()
    ).hexdigest()
    if key in cache:
        return cache[key]

    out_paragraphs = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            out_paragraphs.append("")
            continue
        sentences = [x for x in _SENT_RE.split(paragraph) if x.strip()]
        out_paragraphs.append(" ".join(_translate_sentences(sentences, src, tgt)))
    result = "\n".join(out_paragraphs)

    # Garde anti-omission : une traduction bien plus courte que la source est suspecte
    if len(result) < 0.6 * len(text):
        print(
            f"    ⚠ traduction {src}->{tgt} anormalement courte "
            f"({len(result)}/{len(text)} car.) — à vérifier en relecture"
        )
    cache[key] = result
    return result


def fill_trilingual(
    cur, table, id_col, src_col, prefix, rows, forced_src=None, keep=None
):
    """Remplit prefix_fr/nl/en pour chaque ligne (id, texte_source).

    forced_src : impose la langue source au lieu de la détecter.
    keep       : dict {lang: colonne_source} — versions existantes à conserver
                 telles quelles (ex : translation_en = translation historique).
    """
    print(f"\n[{table}.{src_col} -> {prefix}_*] {len(rows)} lignes")
    for row_id, src_text, *extra in rows:
        if not src_text or not str(src_text).strip():
            continue
        src_text = str(src_text).strip()
        src = forced_src or detect_lang(src_text)
        values = {}
        for lang in LANGS:
            if keep and lang in keep and extra and extra[0]:
                values[lang] = str(extra[0]).strip()  # version historique conservée
            elif lang == src:
                values[lang] = src_text
            else:
                values[lang] = translate(src_text, src, lang)
        cur.execute(
            f"""UPDATE {table} SET {prefix}_fr = ?, {prefix}_nl = ?, {prefix}_en = ?
                WHERE {id_col} = ?""",
            (values["fr"], values["nl"], values["en"], row_id),
        )
        print(f"  {id_col}={row_id} (source {src}) ✓")


# ----------------------------------------------------------------
# Remplissage table par table
# ----------------------------------------------------------------
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# 1. Questions (source : anglais)
rows = cur.execute("SELECT id, content FROM questions").fetchall()
fill_trilingual(cur, "questions", "id", "content", "content", rows, forced_src="en")
print(
    "  ⚠ Remplacer content_fr / content_nl par les formulations officielles des interviews si disponibles."
)

# 2. Types d'objets (libellés courts, langue mêlée)
rows = cur.execute("SELECT id, name FROM types_of_object").fetchall()
fill_trilingual(cur, "types_of_object", "id", "name", "name", rows)
print("  ⚠ Relire les 28 libellés générés (traduction hors contexte).")

# 3. Descriptions des œuvres (FR ou EN selon l'œuvre)
rows = cur.execute("SELECT id, description FROM artworks").fetchall()
fill_trilingual(cur, "artworks", "id", "description", "description", rows)

# 4. Contexte historique (source : FR)
rows = cur.execute(
    "SELECT id, explanation FROM transcriptions WHERE explanation IS NOT NULL"
).fetchall()
fill_trilingual(
    cur, "transcriptions", "id", "explanation", "explanation", rows, forced_src="fr"
)

# 5. Traduction du texte porté par l'objet.
#    La version EN historique (humaine) est conservée ; FR/NL générés depuis
#    le texte original de l'objet quand il est en français, sinon depuis l'EN.
rows = cur.execute("""SELECT id, transcription, translation FROM transcriptions
       WHERE translation IS NOT NULL""").fetchall()
print(f"\n[transcriptions.translation -> translation_*] {len(rows)} lignes")
for row_id, original, historical_en in rows:
    original = (original or "").strip()
    historical_en = historical_en.strip()
    src_lang = detect_lang(original) if original else "en"
    base = original if (original and src_lang == "fr") else historical_en
    base_lang = "fr" if (original and src_lang == "fr") else "en"
    values = {
        "en": historical_en,  # traduction humaine conservée
        "fr": base if base_lang == "fr" else translate(base, base_lang, "fr"),
        "nl": translate(base, base_lang, "nl"),
    }
    cur.execute(
        """UPDATE transcriptions SET translation_fr = ?, translation_nl = ?, translation_en = ?
           WHERE id = ?""",
        (values["fr"], values["nl"], values["en"], row_id),
    )
    print(f"  id={row_id} (base {base_lang}) ✓")

con.commit()
CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

# ----------------------------------------------------------------
# Vérification
# ----------------------------------------------------------------
print("\n=== Vérification ===")
for table, prefix in [
    ("questions", "content"),
    ("types_of_object", "name"),
    ("artworks", "description"),
    ("transcriptions", "explanation"),
    ("transcriptions", "translation"),
]:
    total, filled = cur.execute(
        f"SELECT COUNT(*), SUM({prefix}_fr IS NOT NULL AND {prefix}_nl IS NOT NULL "
        f"AND {prefix}_en IS NOT NULL) FROM {table}"
    ).fetchone()
    print(f"  {table}.{prefix}_* : {filled or 0}/{total} complets")
con.close()
print(f"\n✓ Terminé. Cache : {CACHE_PATH} ({len(cache)} traductions)")
