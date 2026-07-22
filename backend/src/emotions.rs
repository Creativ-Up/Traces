use crate::{common::InternationalizedString, database::{self, Query}};
use anyhow::Result;
use sqlite::Row;

const READ_QUERY: &str = "SELECT emotion, name_en, name_fr, name_nl FROM emotions";

/// An emotion, translated in the 3 supported languages.
#[derive(Clone)]
pub struct Emotion {
    emotion: String,
    name: InternationalizedString,
}

impl Emotion {
    pub fn emotion(&self) -> &str {
        self.emotion.as_str()
    }

    pub fn name(&self) -> &InternationalizedString {
        &self.name
    }
}

/// The set of Plutchik emotions, translated.
pub struct Emotions(Vec<Emotion>);

impl From<Vec<Emotion>> for Emotions {
    fn from(value: Vec<Emotion>) -> Self {
        Emotions(value)
    }
}

impl Emotions {
    /// Returns all the emotions.
    pub fn read_all() -> Result<Self> {
        let query = Query::new(READ_QUERY, &Self::map_row);
        query.execute().map(|r| r.into())
    }

    pub fn iter(&self) -> impl Iterator<Item = &Emotion> + '_ {
        self.0.iter()
    }

    fn map_row(row: Row) -> Emotion {
        Emotion {
            emotion: <String as database::MapRowField<String>>::read(&row, "emotion"),
            name: InternationalizedString::new(
                <String as database::MapRowField<String>>::read(&row, "name_en"),
                <String as database::MapRowField<String>>::read(&row, "name_fr"),
                <String as database::MapRowField<String>>::read(&row, "name_nl"),
            ),
        }
    }
}
