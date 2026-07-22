use anyhow::{Context, Result};
use sqlite::{Row, Value};

/// The default database location.
const DEFAULT_DB_LOCATION: &str = "pp1_collection.db";

/// Returns the effective database location.
fn db_location() -> String {
    DEFAULT_DB_LOCATION.to_string()
}

/// An helper object for database queries.
/// It is designed to handle queries that return results.
/// In the case of insertion queries, they can be adapted so that the return some data using e.g. `RETURNING` clauses.
/// Insertion queries without such clauses should return empty lists but still require a `row_mapping` function (see the [new](Self::new) function).
///
/// For simple queries (i.e. queries which do not rely on parameters), calling `new` and [execute](Self::execute) should be sufficient.
///
/// For queries relying on parameters, [set_bindings](Self::set_bindings) must be called before `execute`.
/// Note that the only allowed placeholders are the named ones.
pub struct Query<'a, R> {
    query: String,
    row_mapping: &'a dyn Fn(Row) -> R,
    bindings: Option<Vec<(&'static str, Value)>>,
}

impl<'a, R> Query<'a, R> {
    /// Creates a new query.
    ///
    /// The query can contain named placeholders (e.g. ":placeholder").
    /// In this case, they must set by a call to [set_bindings](Self::set_bindings).
    ///
    /// The parameter `raw_mapping` is a function that associates an object with an SQLite [Row](sqlite::Row).
    pub fn new<T>(query: T, row_mapping: &'a dyn Fn(Row) -> R) -> Self
    where
        T: ToString,
    {
        Self {
            query: query.to_string(),
            row_mapping,
            bindings: None,
        }
    }

    /// In case the query contains placeholders, this method is used to set them.
    ///
    /// Bindings are provided by couples of placeholder names (as strings) and SQLite [Value](sqlite::Value)s.
    pub fn set_bindings(&mut self, bindings: Vec<(&'static str, Value)>) {
        self.bindings = Some(bindings);
    }

    /// Executes the query, returning a set of values computed  thanks to the `query` and `row_mapping` parameters passed to the [new](Self::new) function.
    pub fn execute(self) -> Result<Vec<R>> {
        let connection = sqlite::open(db_location()).unwrap();
        let mut statement = connection.prepare(&self.query).unwrap();
        if let Some(b) = self.bindings {
            statement.bind_iter(b).context("while binding values")?;
        }
        statement
            .into_iter()
            .map(|s| s.map(self.row_mapping).context("while iterating over rows"))
            .collect()
    }
}

pub(crate) trait MapRowField<T> {
    fn read(row: &Row, id: &str) -> T;
}

impl MapRowField<i64> for i64 {
    fn read(row: &Row, key: &str) -> i64 {
        row.read::<i64, _>(key)
    }
}

impl MapRowField<Option<i64>> for Option<i64> {
    fn read(row: &Row, key: &str) -> Option<i64> {
        row.read::<Option<i64>, _>(key)
    }
}

impl MapRowField<String> for String {
    fn read(row: &Row, key: &str) -> String {
        row.read::<&str, _>(key).to_string()
    }
}

impl MapRowField<Option<String>> for Option<String> {
    fn read(row: &Row, key: &str) -> Option<String> {
        row.read::<Option<&str>, _>(key).map(|s| s.to_string())
    }
}

impl MapRowField<bool> for bool {
    fn read(row: &Row, key: &str) -> bool {
        row.read::<i64, _>(key) != 0
    }
}

impl MapRowField<Vec<u8>> for Vec<u8> {
    fn read(row: &Row, key: &str) -> Vec<u8> {
        row.read::<&[u8], _>(key).to_vec()
    }
}

macro_rules! map_row {
    ($objty:ident) => {
        fn map_row(row: Row) -> $objty {
            $objty {}
        }
    };
    ($objty:ident, $($id:ident: $ty:ty),+ $(,)?) => {
        fn map_row(row: Row) -> $objty {
            $objty {
                $(
                    $id: <$ty as crate::database::MapRowField<$ty>>::read(&row, stringify!($id)),
                )+
            }
        }
    };
}

pub(crate) use map_row;
