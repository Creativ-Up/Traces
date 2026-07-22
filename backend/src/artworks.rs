use crate::{
    common::InternationalizedString,
    database::{self, Query},
    emotions::Emotions,
    types_of_object::TypesOfObject,
};
use anyhow::Result;
use serde::Serialize;
use sqlite::Row;

const READ_QUERY: &str = "SELECT id, keywords, keywords_en, keywords_fr, keywords_nl, description, description_en, description_fr, description_nl, description_vector, media_url, thumbnail_url, date_period, date_year_min, date_year_max, type_of_object_id, emotions, origin, author_name, museum_id, storage_place, popularity, question_id, title_en, title_fr, title_nl FROM artworks";

/// An artwork.
#[derive(Clone, Serialize)]
pub struct Artwork {
    id: i64,
    keywords: String,
    keywords_en: Option<String>,
    keywords_fr: Option<String>,
    keywords_nl: Option<String>,
    description: String,
    description_en: Option<String>,
    description_fr: Option<String>,
    description_nl: Option<String>,
    description_vector: Vec<u8>,
    media_url: Option<String>,
    thumbnail_url: Option<String>,
    date_period: Option<String>,
    date_year_min: Option<i64>,
    date_year_max: Option<i64>,
    type_of_object_id: i64,
    emotions: String,
    origin: String,
    author_name: Option<String>,
    museum_id: Option<String>,
    storage_place: String,
    popularity: i64,
    question_id: Option<i64>,
    title_en: Option<String>,
    title_fr: Option<String>,
    title_nl: Option<String>,
}

#[derive(Clone, Serialize)]
pub struct ResultArtwork {
    id: i64,
    keywords: InternationalizedString,
    description: InternationalizedString,
    // Not every artwork has a title (unlike description, which is always present),
    // so this is None when title_en/fr/nl are all empty in the DB.
    title: Option<InternationalizedString>,
    media_url: Option<String>,
    thumbnail_url: Option<String>,
    date_period: Option<String>,
    emotions: Vec<InternationalizedString>,
    type_of_object: Option<InternationalizedString>,
    origin: String,
    criterion: String,
}

impl ResultArtwork {
    pub fn id(&self) -> i64 {
        self.id
    }

    /// Builds a `ResultArtwork`, translating `emotions`/`type_of_object` via the
    /// referential tables passed in (see `emotions::Emotions`, `types_of_object::TypesOfObject`).
    pub fn from_artwork(
        artwork: Artwork,
        criterion: String,
        emotions: &Emotions,
        types_of_object: &TypesOfObject,
    ) -> Self {
        let title = if artwork.title_en.is_none() && artwork.title_fr.is_none() && artwork.title_nl.is_none() {
            None
        } else {
            Some(InternationalizedString::new(
                artwork.title_en.unwrap_or_default(),
                artwork.title_fr.unwrap_or_default(),
                artwork.title_nl.unwrap_or_default(),
            ))
        };
        let artwork_emotions = emotions_str_to_vec(&artwork.emotions);
        let emotions = emotions
            .iter()
            .filter(|e| artwork_emotions.contains(&e.emotion().to_string()))
            .map(|e| e.name().clone())
            .collect();
        let type_of_object = types_of_object
            .iter()
            .find(|t| t.id() == artwork.type_of_object_id)
            .map(|t| t.name().clone());
        Self {
            id: artwork.id,
            keywords: InternationalizedString::new(
                artwork.keywords_en.unwrap_or_default(),
                artwork.keywords_fr.unwrap_or_default(),
                artwork.keywords_nl.unwrap_or_default(),
            ),
            description: InternationalizedString::new(
                artwork.description_en.unwrap_or_default(),
                artwork.description_fr.unwrap_or_default(),
                artwork.description_nl.unwrap_or_default(),
            ),
            title,
            media_url: artwork.media_url,
            thumbnail_url: artwork.thumbnail_url,
            date_period: artwork.date_period,
            emotions,
            type_of_object,
            origin: artwork.origin,
            criterion,
        }
    }
}

/// Splits a comma-separated `artworks.emotions` string into trimmed, lowercased keys
/// matching `emotions.emotion` (mirrors `scoring::emotions_str_to_vec`).
fn emotions_str_to_vec(emotions: &str) -> Vec<String> {
    emotions
        .split(',')
        .map(|s| s.trim().to_lowercase())
        .collect()
}

/// A set of artworks.
#[derive(Clone, Serialize)]
pub struct Artworks(Vec<Artwork>);

impl From<Vec<Artwork>> for Artworks {
    fn from(value: Vec<Artwork>) -> Self {
        Artworks(value)
    }
}

impl Artworks {
    /// Returns all the artworks.
    pub fn read_all() -> Result<Self> {
        let query = Query::new(format!("{READ_QUERY} ORDER BY id"), &Self::map_row);
        query.execute().map(|r| r.into())
    }

    /// Returns the artworks related to the question which id is passed.
    pub fn read_matching_question_id(question_id: i64) -> Result<Vec<ResultArtwork>> {
        let mut query = Query::new(
            format!("{READ_QUERY} WHERE question_id = :question_id ORDER BY id"),
            &Self::map_row,
        );
        query.set_bindings(vec![(":question_id", question_id.into())]);
        let artworks: Vec<Artwork> = query.execute()?;
        let emotions = Emotions::read_all()?;
        let types_of_object = TypesOfObject::read_all()?;
        Ok(artworks
            .into_iter()
            .map(|a| ResultArtwork::from_artwork(a, "random".to_string(), &emotions, &types_of_object))
            .collect())
    }

    pub fn iter(&self) -> impl Iterator<Item = &Artwork> + '_ {
        self.0.iter()
    }

    database::map_row!(
        Artwork,
        id: i64,
        keywords: String,
        keywords_en: Option<String>,
        keywords_fr: Option<String>,
        keywords_nl: Option<String>,
        description: String,
        description_en: Option<String>,
        description_fr: Option<String>,
        description_nl: Option<String>,
        description_vector: Vec<u8>,
        media_url: Option<String>,
        thumbnail_url: Option<String>,
        date_period: Option<String>,
        date_year_min: Option<i64>,
        date_year_max: Option<i64>,
        type_of_object_id: i64,
        emotions: String,
        origin: String,
        author_name: Option<String>,
        museum_id: Option<String>,
        storage_place: String,
        popularity: i64,
        question_id: Option<i64>,
        title_en: Option<String>,
        title_fr: Option<String>,
        title_nl: Option<String>,
    );
}

impl FromIterator<Artwork> for Artworks {
    fn from_iter<T: IntoIterator<Item = Artwork>>(iter: T) -> Self {
        Artworks(iter.into_iter().collect())
    }
}

impl Artwork {
    pub fn id(&self) -> i64 {
        self.id
    }

    pub fn date_year_min(&self) -> Option<i64> {
        self.date_year_min
    }

    pub fn date_year_max(&self) -> Option<i64> {
        self.date_year_max
    }

    pub fn description_vector(&self) -> &[u8] {
        self.description_vector.as_slice()
    }

    pub fn type_of_object_id(&self) -> i64 {
        self.type_of_object_id
    }

    pub fn emotions(&self) -> &str {
        self.emotions.as_str()
    }
}
