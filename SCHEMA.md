# PP1 Collection Database — Schéma

Base SQLite générée par `pp1_to_sqlite.py` à partir de `PP1-Collection_Database.xlsx`,
selon le DDL défini dans `schema.sql`. Aligné sur le diagramme de classes UML du projet.

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

### `artworks` — Entité principale (117 lignes)

| Colonne                  | Type    | Notes                                                   |
|--------------------------|---------|---------------------------------------------------------|
| `id`                     | INTEGER | PK = Database ID du fichier source                      |
| `keywords`               | TEXT    | NOT NULL. Excel : « Description, Key words » (mots-clés bruts, virgules) |
| `description`            | TEXT    | NOT NULL. Excel : « Explanation » (texte présenté au visiteur, **base du vecteur**) |
| `description_vector`     | BLOB    | Embedding sémantique de `description` (via sqlite-vec) — Calculé via `compute_embeddings.py` |
| `media_url`              | TEXT    | URL/références photo (potentiellement multiples)        |
| `date_period`            | TEXT    | Forme brute lisible (`"1800-1850"`, `"20th century"`)   |
| `date_year_min`          | INTEGER | Borne basse calculée pour le matching                   |
| `date_year_max`          | INTEGER | Borne haute calculée pour le matching                   |
| `type_of_object_id`      | INTEGER | FK → `types_of_object.id`                               |
| `emotions`               | TEXT    | Émotions Plutchik concaténées (vue dénormalisée, voir `artwork_emotions` pour les requêtes) |
| `origin`                 | TEXT    | NOT NULL. Le Fresnoy / Abby / Maison des collections    |
| `author_name`            | TEXT    | Nom(s) brut(s)                                          |
| `birthday`               | TEXT    | Date associée à l'auteur si connue                      |
| `places`                 | TEXT    | Lieux liés (texte brut)                                 |
| `storage_place`          | TEXT    | Lieu de stockage                                        |
| `popularity`             | INTEGER | NOT NULL, défaut 0. Compteur incrémenté par le backend  |
| `question_id`            | INTEGER | FK → `questions.id` (peut être NULL : actuellement l'ID 15 ne possède pas de question associée)      |

### `artwork_emotions` — Table de jointure (346 lignes)

Issue de la roue de Plutchik. Utilisée pour la **similarité Jaccard** sur les émotions.

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `artwork_id`| INTEGER | FK → `artworks.id` (ON DELETE CASCADE)         |
| `emotion`   | TEXT    | Émotion en minuscules (joy, sadness, trust…)   |
| PK          |         | `(artwork_id, emotion)`                        |

### `transcriptions` — Relation 1:0..1 (85 lignes)

| Colonne          | Type    | Notes                                       |
|------------------|---------|---------------------------------------------|
| `id`             | INTEGER | PK                         |
| `artwork_id`     | INTEGER | FK → `artworks.id`, **UNIQUE** (1:0..1)     |
| `transcription`  | TEXT    | Texte transcrit                             |
| `explanation`    | TEXT    | Contexte historique                         |
| `translation`    | TEXT    | Traduction si applicable                    |

### `types_of_object` (28 lignes) et `questions` (12 lignes)

Tables de référence (vocabulaire contrôlé et questions du parcours visiteur).

### `visitors` — Sessions visiteurs éphémères

| Colonne     | Type    | Notes                                          |
|-------------|---------|------------------------------------------------|
| `id`        | TEXT    | PK = UUID de session (généré côté backend)     |
| `surname`   | TEXT    | Prénom/pseudo donné par le visiteur            |
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
| `content`        | TEXT    | Contenu                                                     |
| `status`         | TEXT    | `pending` / `validated` / `censored`                        |
| `consent_given`  | INTEGER | 0/1 : publication autorisée par le visiteur                 |
| `created_at`     | TEXT    | Horodatage de création                                      |
| `moderated_at`   | TEXT    | Horodatage de modération                                    |
| `moderated_by`   | INTEGER | FK → `staff.id`                                             |
| —                |         | **UNIQUE (visitor_id, artwork_id)** : un visiteur ne peut laisser qu'un seul témoignage par œuvre. La contrainte ne s'applique pas si `visitor_id` est NULL (anonymisation après suppression du visiteur).                         

**Cardinalités** : 0..N témoignages par visiteur (un visiteur consulte plusieurs œuvres
mais ne témoigne pas forcément sur toutes), au plus 1 témoignage par couple (visiteur, œuvre).

**Règle métier** : un témoignage n'est visible aux autres visiteurs que si
`status = 'validated'` ET `consent_given = 1`.

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