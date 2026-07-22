use crate::{common::InternationalizedString, database::{self, Query}};
use anyhow::Result;
use sqlite::Row;

const READ_QUERY: &str = "SELECT id, name_en, name_fr, name_nl FROM types_of_object";

/// A type of object, translated in the 3 supported languages.
#[derive(Clone)]
pub struct TypeOfObject {
    id: i64,
    name: InternationalizedString,
}

impl TypeOfObject {
    pub fn id(&self) -> i64 {
        self.id
    }

    pub fn name(&self) -> &InternationalizedString {
        &self.name
    }
}

/// The set of object types.
pub struct TypesOfObject(Vec<TypeOfObject>);

impl From<Vec<TypeOfObject>> for TypesOfObject {
    fn from(value: Vec<TypeOfObject>) -> Self {
        TypesOfObject(value)
    }
}

impl TypesOfObject {
    /// Returns all the types of object.
    pub fn read_all() -> Result<Self> {
        let query = Query::new(READ_QUERY, &Self::map_row);
        query.execute().map(|r| r.into())
    }

    pub fn iter(&self) -> impl Iterator<Item = &TypeOfObject> + '_ {
        self.0.iter()
    }

    fn map_row(row: Row) -> TypeOfObject {
        TypeOfObject {
            id: <i64 as database::MapRowField<i64>>::read(&row, "id"),
            name: InternationalizedString::new(
                <Option<String> as database::MapRowField<Option<String>>>::read(&row, "name_en")
                    .unwrap_or_default(),
                <Option<String> as database::MapRowField<Option<String>>>::read(&row, "name_fr")
                    .unwrap_or_default(),
                <Option<String> as database::MapRowField<Option<String>>>::read(&row, "name_nl")
                    .unwrap_or_default(),
            ),
        }
    }
}
