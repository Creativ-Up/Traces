# PP1 Collection Database — Schéma

Documentation technique de `pp1_collection.db` : la base SQLite de TRACES,
versionnée dans ce dossier et lue par le serveur du kiosque. Elle réunit 230
œuvres de cinq partenaires et les 150 interviews recueillies à Mons, Lens et
Courtrai, selon le DDL de `schema.sql`.

Pour ajouter une collection, voir le [README](README.md) (guide en anglais, destiné
aux musées qui intègrent eux-mêmes leur collection).

**Chaîne d'intégration d'une collection** (tout contenu affiché existe en
trois versions, FR / NL / EN, selon la langue choisie par le visiteur) :

```
prepare_media.py          médias du musée -> JPG / MP4 normalisés (+ vignettes vidéo)
import_collection.py      tableur du musée -> artworks, artwork_emotions, transcriptions
translate_collection.py   textes manquants -> DeepL -> review_translations.xlsx (à relire)
import_translations.py    review_translations.xlsx -> colonnes *_fr / *_nl / *_en
compute_embeddings.py     description_fr -> description_vector (obligatoire)
check_collection.py       contrôle avant déploiement (médias, vecteurs, traductions)
```

**Internationalisation** : les colonnes sans suffixe (`description`,
`title`, `keywords`, `name`…) gardent le texte d'origine, dans sa langue.
`import_collection.py` recopie le texte d'origine dans la colonne de sa langue
(`description_nl` pour une notice en néerlandais, par exemple) ; les deux
autres langues sont alimentées par `import_translations.py`, depuis le
classeur de relecture, qui est la source de vérité de tous les textes
affichés.

## Vue d'ensemble

```
                         ┌────────────────┐
                         │   questions    │
                         └────────┬───────┘
                                  │ question_id
                                  ▼
   ┌────────────────┐   ┌────────────────────┐   ┌──────────────────┐
   │ types_of_object│──▶│      artworks      │◀──│  transcriptions  │ 
   └────────────────┘   │ + description_vec  │   └──────────────────┘
                        └────┬───────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       artwork_emotions  testimonies   visitor_artwork_views
                              │              │
                              ▼              ▼
                            staff        visitors ──── summaries 
```

## Tables

### `artworks` — Entité principale (230 lignes)

| Colonne                  | Type    | Notes                                                   |
|--------------------------|---------|---------------------------------------------------------|
| `id`                     | INTEGER | PK = Database ID du fichier source                      |
| `keywords`               | TEXT    | NOT NULL. Excel : « Description, Key words » (mots-clés bruts, usage interne) |
| `description`            | TEXT    | NOT NULL. Excel : « Explanation » — texte source original. **La langue varie par ligne** (FR, NL ou EN selon le partenaire et l'œuvre) : utiliser les colonnes i18n pour l'affichage |
| `description_fr`         | TEXT    | Affichage FR + **base du vecteur** (langue canonique : évite le biais de langue du corpus mixte) |
| `description_nl`         | TEXT    | Affichage NL                                            |
| `description_en`         | TEXT    | Affichage EN                                            |
| `description_vector`     | BLOB    | Embedding sémantique de `description_fr` (via sqlite-vec) — calculé par `compute_embeddings.py`. **Obligatoire** : le serveur ne peut pas lire une œuvre sans vecteur |
| `media_url`              | TEXT    | Noms de fichiers de `assets/`, séparés par `, `. Normalisés : minuscules, `[a-z0-9-]`, extension préservée (`imadeyou-01-053.jpg`). **Le type se déduit de l'extension** : `.jpg` → image, `.mp4` → vidéo (10 œuvres : 6 du Huis van Alijn en **V10**, 4 du Fresnoy en **V11**) |
| `thumbnail_url`          | TEXT    | **V3.** Vignette de l'œuvre, toujours une image. Pour les œuvres purement vidéo, vignette `*-thumb.jpg` extraite par `prepare_media.py` (**V10**) |
| `date_period`            | TEXT    | Forme brute lisible (`"1800-1850"`, `"20th century"`)   |
| `date_year_min`          | INTEGER | Borne basse calculée pour le matching                   |
| `date_year_max`          | INTEGER | Borne haute calculée pour le matching                   |
| `type_of_object_id`      | INTEGER | FK → `types_of_object.id`                               |
| `emotions`               | TEXT    | NOT NULL en pratique. Clés d'émotions (`emotions.emotion`) séparées par des virgules : **c'est cette colonne que lit le serveur** (affichage et matching). `artwork_emotions` en est la forme normalisée, tenue à jour par `import_collection.py` |
| `origin`                 | TEXT    | NOT NULL. Partenaire fournisseur : Maison des collections (Ville de Mons), Abby, Le Fresnoy, **Huis van Alijn**, **MUMONS** (**V10**) |
| `author_name`            | TEXT    | Excel « Name » — nom(s) brut(s), 99 œuvres              |
| `author`                 | TEXT    | **V9.** Excel « Author » — auteur de l'œuvre, 14 œuvres. Affichage : `COALESCE(author, author_name)` |
| `museum_id`              | TEXT    | Excel : « Museum ID ». N° d'inventaire musée (`MSK_0320`, `MOS_5162`, `JL.2022.0.182`…). NULL pour les 4 œuvres Le Fresnoy (IDs 1–4) |
| `storage_place`          | TEXT    | Lieu de stockage. Jamais NULL (chaîne vide à défaut) : le serveur le lit comme texte obligatoire |
| `popularity`             | INTEGER | NOT NULL, défaut 0. Compteur incrémenté par le backend  |
| `question_id`            | INTEGER | FK → `questions.id` (peut être NULL : l'œuvre n'est alors associée à aucune question ; ce n'est le cas d'aucune œuvre actuellement) |
| `keywords_fr` `keywords_nl` `keywords_en` | TEXT | **V3.** Mots-clés affichables traduits et relus (feuille « Description - Key words ») |
| `title` `title_fr` `title_nl` `title_en` | TEXT | **V4/V9.** Titre de l'œuvre (source + i18n). Les versions i18n viennent de la feuille « Titres » du classeur de relecture |

### `artwork_emotions` — Table de jointure (595 lignes)

Issue de la roue de Plutchik. Forme normalisée de `artworks.emotions`, tenue à jour par `import_collection.py` pour les requêtes SQL (le serveur, lui, lit `artworks.emotions`).

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `artwork_id`| INTEGER | FK → `artworks.id` (ON DELETE CASCADE)         |
| `emotion`   | TEXT    | Émotion en minuscules (joy, sadness, trust…)   |
| PK          |         | `(artwork_id, emotion)`                        |

> **V3** : typos corrigées dans les données (`submision` → `submission`,
> `dissaproval` → `disapproval`).

### `emotions` — Référentiel i18n des émotions (32 lignes) — **V3**

Libellés affichables des émotions Plutchik, dans les trois langues. Jointure :
`artwork_emotions.emotion = emotions.emotion`.

| Colonne   | Type | Notes                                   |
|-----------|------|-----------------------------------------|
| `emotion` | TEXT | PK. Clé en minuscules (= `artwork_emotions.emotion`) |
| `name_fr` | TEXT | NOT NULL. Libellé français              |
| `name_nl` | TEXT | NOT NULL. Libellé néerlandais           |
| `name_en` | TEXT | NOT NULL. Libellé anglais               |

Les libellés viennent de la feuille « Emotions » du classeur de relecture.
`import_collection.py` reconnaît une émotion par sa clé ou par l'un de ses
trois libellés ; une émotion hors référentiel est ignorée avec un
avertissement.

### `transcriptions` — Relation 1:0..1 (85 lignes)

| Colonne              | Type    | Notes                                       |
|----------------------|---------|---------------------------------------------|
| `id`                 | INTEGER | PK                                          |
| `artwork_id`         | INTEGER | FK → `artworks.id`, **UNIQUE** (1:0..1)     |
| `transcription`      | TEXT    | Texte original porté par l'objet — affiché tel quel (artefact, non traduit) |
| `explanation`        | TEXT    | Contexte historique — source (FR)           |
| `explanation_fr/nl/en` | TEXT  | Versions affichées selon la langue de session |
| `translation`        | TEXT    | Traduction moderne du texte de l'objet — source (EN) |
| `translation_fr/nl/en` | TEXT  | Versions affichées selon la langue de session |

### `types_of_object` (27 lignes) et `questions` (12 lignes)

Tables de référence : vocabulaire contrôlé des types d'objets et questions du
parcours visiteur. Les deux sont affichées au visiteur et portent des
colonnes trilingues (`name_fr/nl/en`, `content_fr/nl/en`) à côté de la
colonne source (`name`, `content`). Un type d'objet inconnu rencontré par
`import_collection.py` est créé avec son seul nom source ; ses traductions
suivent la chaîne habituelle (`translate_collection.py`, relecture,
`import_translations.py`).

### `recorded_testimonies` — fusionnée dans `testimonies` (**V8**)

Les 150 témoignages recueillis en interview (sites de Lens, Mons et Kortrijk)
vivent désormais dans **`testimonies`**, avec `visitor_id IS NULL` comme
discriminant, `status='validated'`, `consent_given=1` et leurs **ids
historiques**. Ils portent un `artwork_id` (**V6** : une œuvre unique parmi
celles de leur question), `city` et `created_at` (**V3.1** : un témoignage est
identifié par le couple ville + date, sans prénom ni nom).

Le backend les sert donc par sa route `testimonies` sans traitement
particulier. Dans le classeur de relecture (feuille « Témoignages »), la
colonne H masquée porte l'`id` du témoignage : c'est la clé de ré-import de
`import_translations.py`. Les anciens identifiants « prénom_ville » ont été
remplacés en octobre 2026 ; ils subsistent dans l'historique Git du dépôt.
Le contenu des témoignages peut, lui, contenir un prénom (question 8 : « Savez-vous
pourquoi vos parents ont choisi votre prénom ? »).


### `visitors` — Sessions visiteurs éphémères

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `id`        | TEXT    | PK = UUID de session (généré côté backend)     |
| `created_at`| TEXT    | Début de session                               |
| `ended_at`  | TEXT    | Fin de session (NULL = active)                 |

### `visitor_artwork_views` — Historique de consultation

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `id`        | INTEGER | PK                            |
| `visitor_id`| TEXT    | FK → `visitors.id`                             |
| `artwork_id`| INTEGER | FK → `artworks.id`                             |
| `viewed_at` | TEXT    | Horodatage de la consultation                  |

### `testimonies` — Témoignages des visiteurs

| Colonne          | Type    | Notes                                                       |
|------------------|---------|-------------------------------------------------------------|
| `id`             | INTEGER | PK                                                          |
| `visitor_id`     | TEXT    | FK → `visitors.id` (nullable si anonymisation)              |
| `artwork_id`     | INTEGER | FK → `artworks.id` (1 témoignage = 1 œuvre)                 |
| `content`        | TEXT    | Texte original saisi/dicté par le visiteur                  |
| `source_lang`    | TEXT    | `fr` / `nl` / `en` : langue de l'original (CHECK)           |
| `content_fr`     | TEXT    | Traduction FR — remplie lors de la modération               |
| `content_nl`     | TEXT    | Traduction NL — remplie lors de la modération               |
| `content_en`     | TEXT    | Traduction EN — remplie lors de la modération               |
| `status`         | TEXT    | `pending` / `validated` / `censored`                        |
| `consent_given`  | INTEGER | 0/1 : publication autorisée par le visiteur                 |
| `created_at`     | TEXT    | Horodatage de création                                      |
| `city`        | TEXT    | **V3.1.** Ville du site d'installation du photomaton (renseignée par le backend à l'insertion) — avec `created_at`, identifie le témoignage |
| `moderated_at`   | TEXT    | Horodatage de modération                                    |
| `moderated_by`   | INTEGER | FK → `staff.id`                                             |
| —                |         | **UNIQUE (visitor_id, artwork_id)** : un visiteur ne peut laisser qu'un seul témoignage par œuvre. La contrainte ne s'applique pas si `visitor_id` est NULL (anonymisation après suppression du visiteur).                         

**Cardinalités** : 0..N témoignages par visiteur (un visiteur consulte plusieurs œuvres
mais ne témoigne pas forcément sur toutes), au plus 1 témoignage par couple (visiteur, œuvre).

**Règle métier** : un témoignage n'est visible aux autres visiteurs que si
`status = 'validated'` ET `consent_given = 1` ET ses traductions sont
renseignées (les trois `content_*` sont produits au moment de la modération).

### `artwork_published_testimonies` — Vue de consultation

Vue (lecture seule) qui unifie, pour une œuvre donnée, **tous les témoignages
publiables** : les interviews enregistrées et les témoignages visiteurs,
rattachés à l'œuvre par `artwork_id`, qui passent la règle métier ci-dessus
(`status = 'validated'` et `consent_given = 1`). C'est le point d'entrée recommandé pour le backend
lors de la consultation d'une œuvre :

```sql
SELECT kind, city, created_at, source_lang, content_fr, content_nl, content_en
FROM artwork_published_testimonies
WHERE artwork_id = ?;
```

| Colonne       | Type    | Notes                                                    |
|---------------|---------|----------------------------------------------------------|
| `artwork_id`  | INTEGER | Œuvre consultée                                          |
| `kind`        | TEXT    | `recorded` (interview) / `visitor` (photomaton)          |
| `source_id`   | INTEGER | id dans la table d'origine (selon `kind`)                |
| `city`        | TEXT    | Ville : site de collecte (interviews) ou site d'installation (visiteurs). Avec `created_at`, identifie le témoignage — aucun prénom n'est exposé (V3.1) |
| `created_at`  | TEXT    | Date du témoignage (ISO)                       |
| `source_lang` | TEXT    | Langue de l'enregistrement/saisie d'origine              |
| `content_fr`  | TEXT    | —                                                        |
| `content_nl`  | TEXT    | —                                                        |
| `content_en`  | TEXT    | —                                                        |

Chaque interview est rattachée à une seule œuvre depuis la **V6** : la vue
compte donc 150 lignes d'interviews, plus les témoignages visiteurs validés.

### `summaries` — Résumés générés par LLM (relation 1:1 avec visitors)

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `id`        | INTEGER | PK                                             |
| `visitor_id`| TEXT    | FK → `visitors.id`, **UNIQUE** (1:1)           |
| `content`   | TEXT    | Résumé textuel du parcours                     |
| `created_at`| TEXT    |                                                |

### `staff` — Modérateurs

| Colonne | Type    | Notes                  |
|---------|---------|------------------------|
| `id`    | INTEGER | PK                     |
| `name`  | TEXT    |                        |
| `city`  | TEXT    |                        |
| `role`  | TEXT    |                        |

## Choix techniques

### SQLite + sqlite-vec pour les embeddings

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

> Relancer `compute_embeddings.py` après tout ajout d'œuvres, et quand des
> descriptions **françaises** changent. Une correction NL ou EN seule
> n'affecte pas les vecteurs.

### Algorithme de matching à 4 critères

À partir d'une œuvre de référence, le serveur propose 4 œuvres : une proche en
**type**, une en **description** (vecteur), une en **émotions** (Jaccard sur
`artworks.emotions`), une en **date** (distance entre centres d'intervalles
via `date_year_min` / `date_year_max`).

### Affichage multilingue

Règle générale : afficher `X_fr` / `X_nl` / `X_en` selon la langue de session ;
la colonne sans suffixe est la source (traçabilité, usage interne). Pour les
émotions : clés de `artworks.emotions` traduites via `emotions.name_fr/nl/en`.

> **La langue source varie d'une œuvre à l'autre**, y compris au sein d'un même
> partenaire : le Huis van Alijn a rédigé une partie de ses descriptions en
> néerlandais et une partie en français. Ne jamais déduire la langue d'un texte
> de sa provenance : utiliser la colonne de la langue de session.

### Médias : images et vidéos

`media_url` liste un ou plusieurs fichiers de `assets/`, séparés par `, `.
**Le type se déduit de l'extension** : `.jpg` → image, `.mp4` → vidéo (le front
rend une balise `<video>`, en lecture automatique, sans son ni contrôles).
`thumbnail_url` désigne toujours une image, y compris pour les œuvres
purement vidéo (vignette `*-thumb.jpg` extraite à 1 seconde par
`prepare_media.py`).

Formats retenus avec les musées : **JPEG** pour les photos, **MP4 (H.264)**
pour les vidéos, moins de 100 Mo par fichier (limite de GitHub). Les masters
(TIF, MOV, RAW) restent chez les partenaires.

### Contraintes métier matérialisées en SQL

- `UNIQUE (visitor_id, artwork_id)` sur `testimonies` → un témoignage par œuvre
  et par visiteur.
- `UNIQUE artwork_id` sur `transcriptions` → relation 1:0..1.
- `UNIQUE visitor_id` sur `summaries` → un seul résumé par visiteur.
- `CHECK status IN ('pending', 'validated', 'censored')` et
  `CHECK consent_given IN (0, 1)` sur `testimonies`.

**Règle non matérialisée** (côté backend) : un témoignage n'est visible aux
autres visiteurs que si `status='validated'` **et** `consent_given=1`
(la vue `artwork_published_testimonies` encapsule cette règle).

## Déploiement sur un kiosque

Sur un kiosque, `pp1_collection.db` est modifiée en continu (visiteurs,
témoignages, résumés) : un `git pull` brut écraserait ces données.
`scripts/update.sh` met le code à jour en conservant la base locale, puis
`scripts/apply-remote-db.sh` fusionne les données visiteurs du kiosque dans la
nouvelle base de référence (`scripts/merge_kiosk_data.py`). Procédure
complète : [`docs/update-collection.md`](../docs/update-collection.md).

> **La base d'un kiosque ne doit jamais être poussée sur GitHub** : le dépôt
> est public et elle contient les témoignages des visiteurs.

## Données et qualité

- 230 œuvres, toutes datées, toutes avec médias, titre et description dans
  les trois langues
- 230 vecteurs d'embedding
- 10 œuvres vidéo (6 du Huis van Alijn, 4 du Fresnoy), avec vignette dédiée
- 85 transcriptions dont 71 avec traduction du texte et 35 avec explication
- 150 témoignages enregistrés, 32 libellés d'émotions traduits
- `author` renseigné pour 14 œuvres, `author_name` pour 99 : deux colonnes
  distinctes issues de l'Excel (« Author » et « Name »). Pour l'affichage,
  utiliser `COALESCE(author, author_name)`.

### Points à connaître

- **IDs manquants** : les œuvres 8, 12 et 50 sont absentes (items supprimés
  volontairement après attribution des IDs), ainsi que l'œuvre 15 (retirée en
  **V7** : aucun média). La ligne 15 subsiste dans le classeur de relecture :
  « 1 ids sans correspondance » sur les descriptions et mots-clés est le
  rapport **normal** de `import_translations.py`.
- **Coquilles de dates** : « 1800-1851 » et « 1800-1852 » dans la source sont
  probablement des erreurs pour « 1800-1850 ». Acceptées telles quelles.
- **Anomalies médias** (en attente d'arbitrage musée) : 2 photos
  `mar-bvm-7-2022-0-65-*` (inventaire JL.2022.0.65) et 5 photos
  `mar-bvm-7-2022-0-80-*` sans œuvre en base ; `imadeyou-06-1243.jpg` non
  référencée par l'œuvre 1 ; les œuvres 56 et 64 partagent les mêmes 5 photos
  (fidèle à l'Excel source) ; les anciennes photos des 4 œuvres du Fresnoy ne
  sont plus citées depuis le passage aux extraits vidéo (V11). Vérifiable à tout moment :
  `python check_collection.py --db pp1_collection.db --images ../assets`
- **Date de l'œuvre 233** (« 1500-1600 ») : `date_year_min` valait 1600, la
  migration V10 ne lisant pas les années 15xx. Corrigé à 1500 en octobre 2026.
- **Transcription de l'œuvre 24** : son texte (« Verso : N°1599… ») n'a jamais
  été traduit ; `translate_collection.py` la propose donc à la traduction.

## Historique des migrations

La base versionnée intègre toutes ces migrations. Les scripts correspondants
(`pp1_to_sqlite.py`, `translate_content.py`, `migrate_v3.py` à
`migrate_v11.py`) ont été retirés du dépôt en octobre 2026 ; ils restent dans
l'historique Git. Ils ne permettaient plus de reconstruire la base depuis
zéro : la première étape dépendait d'un fichier de travail non versionné
(`transcriptions_clean.csv`).

| Version | Objet |
| ------- | ----- |
| **V2**  | Construction initiale depuis l'Excel source ; traductions automatiques NLLB-200, remplacées depuis par les versions relues |
| **V3**  | Ré-import des traductions relues, référentiel `emotions`, `keywords_*`, `thumbnail_url`, normalisation `media_url` (devenu `import_translations.py`) |
| **V4**  | Ajout de `artworks.title` / `title_fr/nl/en` |
| **V5**  | Réparation du point d'extension de `media_url` |
| **V6**  | `artwork_id` sur les témoignages enregistrés : chacun est rattaché à **une** œuvre de sa question (répartition équilibrée, option validée par le musée) |
| **V7**  | Retrait de l'œuvre 15 (MSK_1199), sans média ni question |
| **V8**  | Fusion des témoignages enregistrés dans `testimonies` (`visitor_id IS NULL`) ; `recorded_testimonies` supprimée |
| **V9**  | `artworks.author` (Excel musée) et titres i18n via la feuille « Titres » du classeur |
| **V10** | Intégration des collections **Huis van Alijn** (99) et **MUMONS** (15) : médias convertis, vidéos, `origin` renseignée (devenu `import_collection.py`) |
| **V11** | Extraits vidéo des 4 œuvres du Fresnoy (vignettes photo conservées) |
