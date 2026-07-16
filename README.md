# Traces — PP1 Collection Database

Base SQLite du Pilot Projet 1 (Photomaton), peuplée et prête à l'emploi pour le
backend. Le visiteur choisit sa langue (FR/NL/EN) en début de session : **tout
contenu affiché existe en trois versions** (colonnes `_fr` / `_nl` / `_en`).

## Contenu de la livraison

| Fichier                 | Rôle                                                              |
| ----------------------- | ----------------------------------------------------------------- |
| `pp1_collection.db`     | La base SQLite complète, peuplée et prête à l'emploi (**V3**)     |
| `schema.sql`            | Le DDL en SQL pur (pour recréer la base from scratch si besoin)   |
| `SCHEMA.md`             | La documentation détaillée du schéma                              |
| `pp1_to_sqlite.py`      | Étape 1 — migration depuis le fichier Excel source                |
| `translate_content.py`  | Étape 2 — traductions automatiques NLLB-200 (colonnes `_fr/_nl/_en`) |
| `compute_embeddings.py` | Étape 3 — vecteurs sémantiques (`description_fr`)                 |
| `migrate_v3.py`         | Étape 4 — **V3** : ré-import des traductions relues/corrigées, référentiel `emotions`, `keywords_*`, `thumbnail_url`, normalisation `media_url` |
| `check_images.py`       | Contrôle d'intégrité DB ↔ dossier d'images (exit code 1 si référence cassée) |
| `matching_report.csv`   | Mapping œuvre → images (une ligne par œuvre) pour vérification humaine |
| *(Drive partagé)*       | Les 261 images renommées (`pictures_data_renamed.zip`) sont hébergées hors Git — voir le lien dans le canal du projet |

## Nouveautés (juillet 2026)

- **`artworks.thumbnail_url`** : vignette de l'œuvre, remplie pour les 116
  œuvres avec images (= la vue principale, nom le plus court).
- **`artworks.media_url` normalisé et résolu** : noms en minuscules, seuls
  `[a-z0-9-]` conservés, extensions réelles incluses
  (`IMadeYou_01_053` → `imadeyou-01-053.jpg`). Le matching images ↔ œuvres a été
  reconstruit (réfs Excel re-splittées + numéro d'inventaire `museum_id`) ; les
  fichiers du dossier d'images partagé (Drive) portent les mêmes noms. Vérifiable à
  tout moment : `python check_images.py --db pp1_collection.db --images <dossier>`.
  Anomalies connues (en attente d'arbitrage musée) : œuvre 15 (MSK_1199) sans
  aucune photo ; 2 photos `JL.2022.0.65` sans œuvre en base ;
  `imadeyou-06-1243.jpg` non référencée par l'œuvre 1 ; œuvres 56 et 64
  partagent les mêmes 5 photos (fidèle à l'Excel source).
- **Nouvelle table `emotions`** : référentiel i18n des émotions Plutchik
  (`emotion`, `name_fr`, `name_nl`, `name_en`), jointure sur
  `artwork_emotions.emotion`. Typos de données corrigées
  (`submision`→`submission`, `dissaproval`→`disapproval`).
- **`artworks.keywords_fr/nl/en`** : mots-clés affichables traduits
  (la colonne `keywords` d'origine reste pour usage interne/matching).
- **anonymisation de `recorded_testimonies`** : colonnes `speaker` et
  `source_file` supprimées, remplacées par `created_at` (date d'enregistrement,
  ISO `YYYY-MM-DD`). La correspondance avec les fichiers audio d'origine est
  conservée hors base dans `migrate_v3.py` (`RECORDED_IDS`), qui reste la clé
  de ré-import des traductions. Côté visiteurs, `visitors.surname` est
  supprimée (plus de saisie du prénom) et `testimonies.city` ajoutée : tout
  témoignage est identifié par le couple (ville, date), qu'expose la vue
  `artwork_published_testimonies` — plus aucun prénom nulle part.

## Mettre à jour sa copie locale

```bash
git pull
# la base à jour est à la racine : pp1_collection.db
```

Rien d'autre à faire : la DB est versionnée directement dans le repo. Pour les
requêtes vectorielles, voir la section sqlite-vec ci-dessous.

## Vue d'ensemble du schéma

12 tables + 1 vue, trois familles :

**Données de référence** (peuplées depuis l'Excel et la relecture) :

- `artworks` — 117 œuvres : descriptions i18n, mots-clés i18n, dates, médias,
  vignette, vecteurs
- `transcriptions` — 85 transcriptions liées aux œuvres (1:0..1), traductions
  et explications i18n
- `artwork_emotions` — 346 émotions Plutchik normalisées (jointure pour Jaccard)
- `emotions` — référentiel i18n des libellés d'émotions (**V3**)
- `types_of_object` — 28 types d'objets (vocabulaire contrôlé, i18n)
- `questions` — 12 questions de référence du parcours visiteur (i18n)
- `recorded_testimonies` — 155 témoignages oraux collectés (Mons, Lens,
  Kortrijk), traduits FR/NL/EN

**Données dynamiques** (vides, remplies au runtime par le backend) :

- `visitors` — sessions visiteurs éphémères (PK = UUID de session)
- `visitor_artwork_views` — historique de consultation
- `testimonies` — témoignages laissés par les visiteurs (i18n, modération)
- `summaries` — résumés LLM générés en fin de parcours
- `staff` — modérateurs des témoignages
- `artwork_published_testimonies` — vue des témoignages publiables
  (`status='validated' AND consent_given=1`)

Le diagramme complet, les colonnes et les contraintes sont dans `SCHEMA.md`.

## Choix techniques importants

### 1. SQLite + sqlite-vec pour les embeddings

La colonne `artworks.description_vector` contient un embedding sémantique de
`description_fr` (768 dimensions, modèle `paraphrase-multilingual-mpnet-base-v2`).
Requêtes de similarité directement en SQL :

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect("pp1_collection.db")
conn.execute("PRAGMA foreign_keys = ON")
conn.enable_load_extension(True)
sqlite_vec.load(conn)

# Œuvre la plus proche sémantiquement de l'œuvre #1
conn.execute("""
    SELECT a.id, vec_distance_cosine(a.description_vector,
                                     (SELECT description_vector FROM artworks WHERE id = 1))
    FROM artworks a
    WHERE a.id != 1
    ORDER BY 2 ASC LIMIT 1
""").fetchone()
```

> Si les descriptions sont modifiées (retour du musée sur la relecture),
> relancer `compute_embeddings.py` pour resynchroniser les vecteurs.

### 2. Algorithme de matching à 4 critères

À partir d'une œuvre de référence, proposer 4 œuvres : une proche en **type**,
une en **description** (vecteur), une en **émotions** (Jaccard sur
`artwork_emotions`), une en **date** (distance entre centres d'intervalles via
`date_year_min` / `date_year_max`).

### 3. Affichage multilingue

Règle générale : afficher `X_fr` / `X_nl` / `X_en` selon la langue de session ;
la colonne sans suffixe est la source (traçabilité, usage interne). Pour les
émotions : `JOIN emotions ON artwork_emotions.emotion = emotions.emotion` puis
`name_fr/nl/en`.

### 4. Contraintes métier matérialisées en SQL

- `UNIQUE (visitor_id, artwork_id)` sur `testimonies` → un témoignage par œuvre
  et par visiteur.
- `UNIQUE artwork_id` sur `transcriptions` → relation 1:0..1.
- `UNIQUE visitor_id` sur `summaries` → un seul résumé par visiteur.
- `CHECK status IN ('pending', 'validated', 'censored')` et
  `CHECK consent_given IN (0, 1)` sur `testimonies`.

**Règle non matérialisée** (côté backend) : un témoignage n'est visible aux
autres visiteurs que si `status='validated'` **et** `consent_given=1`
(la vue `artwork_published_testimonies` encapsule cette règle).

## Données et qualité

- 117 œuvres, 116 avec date (1 sans date à la source), 116 avec médias
- 117 vecteurs d'embedding
- 85 transcriptions dont 71 avec traduction de billet et 35 avec explication
- 155 témoignages enregistrés, 25 libellés d'émotions traduits

### Points à connaître

- **IDs manquants** : les œuvres 8, 12 et 50 sont absentes (items supprimés
  volontairement après attribution des IDs).
- **Coquilles de dates** : « 1800-1851 » et « 1800-1852 » dans la source sont
  probablement des erreurs pour « 1800-1850 ». Acceptées telles quelles.
- **Relecture en cours de validation** : les traductions corrigées sont en
  vérification côté musée. En cas d'amendements, mettre à jour
  `review_translations.xlsx` puis relancer `migrate_v3.py` (idempotent).
- **11 libellés d'émotions** ajoutés en traduction Plutchik standard (absents de
  la feuille de relecture) : à faire valider.
