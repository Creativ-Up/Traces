-- =================================================================
-- PP1 Collection Database — Schéma
-- Cible : SQLite (avec extension sqlite-vec pour description_vector)
-- =================================================================

PRAGMA foreign_keys = ON;

-- =================================================================
-- TABLES DE RÉFÉRENCE
-- =================================================================

CREATE TABLE types_of_object (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,                 -- libellé source (mélange FR/EN historique)
    name_fr  TEXT,
    name_nl  TEXT,
    name_en  TEXT
);

CREATE TABLE questions (
    id          INTEGER PRIMARY KEY,
    content     TEXT NOT NULL,                     -- version source (anglais)
    content_fr  TEXT,                              -- versions affichées selon la langue de session
    content_nl  TEXT,                              -- NB : privilégier les formulations officielles
    content_en  TEXT                               --      utilisées lors des interviews
);

CREATE TABLE staff (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    city    TEXT,
    role    TEXT NOT NULL
);


-- =================================================================
-- ENTITÉ PRINCIPALE : ARTWORKS
-- =================================================================

CREATE TABLE artworks (
    id                      INTEGER PRIMARY KEY,
    keywords                TEXT NOT NULL,         -- Excel : "Description, Key words" (usage interne, matching)
    description             TEXT NOT NULL,         -- Excel : "Explanation" — texte source original (FR ou EN)
    description_fr          TEXT,                  -- affichage FR + BASE DU VECTEUR (langue canonique)
    description_nl          TEXT,                  -- affichage NL
    description_en          TEXT,                  -- affichage EN
    description_vector      BLOB,                  -- embedding de description_fr via sqlite-vec
    media_url               TEXT,                  -- URL/ref image principale
    date_period             TEXT,                  -- forme brute lisible
    date_year_min           INTEGER,               -- borne basse pour le matching
    date_year_max           INTEGER,               -- borne haute pour le matching
    type_of_object_id       INTEGER NOT NULL,
    emotions                TEXT,                  -- émotions Plutchik concaténées (cf. artwork_emotions pour les requêtes)
    origin                  TEXT NOT NULL,         -- Le Fresnoy / Abby / Maison des collections
    author_name             TEXT,
    museum_id               TEXT,                  -- n° d'inventaire musée (ex : MSK_0320) ; NULL pour Le Fresnoy
    storage_place           TEXT,
    popularity              INTEGER NOT NULL DEFAULT 0,
    question_id             INTEGER,
    FOREIGN KEY (type_of_object_id) REFERENCES types_of_object(id),
    FOREIGN KEY (question_id) REFERENCES questions(id),
    CHECK (date_year_max IS NULL OR date_year_min IS NULL OR date_year_max >= date_year_min)
);

-- Table de jointure pour les émotions (matching par Jaccard)
CREATE TABLE artwork_emotions (
    artwork_id  INTEGER NOT NULL,
    emotion     TEXT NOT NULL,
    PRIMARY KEY (artwork_id, emotion),
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE
);

-- Transcription : 1 artwork -> 0..1 transcription
CREATE TABLE transcriptions (
    id              INTEGER PRIMARY KEY,
    artwork_id      INTEGER NOT NULL UNIQUE,
    transcription   TEXT,                          -- texte original porté par l'objet : affiché tel quel (artefact)
    explanation     TEXT,                          -- contexte historique — source (FR)
    explanation_fr  TEXT,
    explanation_nl  TEXT,
    explanation_en  TEXT,
    translation     TEXT,                          -- traduction du texte de l'objet — source (EN)
    translation_fr  TEXT,
    translation_nl  TEXT,
    translation_en  TEXT,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE
);


-- =================================================================
-- ENTITÉS DYNAMIQUES
-- =================================================================

CREATE TABLE visitors (
    id          TEXT PRIMARY KEY,                          -- UUID de session
    surname     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT
);

CREATE TABLE visitor_artwork_views (
    id          INTEGER PRIMARY KEY,
    visitor_id  TEXT NOT NULL,
    artwork_id  INTEGER NOT NULL,
    viewed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE CASCADE,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE
);

CREATE TABLE testimonies (
    id              INTEGER PRIMARY KEY,
    visitor_id      TEXT,
    artwork_id      INTEGER NOT NULL,
    content         TEXT NOT NULL,                 -- texte original saisi/dicté par le visiteur
    source_lang     TEXT
                    CHECK (source_lang IN ('fr', 'nl', 'en')),
    content_fr      TEXT,                          -- traductions remplies lors de la modération
    content_nl      TEXT,
    content_en      TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'validated', 'censored')),
    consent_given   INTEGER NOT NULL DEFAULT 0
                    CHECK (consent_given IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    moderated_at    TEXT,
    moderated_by    INTEGER,
    FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE SET NULL,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE,
    FOREIGN KEY (moderated_by) REFERENCES staff(id) ON DELETE SET NULL,
    -- Un visiteur ne peut laisser qu'un seul témoignage par œuvre.
    UNIQUE (visitor_id, artwork_id)
);

-- Témoignages enregistrés en interview, rattachés aux questions (pas aux œuvres),
-- disponibles en trois langues. À distinguer de `testimonies` (témoignages
-- visiteurs saisis sur le photomaton, avec cycle de modération).
CREATE TABLE recorded_testimonies (
    id          INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL,
    speaker     TEXT NOT NULL,                     -- prénom extrait de fichier_source
    city        TEXT,                              -- Lens / Mons / Kortrijk
    source_file TEXT NOT NULL,                     -- nom du fichier audio source (traçabilité)
    source_lang TEXT NOT NULL
                CHECK (source_lang IN ('fr', 'nl')),
    content_fr  TEXT NOT NULL,
    content_nl  TEXT NOT NULL,
    content_en  TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id),
    UNIQUE (question_id, source_file)
);

CREATE TABLE summaries (
    id          INTEGER PRIMARY KEY,
    visitor_id  TEXT NOT NULL UNIQUE,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE CASCADE
);


-- =================================================================
-- VUES
-- =================================================================

-- Tous les témoignages publiables pour une œuvre donnée :
--   - témoignages enregistrés (interviews), rattachés via la question de l'œuvre,
--     publiables par définition ;
--   - témoignages visiteurs validés + consentis + traduits.
-- Usage backend : SELECT ... FROM artwork_published_testimonies WHERE artwork_id = ?
CREATE VIEW artwork_published_testimonies AS
SELECT
    a.id            AS artwork_id,
    'recorded'      AS kind,
    rt.id           AS source_id,     -- id dans recorded_testimonies
    rt.speaker      AS speaker,
    rt.source_lang  AS source_lang,
    rt.content_fr   AS content_fr,
    rt.content_nl   AS content_nl,
    rt.content_en   AS content_en
FROM recorded_testimonies rt
JOIN artworks a ON a.question_id = rt.question_id
UNION ALL
SELECT
    t.artwork_id    AS artwork_id,
    'visitor'       AS kind,
    t.id            AS source_id,     -- id dans testimonies
    v.surname       AS speaker,       -- prénom laissé par le visiteur (facultatif -> NULL)
    t.source_lang   AS source_lang,
    t.content_fr    AS content_fr,
    t.content_nl    AS content_nl,
    t.content_en    AS content_en
FROM testimonies t
LEFT JOIN visitors v ON v.id = t.visitor_id
WHERE t.status = 'validated'
  AND t.consent_given = 1
  AND t.content_fr IS NOT NULL;       -- traductions produites à la modération


-- =================================================================
-- INDEX
-- =================================================================

CREATE INDEX idx_artworks_type       ON artworks(type_of_object_id);
CREATE INDEX idx_artworks_question   ON artworks(question_id);
CREATE INDEX idx_artworks_origin     ON artworks(origin);
CREATE INDEX idx_artworks_dates      ON artworks(date_year_min, date_year_max);
CREATE INDEX idx_emotions_emotion    ON artwork_emotions(emotion);
CREATE INDEX idx_transcr_artwork     ON transcriptions(artwork_id);
CREATE INDEX idx_views_visitor       ON visitor_artwork_views(visitor_id);
CREATE INDEX idx_views_artwork       ON visitor_artwork_views(artwork_id);
CREATE INDEX idx_testimonies_artwork ON testimonies(artwork_id);
CREATE INDEX idx_testimonies_status  ON testimonies(status);
CREATE INDEX idx_testimonies_visitor ON testimonies(visitor_id);
CREATE INDEX idx_rec_testimonies_question ON recorded_testimonies(question_id);
CREATE INDEX idx_rec_testimonies_city     ON recorded_testimonies(city);
