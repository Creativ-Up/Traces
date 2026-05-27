"""
PP1 Collection Database — Migration Excel -> SQLite

Construit la base SQLite selon le schéma défini dans schema.sql.

Usage :
    python pp1_to_sqlite.py [chemin_xlsx] [chemin_db] [chemin_schema_sql]
"""

import re
import sqlite3
import sys
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

DEFAULT_XLSX = "PP1-Collection_Database.xlsx"
DEFAULT_DB = "pp1_collection.db"
DEFAULT_SCHEMA = "schema.sql"


# =========================
# PARSING DES DATES
# =========================
def parse_date_period(text) -> tuple[int | None, int | None]:
    """Convertit une valeur 'Date /period' en (year_min, year_max).

    Formats gérés (basés sur les 40 variantes présentes dans le fichier source) :
        "1830"                        -> (1830, 1830)
        "1800-1850"                   -> (1800, 1850)
        "20th century"                -> (1900, 1999)
        "first half 20th century"     -> (1900, 1949)
        "second half / early / mid / late 20th century" idem
    Retourne (None, None) si le format n'est pas reconnu.
    """
    if not text or pd.isna(text):
        return (None, None)
    s = str(text).strip().lower()

    m = re.fullmatch(r"(\d{4})", s)
    if m:
        y = int(m.group(1))
        return (y, y)

    m = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s+century", s)
    if m:
        century = int(m.group(1))
        start = (century - 1) * 100
        end = start + 99
        if "first half" in s:
            return (start, start + 49)
        if "second half" in s:
            return (start + 50, end)
        if "early" in s:
            return (start, start + 33)
        if "mid" in s:
            return (start + 33, start + 66)
        if "late" in s:
            return (start + 66, end)
        return (start, end)

    return (None, None)


# =========================
# UTILITAIRES
# =========================
def split_csv_field(value) -> list[str]:
    if pd.isna(value):
        return []
    return [p.strip() for p in str(value).split(",") if p.strip()]


def normalize_question_match(text: str) -> str:
    if not text:
        return ""
    return " ".join(str(text).lower().split()).rstrip("?.! ")


def match_question(
    text,
    reference_questions: dict[int, str],
    threshold: float = 0.55,
    margin: float = 0.15,
) -> int | None:
    if pd.isna(text) or not text:
        return None
    norm = normalize_question_match(text)
    scores = sorted(
        (
            (qid, SequenceMatcher(None, norm, q_norm).ratio())
            for qid, q_norm in reference_questions.items()
        ),
        key=lambda x: x[1],
        reverse=True,
    )
    if not scores:
        return None
    best_id, best_score = scores[0]
    second = scores[1][1] if len(scores) > 1 else 0.0
    return (
        best_id if best_score >= threshold and (best_score - second) >= margin else None
    )


def cell(value):
    """Convertit une cellule pandas en valeur SQL (None pour NaN, str strippé sinon)."""
    if pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


# =========================
# IMPORT
# =========================
def build_database(xlsx_path: Path, db_path: Path, schema_path: Path) -> None:
    print(f"[1/4] Lecture des sources")
    print(f"  Excel  : {xlsx_path}")
    print(f"  Schéma : {schema_path}")
    items_df = pd.read_excel(xlsx_path, sheet_name="Database", header=1)
    transcr_df = pd.read_excel(xlsx_path, sheet_name="Transcriptions", header=1)
    questions_df = pd.read_excel(xlsx_path, sheet_name="List of questions", header=1)
    types_df = pd.read_excel(xlsx_path, sheet_name="Type of object", header=None)
    types_df.columns = ["name"]
    questions_df.columns = ["id", "content"]
    schema_sql = schema_path.read_text(encoding="utf-8")

    print(f"\n[2/4] Création du schéma : {db_path}")
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    cur = conn.cursor()

    # --- Tables de référence ---
    print(f"\n[3/4] Insertion des données")
    types_clean = list(types_df["name"].dropna().str.strip().unique())
    extra = set(items_df["Type of object"].dropna().str.strip()) - set(types_clean)
    types_clean.extend(sorted(extra))
    cur.executemany(
        "INSERT INTO types_of_object (name) VALUES (?)", [(t,) for t in types_clean]
    )
    type_id_by_name = dict(cur.execute("SELECT name, id FROM types_of_object"))

    cur.executemany(
        "INSERT INTO questions (id, content) VALUES (?, ?)",
        [
            (int(r["id"]), str(r["content"]).strip())
            for _, r in questions_df.dropna(subset=["id", "content"]).iterrows()
        ],
    )
    reference_questions = {
        int(r["id"]): normalize_question_match(r["content"])
        for _, r in questions_df.dropna(subset=["id", "content"]).iterrows()
    }
    print(f"  types_of_object : {len(types_clean)}")
    print(f"  questions       : {len(reference_questions)}")

    # --- Artworks ---
    artworks_inserted = 0
    dates_unparsed = 0
    questions_unmatched = 0
    emotions_inserted = 0

    for _, row in items_df.iterrows():
        if pd.isna(row["Database ID"]):
            continue
        artwork_id = int(row["Database ID"])
        type_id = type_id_by_name.get(cell(row["Type of object"]))
        question_id = match_question(row.get("Question"), reference_questions)
        if pd.notna(row.get("Question")) and question_id is None:
            questions_unmatched += 1

        date_text = cell(row["Date /period"])
        ymin, ymax = parse_date_period(date_text)
        if date_text and ymin is None:
            dates_unparsed += 1

        cur.execute(
            """
            INSERT INTO artworks (
                id, keywords, description, description_vector, media_url,
                date_period, date_year_min, date_year_max,
                type_of_object_id, emotions, origin,
                author_name, birthday, places, storage_place,
                popularity, question_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artwork_id,
                cell(
                    row["Description, Key words"]
                ),  # keywords (Excel: "Description, Key words")
                cell(
                    row["Explanation"]
                ),  # description (Excel: "Explanation") — base du vecteur
                None,  # description_vector — calculé plus tard
                cell(row["PHOTO"]),  # media_url
                date_text,
                ymin,
                ymax,
                type_id,
                cell(row["Pulchik's wheel match"]),  # emotions (Plutchik concaténé)
                cell(row["Origin"]),
                cell(row["Name"]),
                cell(row["birthday"]),
                cell(row["Places"]),
                cell(row["Storage place"]),
                0,  # popularity initial
                question_id,
            ),
        )
        artworks_inserted += 1

        # Émotions normalisées (Plutchik) -> table de jointure pour Jaccard
        for emotion in split_csv_field(row["Pulchik's wheel match"]):
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO artwork_emotions (artwork_id, emotion) VALUES (?, ?)",
                    (artwork_id, emotion.lower()),
                )
                emotions_inserted += 1
            except sqlite3.IntegrityError:
                pass

    print(f"  artworks         : {artworks_inserted}")
    print(f"  artwork_emotions : {emotions_inserted}")
    if questions_unmatched:
        print(f"  ⚠ {questions_unmatched} item(s) avec question non matchée")
    if dates_unparsed:
        print(f"  ⚠ {dates_unparsed} date(s) non parsée(s)")

    # --- Transcriptions (1:0..1) ---
    existing_ids = {row[0] for row in cur.execute("SELECT id FROM artworks")}
    transcr_inserted = 0
    orphan = 0
    seen_artworks = set()
    duplicates = 0

    for _, row in transcr_df.iterrows():
        if pd.isna(row["Database ID"]):
            continue
        artwork_id = int(row["Database ID"])
        if artwork_id not in existing_ids:
            orphan += 1
            continue
        has_content = any(
            pd.notna(row[c]) for c in ["Transcriptions", "Explanation", "Translation"]
        )
        if not has_content:
            continue
        if artwork_id in seen_artworks:
            duplicates += 1
            continue
        cur.execute(
            """INSERT INTO transcriptions (artwork_id, transcription, explanation, translation)
               VALUES (?, ?, ?, ?)""",
            (
                artwork_id,
                cell(row["Transcriptions"]),
                cell(row["Explanation"]),
                cell(row["Translation"]),
            ),
        )
        seen_artworks.add(artwork_id)
        transcr_inserted += 1

    print(f"  transcriptions   : {transcr_inserted}")
    if orphan:
        print(f"  ⚠ {orphan} transcription(s) orpheline(s) ignorée(s)")
    if duplicates:
        print(
            f"  ⚠ {duplicates} transcription(s) dupliquée(s) ignorée(s) "
            "(la contrainte 1:0..1 n'accepte qu'une transcription par œuvre)"
        )

    conn.commit()

    # --- Vérification ---
    print(f"\n[4/4] Vérification")
    for table in [
        "artworks",
        "transcriptions",
        "types_of_object",
        "questions",
        "artwork_emotions",
        "visitors",
        "testimonies",
        "summaries",
        "staff",
        "visitor_artwork_views",
    ]:
        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<25} {n:>5} lignes")

    print(f"\n✓ Base prête : {db_path.resolve()}")
    conn.close()


if __name__ == "__main__":
    xlsx = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX)
    db = Path(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DB)
    schema = Path(sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SCHEMA)
    for p, label in [(xlsx, "Excel"), (schema, "Schéma SQL")]:
        if not p.exists():
            sys.exit(f"{label} introuvable : {p.resolve()}")
    build_database(xlsx, db, schema)
