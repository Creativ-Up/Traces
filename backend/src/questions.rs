use crate::{
    common::InternationalizedString,
    database::{self, Query},
};
use anyhow::Result;
use serde::Serialize;
use sqlite::Row;

/// A question.
#[derive(Clone, Serialize)]
pub struct Question {
    id: i64,
    content: InternationalizedString,
}

/// A set of questions.
#[derive(Clone, Serialize)]
pub struct Questions(Vec<Question>);

impl From<Vec<Question>> for Questions {
    fn from(value: Vec<Question>) -> Self {
        Questions(value)
    }
}

/// A structure used to globally handle questions in Rocket.
pub struct QuestionsState {
    questions: Questions,
}

impl Default for QuestionsState {
    fn default() -> Self {
        Self {
            questions: Questions::read_all().unwrap(),
        }
    }
}

impl QuestionsState {
    /// Returns the underlying set of questions.
    pub fn questions(&self) -> &Questions {
        &self.questions
    }
}

impl Questions {
    /// Returns all the question.
    pub fn read_all() -> Result<Self> {
        let query = Query::new(
            "SELECT id, content_en, content_fr, content_nl FROM questions ORDER BY id",
            &Self::map_row,
        );
        query.execute().map(|r| r.into())
    }

    fn map_row(row: Row) -> Question {
        Question {
            id: <i64 as database::MapRowField<i64>>::read(&row, "id"),
            content: InternationalizedString::new(
                <Option<String> as database::MapRowField<Option<String>>>::read(&row, "content_en")
                    .unwrap_or_default(),
                <Option<String> as database::MapRowField<Option<String>>>::read(&row, "content_fr")
                    .unwrap_or_default(),
                <Option<String> as database::MapRowField<Option<String>>>::read(&row, "content_nl")
                    .unwrap_or_default(),
            ),
        }
    }
}
