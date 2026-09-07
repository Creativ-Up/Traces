# Traces — PP1 Collection Database

Base SQLite du Pilot Projet 1 (Photomaton), peuplée et prête à l'emploi pour le
backend. Le visiteur choisit sa langue (FR/NL/EN) en début de session : **tout
contenu affiché existe en trois versions** (colonnes `_fr` / `_nl` / `_en`).

La collection réunit **230 œuvres de cinq partenaires** :

| Partenaire                            | Œuvres | IDs       |
| ------------------------------------- | -----: | --------- |
| Maison des collections, Ville de Mons |     99 | 1–120     |
| Abby                                  |     13 | 1–120     |
| Le Fresnoy                            |      4 | 1–120     |
| **Huis van Alijn**                    | **99** | 121–219   |
| **MUMONS**                            | **15** | 220–234   |

## Contenu de la livraison

| Fichier                      | Rôle                                                              |
| ---------------------------- | ----------------------------------------------------------------- |
| `pp1_collection.db`          | La base SQLite complète, peuplée et prête à l'emploi (**V10**)    |
| `schema.sql`                 | Le DDL en SQL pur (pour recréer la base from scratch si besoin)   |
| `SCHEMA.md`                  | La documentation détaillée du schéma                              |
| `PP1-Collection_Database.xlsx` | L'Excel de référence consolidé (230 lignes, tous partenaires)   |
| `review_translations.xlsx`   | Le classeur de relecture des traductions (source de vérité des textes) |
| `pp1_to_sqlite.py`           | Étape 1 — migration depuis le fichier Excel source                |
| `translate_content.py`       | Étape 2 — traductions automatiques NLLB-200 (colonnes `_fr/_nl/_en`) |
| `compute_embeddings.py`      | Étape 3 — vecteurs sémantiques (`description_fr`)                 |
| `migrate_v3.py`              | **Le seul script rejouable** — ré-import des traductions relues (descriptions, mots-clés, titres, transcriptions, témoignages, émotions) |
| `migrate_v4.py` … `migrate_v10.py` | Migrations ponctuelles, déjà appliquées (voir « Historique ») |
| `prepare_media.py`           | Conversion des médias musée (TIF/PNG → JPG, vidéos, vignettes) vers `assets/` |
| `check_images.py`            | Contrôle d'intégrité DB ↔ `assets/` (exit code 1 si référence cassée) |
| `matching_report.csv`        | Mapping œuvre → images (une ligne par œuvre) pour vérification humaine |
| `media_mapping_hva.csv`, `media_mapping_mumons.csv` | Correspondance fichier d'origine → fichier converti |

> **Les médias sont versionnés dans `assets/`** (à la racine du monorepo), et
> non plus sur un Drive partagé.

## Historique des migrations

`migrate_v3.py` est **le seul script destiné à être relancé** : à chaque retour
de relecture du musée, on met à jour `review_translations.xlsx` puis on le
rejoue (il est idempotent). Les autres sont des migrations ponctuelles, déjà
appliquées à la base versionnée ; elles ne servent qu'à reconstruire depuis un
état antérieur.

| Version | Objet |
| ------- | ----- |
| **V3**  | Ré-import des traductions relues, référentiel `emotions`, `keywords_*`, `thumbnail_url`, normalisation `media_url` |
| **V4**  | Ajout de `artworks.title` / `title_fr/nl/en` |
| **V5**  | Réparation du point d'extension de `media_url` (corrigé à la racine dans V3 depuis) |
| **V6**  | `artwork_id` sur les témoignages enregistrés : chacun est rattaché à **une** œuvre de sa question (répartition équilibrée, option validée par le musée) |
| **V7**  | Retrait de l'œuvre 15 (MSK_1199), sans média ni question |
| **V8**  | Fusion des témoignages enregistrés dans `testimonies` (`visitor_id IS NULL`) ; `recorded_testimonies` supprimée |
| **V9**  | `artworks.author` (Excel musée) et remplissage des titres i18n via la feuille « Titres » du classeur |
| **V10** | Intégration des collections **Huis van Alijn** (99) et **MUMONS** (15) : médias convertis, vidéos, `origin` renseignée |

## Mettre à jour sa copie locale

```bash
git pull
# la base à jour est dans database/pp1_collection.db
```

Rien d'autre à faire : la DB est versionnée directement dans le repo. Pour les
requêtes vectorielles, voir la section sqlite-vec ci-dessous.

### Cas du kiosque

Sur une machine kiosque, `pp1_collection.db` est modifiée en continu à
l'exécution (visiteurs, témoignages, résumés) : un `git pull` brut écraserait
ou entrerait en conflit avec ces écritures locales. Utiliser à la place :

- `scripts/update.sh` — pull du monorepo en conservant la DB locale du
  kiosque (elle est mise de côté puis restaurée après coup ; la version
  d'origin atterrit quand même dans l'historique Git, juste jamais appliquée
  à la copie de travail).
- `scripts/sync-db.sh` — commit + push de la DB locale vers `origin/main`, à
  lancer manuellement de temps en temps pour remonter les données collectées.

Les deux scripts sont à exécuter à la main, comme les autres scripts du
dossier `scripts/` — aucun timer n'est configuré.

## Vue d'ensemble du schéma

11 tables + 1 vue, deux familles :

**Données de référence** (peuplées depuis l'Excel et la relecture) :

- `artworks` — 230 œuvres : titres i18n, descriptions i18n, mots-clés i18n,
  auteur, provenance (`origin`), dates, médias, vignette, vecteurs
- `transcriptions` — 85 transcriptions liées aux œuvres (1:0..1), traductions
  et explications i18n
- `artwork_emotions` — 595 émotions Plutchik normalisées (jointure pour Jaccard)
- `emotions` — référentiel i18n des 32 libellés d'émotions
- `types_of_object` — 27 types d'objets (vocabulaire contrôlé, i18n)
- `questions` — 12 questions de référence du parcours visiteur (i18n)

**Données dynamiques** (remplies au runtime par le backend) :

- `visitors` — sessions visiteurs éphémères (PK = UUID de session)
- `visitor_artwork_views` — historique de consultation
- `testimonies` — témoignages : les **150 interviews** collectées (Mons, Lens,
  Kortrijk) y cohabitent avec ceux des visiteurs, distinguées par
  `visitor_id IS NULL` (**V8**)
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

> Si les descriptions **françaises** sont modifiées (retour du musée sur la
> relecture), relancer `compute_embeddings.py` pour resynchroniser les vecteurs.
> Une correction NL ou EN seule n'affecte pas les vecteurs.

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

> **La langue source varie d'une œuvre à l'autre**, y compris au sein d'un même
> partenaire : Huis van Alijn a rédigé une partie de ses descriptions en
> néerlandais et une partie en français. Ne jamais déduire la langue d'un texte
> de sa provenance — les colonnes i18n sont toutes remplies, utiliser celle de
> la langue de session.

### 4. Médias : images et vidéos

`media_url` liste un ou plusieurs fichiers de `assets/`, séparés par `, `.
**Le type se déduit de l'extension** : `.jpg` → image, `.mp4` → vidéo (le front
rend une balise `<video>`). `thumbnail_url` désigne toujours une image, y
compris pour les œuvres purement vidéo (vignette `*-thumb.jpg` extraite de la
première seconde par `prepare_media.py`).

Formats retenus avec les musées : **JPEG** pour les photos, **MP4 (H.264)**
pour les vidéos. Les masters (TIF, MOV, NEF) restent chez les partenaires.

### 5. Contraintes métier matérialisées en SQL

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

- 230 œuvres, toutes datées, toutes avec médias et toutes avec un titre i18n
- 230 vecteurs d'embedding
- 6 œuvres vidéo (Huis van Alijn), avec vignette dédiée
- 85 transcriptions dont 71 avec traduction de billet et 35 avec explication
- 150 témoignages enregistrés, 32 libellés d'émotions traduits
- `author` renseigné pour 14 œuvres, `author_name` pour 99 : deux colonnes
  distinctes issues de l'Excel (« Author » et « Name »). Pour l'affichage,
  utiliser `COALESCE(author, author_name)`.

### Points à connaître

- **IDs manquants** : les œuvres 8, 12 et 50 sont absentes (items supprimés
  volontairement après attribution des IDs), ainsi que l'œuvre 15 (retirée en
  **V7** : aucun média). La ligne 15 subsiste dans le classeur de relecture —
  `migrate_v3.py` la saute donc : « 1 id keywords sans correspondance » est le
  rapport **normal**, pas une régression.
- **Coquilles de dates** : « 1800-1851 » et « 1800-1852 » dans la source sont
  probablement des erreurs pour « 1800-1850 ». Acceptées telles quelles.
- **Anomalies médias** (en attente d'arbitrage musée) : 2 photos
  `JL.2022.0.65` sans œuvre en base ; `imadeyou-06-1243.jpg` non référencée par
  l'œuvre 1 ; les œuvres 56 et 64 partagent les mêmes 5 photos (fidèle à
  l'Excel source). Vérifiable à tout moment :
  `python check_images.py --db pp1_collection.db --images ../assets`
- **Relecture continue** : les traductions des collections Huis van Alijn et
  MUMONS ont été produites en première passe puis relues par les partenaires.
  En cas de nouvel amendement, mettre à jour `review_translations.xlsx` puis
  relancer `migrate_v3.py`.
