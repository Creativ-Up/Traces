use crate::database::{Query, map_row};
use anyhow::Result;
use serde::Serialize;
use sqlite::Row;

const READ_QUERY: &str = "SELECT id, visitor_id, content, created_at FROM summaries";

/// An end-of-session LLM-generated ticket summary, 1:1 with a visitor.
#[derive(Clone, Serialize)]
pub struct Summary {
    id: i64,
    visitor_id: String,
    content: String,
    created_at: String,
}

map_row!(Summary, id: i64, visitor_id: String, content: String, created_at: String);

impl Summary {
    /// Stores `content` as the summary for `visitor_id`, replacing any existing summary for
    /// that visitor (`summaries.visitor_id` is UNIQUE — one summary per session).
    ///
    /// The matching `visitors` row is created here if it doesn't exist yet, same upsert-guard
    /// as `Testimonies::new_testimony`.
    pub fn store(visitor_id: String, content: String) -> Result<Self> {
        let mut visitor_query = Query::new("INSERT OR IGNORE INTO visitors(id) VALUES (:id)", &|_row| ());
        visitor_query.set_bindings(vec![(":id", visitor_id.clone().into())]);
        visitor_query.execute()?;

        let mut insert_query = Query::new(
            "INSERT INTO summaries(visitor_id, content) VALUES (:visitor_id, :content) \
             ON CONFLICT(visitor_id) DO UPDATE SET content = excluded.content, created_at = datetime('now') \
             RETURNING *",
            &map_row,
        );
        insert_query.set_bindings(vec![
            (":visitor_id", visitor_id.into()),
            (":content", content.into()),
        ]);
        insert_query
            .execute()?
            .into_iter()
            .next()
            .ok_or_else(|| anyhow::anyhow!("insert into summaries returned no row"))
    }
}
