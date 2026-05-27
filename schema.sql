-- =================================================================
-- PP1 Collection Database — Schéma
-- Cible : SQLite (avec extension sqlite-vec pour description_vector)
-- =================================================================

PRAGMA foreign_keys = ON;

-- =================================================================
-- TABLES DE RÉFÉRENCE
-- =================================================================

CREATE TABLE types_of_object (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE questions (
    id      INTEGER PRIMARY KEY,
    content TEXT NOT NULL
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
    keywords                TEXT NOT NULL,         -- Excel : "Description, Key words"
    description             TEXT NOT NULL,         -- Excel : "Explanation" (base du vecteur)
    description_vector      BLOB,                  -- embedding via sqlite-vec
    media_url               TEXT,                  -- URL/ref image principale
    date_period             TEXT,                  -- forme brute lisible
    date_year_min           INTEGER,               -- borne basse pour le matching
    date_year_max           INTEGER,               -- borne haute pour le matching
    type_of_object_id       INTEGER NOT NULL,
    emotions                TEXT,                  -- émotions Plutchik concaténées (cf. artwork_emotions pour les requêtes)
    origin                  TEXT NOT NULL,         -- Le Fresnoy / Abby / Maison des collections
    author_name             TEXT,
    birthday                TEXT,
    places                  TEXT,
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
    transcription   TEXT,
    explanation     TEXT,
    translation     TEXT,
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
    content         TEXT NOT NULL,
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

CREATE TABLE summaries (
    id          INTEGER PRIMARY KEY,
    visitor_id  TEXT NOT NULL UNIQUE,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE CASCADE
);


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
