"""
compute_embeddings.py

Computes the semantic embeddings of the artwork descriptions (description_fr,
or the original description when there is no French version yet) and stores
them in `artworks.description_vector`, in the sqlite-vec format.
The kiosk uses them to pick related artworks. REQUIRED after adding artworks:
the kiosk server does not start if an artwork has no vector.

Model: paraphrase-multilingual-mpnet-base-v2 (768 dimensions, FR/EN/NL and 50+ languages)
Format: float32 BLOB serialised with sqlite_vec.serialize_float32
Recommended distance for matching: cosine (vec_distance_cosine)

Requirements:
    pip install sentence-transformers sqlite-vec numpy

Usage:
    python compute_embeddings.py [db_path]
    Default: pp1_collection.db

The first run downloads the model (~1 GB) from Hugging Face; later runs use
the local cache (~/.cache/huggingface/).
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import sqlite_vec
from sentence_transformers import SentenceTransformer

DEFAULT_DB = "pp1_collection.db"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


def main(db_path: Path) -> None:
    print(f"[1/5] Loading the model: {MODEL_NAME}")
    print("      (~1 GB download on the first run, then local cache)")
    model = SentenceTransformer(MODEL_NAME)
    embed_dim = (getattr(model, 'get_embedding_dimension', None) or model.get_sentence_embedding_dimension)()
    print(f"      Vector size: {embed_dim}")

    print(f"\n[2/5] Opening the database and loading sqlite-vec: {db_path}")
    conn = sqlite3.connect(db_path)
    # The extension is only needed for the final check: some Python builds
    # (macOS in particular) cannot load SQLite extensions; vectors are written
    # anyway (serialize_float32 does not need it).
    vec_loaded = False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        vec_loaded = True
    except (AttributeError, sqlite3.OperationalError) as exc:
        print(f"      sqlite-vec not loaded ({exc}): final check skipped")
    cur = conn.cursor()

    print(f"\n[3/5] Reading the descriptions to encode")
    rows = cur.execute(
        "SELECT id, COALESCE(description_fr, description) FROM artworks "
        "WHERE description IS NOT NULL ORDER BY id"
    ).fetchall()
    ids = [r[0] for r in rows]
    descriptions = [r[1] for r in rows]
    print(f"      {len(ids)} descriptions found")

    print(f"\n[4/5] Encoding")
    embeddings = model.encode(
        descriptions,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    print(
        f"      Embeddings: shape={embeddings.shape}, dtype={embeddings.dtype}"
    )

    print(f"\n[5/5] Writing the vectors into artworks.description_vector")
    updates = [
        (sqlite_vec.serialize_float32(vec.tolist()), artwork_id)
        for artwork_id, vec in zip(ids, embeddings)
    ]
    cur.executemany("UPDATE artworks SET description_vector = ? WHERE id = ?", updates)
    conn.commit()

    n_filled = cur.execute(
        "SELECT COUNT(*) FROM artworks WHERE description_vector IS NOT NULL"
    ).fetchone()[0]
    n_total = cur.execute("SELECT COUNT(*) FROM artworks").fetchone()[0]
    print(f"      {n_filled} / {n_total} artworks with a vector")

    if not vec_loaded:
        conn.close()
        print(f"\n✓ Embeddings computed and stored in {db_path.resolve()}")
        print(f"  → next step: python check_collection.py --db {db_path} --images ../assets")
        return

    # --- Sanity check: the 5 closest artworks to a sample artwork ---
    sample_id = ids[0]
    print(
        f"\n=== Check: the 5 artworks closest in meaning to artwork #{sample_id} ==="
    )
    sample_desc = cur.execute(
        "SELECT description FROM artworks WHERE id = ?", (sample_id,)
    ).fetchone()[0]
    print(f"Reference description: {sample_desc[:200]}...\n")

    results = cur.execute(
        """
        SELECT a.id,
               vec_distance_cosine(
                   a.description_vector,
                   (SELECT description_vector FROM artworks WHERE id = ?)
               ) AS dist,
               substr(a.description, 1, 100) AS preview
        FROM artworks a
        WHERE a.id != ? AND a.description_vector IS NOT NULL
        ORDER BY dist ASC
        LIMIT 5
    """,
        (sample_id, sample_id),
    ).fetchall()

    for artwork_id, dist, preview in results:
        print(f"  #{artwork_id:<3}  dist={dist:.4f}  {preview!r}")

    conn.close()
    print(f"\n✓ Embeddings computed and stored in {db_path.resolve()}")
    print(f"  → next step: python check_collection.py --db {db_path} --images ../assets")


if __name__ == "__main__":
    db_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB)
    if not db_path.exists():
        sys.exit(f"database not found: {db_path.resolve()}")
    main(db_path)
