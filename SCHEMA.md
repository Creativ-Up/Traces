# PP1 Collection Database — Schéma

Base SQLite générée à partir de `PP1-Collection_Database.xlsx` et des
témoignages enregistrés traduits FR/NL/EN (fichier de travail
`transcriptions_clean.csv`, non versionné ici — la table `recorded_testimonies`
est livrée peuplée), selon le DDL défini dans `schema.sql`. Aligné sur le
diagramme de classes UML du projet.

**Pipeline de construction** (le visiteur choisit sa langue FR/NL/EN en début
de session ; tout contenu affiché existe donc en trois versions) :

```
1. python pp1_to_sqlite.py        # structure + données sources
2. python translate_content.py    # colonnes *_fr/_nl/_en (NLLB-200, cache local)
3. python compute_embeddings.py   # vecteurs sur description_fr (langue canonique)
4. python migrate_v3.py <db> review_translations.xlsx
                                  # V3 : traductions relues/corrigées, référentiel
                                  # emotions, keywords i18n, thumbnail_url,
                                  # normalisation media_url
5. python check_images.py --db <db> --images <dossier>
                                  # contrôle d'intégrité DB <-> dossier d'images
                                  # (images renommées : voir le Drive partagé du projet)
```

**Internationalisation** : les colonnes `_fr`/`_nl`/`_en` sont d'abord remplies
par `translate_content.py` (NLLB-200), puis écrasées par les versions relues et
corrigées via `migrate_v3.py` (étape 4). Les colonnes sources d'origine sont
conservées pour la traçabilité.

## Vue d'ensemble

```
                         ┌────────────────┐     ┌───────────────────────┐
                         │   questions    │◀────│ recorded_testimonies  │
                         └────────┬───────┘     │  (FR / NL / EN)       │
                                  │ question_id └───────────────────────┘
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

### `artworks` — Entité principale (117 lignes)

| Colonne                  | Type    | Notes                                                   |
|--------------------------|---------|---------------------------------------------------------|
| `id`                     | INTEGER | PK = Database ID du fichier source                      |
| `keywords`               | TEXT    | NOT NULL. Excel : « Description, Key words » (mots-clés bruts, usage interne) |
| `description`            | TEXT    | NOT NULL. Excel : « Explanation » — texte source original (99 FR, 18 EN) |
| `description_fr`         | TEXT    | Affichage FR + **base du vecteur** (langue canonique : évite le biais de langue du corpus mixte) |
| `description_nl`         | TEXT    | Affichage NL                                            |
| `description_en`         | TEXT    | Affichage EN                                            |
| `description_vector`     | BLOB    | Embedding sémantique de `description_fr` (via sqlite-vec) — Calculé via `compute_embeddings.py` |
| `media_url`              | TEXT    | Noms de fichiers image avec extension, séparés par `, `. **Normalisés V3** : minuscules, `[a-z0-9-]` uniquement (`imadeyou-01-053.jpg`). NULL pour l'œuvre 15 (aucune photo) |
| `thumbnail_url`          | TEXT    | **V3.** Vignette de l'œuvre = vue principale (nom le plus court de `media_url`). NULL pour l'œuvre 15 |
| `date_period`            | TEXT    | Forme brute lisible (`"1800-1850"`, `"20th century"`)   |
| `date_year_min`          | INTEGER | Borne basse calculée pour le matching                   |
| `date_year_max`          | INTEGER | Borne haute calculée pour le matching                   |
| `type_of_object_id`      | INTEGER | FK → `types_of_object.id`                               |
| `emotions`               | TEXT    | Émotions Plutchik concaténées (vue dénormalisée, voir `artwork_emotions` pour les requêtes) |
| `origin`                 | TEXT    | NOT NULL. Le Fresnoy / Abby / Maison des collections    |
| `author_name`            | TEXT    | Nom(s) brut(s)                                          |
| `museum_id`              | TEXT    | Excel : « Museum ID ». N° d'inventaire musée (`MSK_0320`, `MOS_5162`, `JL.2022.0.182`…). NULL pour les 4 œuvres Le Fresnoy (IDs 1–4) |
| `storage_place`          | TEXT    | Lieu de stockage                                        |
| `popularity`             | INTEGER | NOT NULL, défaut 0. Compteur incrémenté par le backend  |
| `question_id`            | INTEGER | FK → `questions.id` (peut être NULL : actuellement l'ID 15 ne possède pas de question associée)      |
| `keywords_fr` `keywords_nl` `keywords_en` | TEXT | **V3.** Mots-clés affichables traduits et relus (feuille « Description - Key words ») |

### `artwork_emotions` — Table de jointure (346 lignes)

Issue de la roue de Plutchik. Utilisée pour la **similarité Jaccard** sur les émotions.

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `artwork_id`| INTEGER | FK → `artworks.id` (ON DELETE CASCADE)         |
| `emotion`   | TEXT    | Émotion en minuscules (joy, sadness, trust…)   |
| PK          |         | `(artwork_id, emotion)`                        |

> **V3** : typos corrigées dans les données (`submision` → `submission`,
> `dissaproval` → `disapproval`).

### `emotions` — Référentiel i18n des émotions (25 lignes) — **V3**

Libellés affichables des émotions Plutchik, dans les trois langues. Jointure :
`artwork_emotions.emotion = emotions.emotion`.

| Colonne   | Type | Notes                                   |
|-----------|------|-----------------------------------------|
| `emotion` | TEXT | PK. Clé en minuscules (= `artwork_emotions.emotion`) |
| `name_fr` | TEXT | NOT NULL. Libellé français              |
| `name_nl` | TEXT | NOT NULL. Libellé néerlandais           |
| `name_en` | TEXT | NOT NULL. Libellé anglais               |

14 entrées proviennent de la relecture (`review_translations.xlsx`, feuille
Emotions) ; 11 complètent les émotions utilisées en base mais absentes de la
feuille (traductions Plutchik standard, **à faire valider**).

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

### `types_of_object` (28 lignes) et `questions` (12 lignes)

Tables de référence (vocabulaire contrôlé et questions du parcours visiteur).
Les deux portent des colonnes trilingues pour l'affichage selon la langue de
session : `name_fr/nl/en` et `content_fr/nl/en` (remplies par
`translate_content.py` ; pour les questions, remplacer les versions FR/NL
générées par les formulations officielles utilisées lors des interviews).
Les deux sont affichées au visiteur et portent donc des colonnes trilingues :
`name_fr/nl/en` pour les types, `content_fr/nl/en` pour les questions (la
colonne source `name`/`content` est conservée). ⚠ Pour `questions`, remplacer
les traductions machine par les **formulations officielles** FR/NL utilisées
lors des interviews.

### `recorded_testimonies` — Témoignages enregistrés traduits (155 lignes)

Témoignages recueillis en interview (32 personnes, sites de Lens, Mons et
Kortrijk), rattachés aux **questions** du parcours (pas aux œuvres) et
disponibles en trois langues. La langue source est celle de l'enregistrement
(`fr` ou `nl`) ; les deux autres versions sont des traductions automatiques
(pipeline faster-whisper + NLLB-200). À ne pas confondre avec `testimonies`
(témoignages saisis par les visiteurs sur le photomaton, avec modération).

| Colonne       | Type    | Notes                                                   |
|---------------|---------|---------------------------------------------------------|
| `id`          | INTEGER | PK                                                      |
| `question_id` | INTEGER | FK → `questions.id`                                     |
| `city`        | TEXT    | `Lens` / `Mons` / `Kortrijk`                            |
| `source_lang` | TEXT    | `fr` ou `nl` (CHECK). « Question N » = fr, « Vraag N » = nl |
| `content_fr`  | TEXT    | NOT NULL                                                |
| `content_nl`  | TEXT    | NOT NULL                                                |
| `content_en`  | TEXT    | NOT NULL                                                |
| `created_at`  | TEXT    | **V3.1.** Date d'enregistrement du témoignage (ISO `YYYY-MM-DD`), issue de la campagne de collecte (oct. 2025 Mons/Lens, fév. 2026 Kortrijk) |

> **V3.1** : les colonnes `speaker` et `source_file` ont été supprimées, et
> côté visiteurs `visitors.surname` a également disparu (le visiteur ne donne
> plus son prénom) ; `testimonies.city` a été ajoutée. Tout témoignage est
> identifié par le couple **(ville, date)**.
> (anonymisation). La correspondance ligne ↔ fichier audio d'origine est
> conservée hors base, dans `migrate_v3.py` (`RECORDED_IDS`), qui sert de clé
> de ré-import des traductions depuis `review_translations.xlsx`.

**Cardinalités** : 0..N témoignages par question (de 12 à 15 selon la question) ;
une personne peut témoigner sur plusieurs questions.

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
publiables** : les témoignages enregistrés (rattachés via la question de
l'œuvre, publiables par définition) et les témoignages visiteurs qui passent
la règle métier ci-dessus. C'est le point d'entrée recommandé pour le backend
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
| `city`        | TEXT    | Ville : site de collecte (interviews) ou site d'installation (visiteurs). Avec `created_at`, identifie le témoignage — plus aucun prénom n'est exposé (V3.1) |
| `created_at`  | TEXT    | Date du témoignage (ISO)                       |
| `source_lang` | TEXT    | Langue de l'enregistrement/saisie d'origine              |
| `content_fr`  | TEXT    | —                                                        |
| `content_nl`  | TEXT    | —                                                        |
| `content_en`  | TEXT    | —                                                        |

Un témoignage enregistré apparaît pour **chacune des œuvres** de sa question
(la vue matérialise la relation question → œuvres à la lecture, sans dupliquer
le stockage) : ~1 480 lignes virtuelles pour 155 + N témoignages stockés.

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