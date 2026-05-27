"""
compute_embeddings.py

Calcule les embeddings sémantiques de la colonne `description` (Excel "Explanation")
et les stocke dans `artworks.description_vector` au format compatible sqlite-vec.

Modèle : paraphrase-multilingual-mpnet-base-v2 (768 dimensions, FR/EN/+50 langues)
Format : BLOB float32 sérialisé via sqlite_vec.serialize_float32
Distance recommandée pour le matching : cosinus (vec_distance_cosine)

Prérequis :
    pip install sentence-transformers sqlite-vec numpy

Usage :
    python compute_embeddings.py [chemin_db]
    Défaut : pp1_collection.db

Le premier lancement télécharge le modèle (~1 GB) depuis HuggingFace.
Les lancements suivants utilisent le cache local (~/.cache/huggingface/).
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
    print(f"[1/5] Chargement du modèle : {MODEL_NAME}")
    print("      (téléchargement ~1 GB au premier lancement, puis cache local)")
    model = SentenceTransformer(MODEL_NAME)
    embed_dim = model.get_sentence_embedding_dimension()
    print(f"      Dimension des vecteurs : {embed_dim}")

    print(f"\n[2/5] Connexion à la base et chargement de sqlite-vec : {db_path}")
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    cur = conn.cursor()

    print(f"\n[3/5] Récupération des descriptions à encoder")
    rows = cur.execute(
        "SELECT id, description FROM artworks "
        "WHERE description IS NOT NULL ORDER BY id"
    ).fetchall()
    ids = [r[0] for r in rows]
    descriptions = [r[1] for r in rows]
    print(f"      {len(ids)} descriptions trouvées")

    print(f"\n[4/5] Encodage en batch")
    embeddings = model.encode(
        descriptions,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    print(
        f"      Embeddings produits : shape={embeddings.shape}, dtype={embeddings.dtype}"
    )

    print(f"\n[5/5] Écriture des vecteurs dans artworks.description_vector")
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
    print(f"      {n_filled} / {n_total} items avec un vecteur")

    # --- Vérification qualitative : top 5 plus proches d'une œuvre choisie ---
    sample_id = ids[0]
    print(
        f"\n=== Vérification : top 5 plus proches sémantiquement de l'œuvre #{sample_id} ==="
    )
    sample_desc = cur.execute(
        "SELECT description FROM artworks WHERE id = ?", (sample_id,)
    ).fetchone()[0]
    print(f"Description de référence : {sample_desc[:200]}...\n")

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
    print(f"\n✓ Embeddings calculés et stockés dans {db_path.resolve()}")


if __name__ == "__main__":
    db_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB)
    if not db_path.exists():
        sys.exit(f"Base introuvable : {db_path.resolve()}")
    main(db_path)
