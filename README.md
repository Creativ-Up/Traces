## Contenu de la livraison

| Fichier | Rôle |
|---|---|
| `pp1_collection.db` | La base SQLite complète, peuplée et prête à l'emploi     |
| `schema.sql` | Le DDL en SQL pur (pour recréer la base from scratch si besoin) |
| `pp1_to_sqlite.py` | Le script de migration depuis le fichier Excel source     |
| `compute_embeddings.py` | Le script qui a calculé les vecteurs sémantiques     |
| `SCHEMA.md` | La documentation détaillée du schéma                             |

## Vue d'ensemble du schéma

10 tables, deux familles :

**Données de référence** (peuplées depuis l'Excel) :
- `artworks` — 117 œuvres avec descriptions, mots-clés, dates, émotions, vecteurs
- `transcriptions` — 85 transcriptions liées aux œuvres (1:0..1)
- `artwork_emotions` — 346 émotions Plutchik normalisées (table de jointure pour Jaccard)
- `types_of_object` — 28 types d'objets (vocabulaire contrôlé)
- `questions` — 12 questions de référence pour le parcours visiteur

**Données dynamiques** (vides, à remplir au runtime par le backend) :
- `visitors` — sessions visiteurs éphémères (PK = UUID de session)
- `visitor_artwork_views` — historique de consultation
- `testimonies` — témoignages laissés sur les œuvres
- `summaries` — résumés LLM générés en fin de parcours
- `staff` — modérateurs des témoignages

Le diagramme complet, les colonnes, les contraintes sont dans `SCHEMA.md`.

## Choix techniques importants

### 1. SQLite + sqlite-vec pour les embeddings

La colonne `artworks.description_vector` contient un embedding sémantique de la
description (768 dimensions, modèle `paraphrase-multilingual-mpnet-base-v2`,
multilingue FR/EN). Tu peux faire des requêtes de similarité directement en SQL :

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect("pp1_collection.db")
conn.execute("PRAGMA foreign_keys = ON")           
conn.enable_load_extension(True)
sqlite_vec.load(conn)                              # active vec_distance_*, vec_f32, etc.

# Œuvre la plus proche sémantiquement de l'œuvre #1
conn.execute("""
    SELECT a.id, vec_distance_cosine(a.description_vector,
                                     (SELECT description_vector FROM artworks WHERE id = 1))
    FROM artworks a
    WHERE a.id != 1
    ORDER BY 2 ASC LIMIT 1
""").fetchone()
```

Si tu as besoin d'encoder de nouveaux textes au runtime (pour matcher un témoignage
contre les œuvres par exemple), il faut installer `sentence-transformers` et charger
le même modèle. Sinon, `sqlite-vec` seul suffit.

### 2. Algorithme de matching à 4 critères

Le parcours visiteur prévoit, à partir d'une œuvre de référence, de proposer 4 œuvres :
une proche en **type**, une en **description** (via vecteur), une en **émotions**
(Jaccard ou autre sur `artwork_emotions`), une en **date** (distance entre centres
d'intervalles via `date_year_min` / `date_year_max`).

### 3. Pas d'`AUTOINCREMENT`

Toutes les clés primaires utilisent `INTEGER PRIMARY KEY` simple. SQLite gère
l'auto-incrémentation via `rowid` sans table `sqlite_sequence`. 

### 4. Contraintes métier matérialisées en SQL

Plutôt que de laisser tout vérifier côté application, certaines règles sont imposées
au niveau du schéma :

- `UNIQUE (visitor_id, artwork_id)` sur `testimonies` → un visiteur ne peut laisser
  qu'un seul témoignage par œuvre.
- `UNIQUE artwork_id` sur `transcriptions` → relation 1:0..1.
- `UNIQUE visitor_id` sur `summaries` → un seul résumé par visiteur (le résumé LLM
  est généré en fin de parcours, pas plusieurs fois).
- `CHECK status IN ('pending', 'validated', 'censored')` sur `testimonies`.
- `CHECK consent_given IN (0, 1)` sur `testimonies`.

**Règle métier non matérialisée** (à imposer côté backend) : un témoignage n'est
visible aux autres visiteurs que si `status = 'validated'` ET `consent_given = 1`.

## Données et qualité

### Ce qui est en base

- 117 œuvres, 116 avec date parsée correctement (1 sans date renseignée à la source)
- 117 vecteurs d'embedding calculés
- 85 transcriptions

### Points de qualité à connaître

- **IDs manquants** : les œuvres 8, 12 et 50 sont absentes de la table principale.
  Ce sont des items supprimés volontairement après attribution de leurs IDs.

- **Coquilles de dates** : « 1800-1851 » et « 1800-1852 » dans la source sont
  probablement des erreurs pour « 1800-1850 ». Le parser les accepte tels quels mais
  ça fait des intervalles bizarres. À voir si on demande correction.

- **Matching des questions** : les questions présentes dans `artworks` (en texte
  libre) ont été matchées aux 12 questions de référence via une similarité textuelle
  (`difflib`) pour absorber les variantes orthographiques (« favorite »/« favourite »,
  espaces parasites…). Tous les items ont été matchés sauf 1 sans question
  renseignée. 