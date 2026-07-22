use crate::{database::{self, Query}, staff};
use anyhow::{Result, bail};
use serde::Serialize;
use sqlite::{Row, Value};

const READ_QUERY: &str = "SELECT id, visitor_id, artwork_id, content, source_lang, content_fr, content_nl, content_en, city, status, consent_given, created_at, moderated_at, moderated_by FROM testimonies";

/// A testimony.
#[derive(Clone, Serialize)]
pub struct Testimony {
    id: i64,
    visitor_id: Option<String>,
    artwork_id: i64,
    /// Per-language content. Only `lang` (the original recording's language) is guaranteed
    /// to be filled in before moderation; the others are empty strings until translated.
    content: InternationalizedTestimony,
    // Original recording language: 'fr', 'nl', or 'en'. Null until moderation sets it.
    lang: Option<String>,
    // Recording machine's location id (e.g. 'le_fresnoy'), stamped by the client at
    // submission time. Column name is `city` but the value is a fixed location id, not
    // a free city name.
    city: Option<String>,
    // 'pending', 'validated', or 'censored'
    status: String,
    consent_given: bool,
    created_at: String,
    moderated_at: Option<String>,
    moderated_by: Option<i64>,
}

#[derive(Clone, Serialize)]
pub struct InternationalizedTestimony {
    en: String,
    fr: String,
    nl: String,
}

/// The raw row shape, before `content`/`source_lang`/`content_{en,fr,nl}` are merged into
/// `Testimony::content` + `Testimony::lang` (see `Testimonies::map_row`).
#[derive(Clone)]
struct RawTestimony {
    id: i64,
    visitor_id: Option<String>,
    artwork_id: i64,
    content: String,
    source_lang: Option<String>,
    content_fr: Option<String>,
    content_nl: Option<String>,
    content_en: Option<String>,
    city: Option<String>,
    status: String,
    consent_given: bool,
    created_at: String,
    moderated_at: Option<String>,
    moderated_by: Option<i64>,
}

impl From<RawTestimony> for Testimony {
    fn from(raw: RawTestimony) -> Self {
        // The original recording's text belongs in its own language slot; the other slots
        // stay empty until moderation fills in content_{en,fr,nl}.
        let mut content = InternationalizedTestimony {
            en: raw.content_en.unwrap_or_default(),
            fr: raw.content_fr.unwrap_or_default(),
            nl: raw.content_nl.unwrap_or_default(),
        };
        match raw.source_lang.as_deref() {
            Some("en") if content.en.is_empty() => content.en = raw.content.clone(),
            Some("fr") if content.fr.is_empty() => content.fr = raw.content.clone(),
            Some("nl") if content.nl.is_empty() => content.nl = raw.content.clone(),
            _ => {}
        }
        Self {
            id: raw.id,
            visitor_id: raw.visitor_id,
            artwork_id: raw.artwork_id,
            content,
            lang: raw.source_lang,
            city: raw.city,
            status: raw.status,
            consent_given: raw.consent_given,
            created_at: raw.created_at,
            moderated_at: raw.moderated_at,
            moderated_by: raw.moderated_by,
        }
    }
}

/// A set of testimonies.
#[derive(Clone, Serialize)]
pub struct Testimonies(Vec<Testimony>);

impl From<Vec<Testimony>> for Testimonies {
    fn from(value: Vec<Testimony>) -> Self {
        Testimonies(value)
    }
}

impl Testimonies {
    /// Returns all the testimonies.
    pub fn read_all() -> Result<Self> {
        let query = Query::new(format!("{READ_QUERY} ORDER BY id"), &Self::map_row);
        query.execute().map(|r| r.into())
    }

    /// Returns the testimonies related to the artwork which id is passed.
    pub fn read_matching_artwork_id(artwork_id: i64) -> Result<Self> {
        let mut query = Query::new(
            format!("{READ_QUERY} WHERE artwork_id = :artwork_id ORDER BY id"),
            &Self::map_row,
        );
        query.set_bindings(vec![(":artwork_id", artwork_id.into())]);
        query.execute().map(|r| r.into())
    }

    fn map_row(row: Row) -> Testimony {
        RawTestimony {
            id: <i64 as database::MapRowField<i64>>::read(&row, "id"),
            visitor_id: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "visitor_id",
            ),
            artwork_id: <i64 as database::MapRowField<i64>>::read(&row, "artwork_id"),
            content: <String as database::MapRowField<String>>::read(&row, "content"),
            source_lang: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "source_lang",
            ),
            content_fr: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "content_fr",
            ),
            content_nl: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "content_nl",
            ),
            content_en: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "content_en",
            ),
            city: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "city",
            ),
            status: <String as database::MapRowField<String>>::read(&row, "status"),
            consent_given: <bool as database::MapRowField<bool>>::read(&row, "consent_given"),
            created_at: <String as database::MapRowField<String>>::read(&row, "created_at"),
            moderated_at: <Option<String> as database::MapRowField<Option<String>>>::read(
                &row,
                "moderated_at",
            ),
            moderated_by: <Option<i64> as database::MapRowField<Option<i64>>>::read(
                &row,
                "moderated_by",
            ),
        }
        .into()
    }

    /// Inserts a new testimony, returning it as a list of testimonies containing a single element.
    ///
    /// `city` is the recording machine's location id, stamped by the client (not visitor input).
    /// `visitor_id` is the client's session id (Session.id on the frontend); the matching
    /// `visitors` row is created here if it doesn't exist yet (one kiosk, one session at a
    /// time, so a plain upsert is enough — no concurrent-session id collisions to guard against).
    pub fn new_testimony(
        artwork_id: i64,
        content: String,
        city: Option<String>,
        visitor_id: Option<String>,
    ) -> Result<Self> {
        if let Some(id) = &visitor_id {
            let mut visitor_query = Query::new(
                "INSERT OR IGNORE INTO visitors(id) VALUES (:id)",
                &|_row| (),
            );
            visitor_query.set_bindings(vec![(":id", id.clone().into())]);
            visitor_query.execute()?;
        }

        let mut insert_query = Query::new(
            "INSERT INTO Testimonies(visitor_id, artwork_id, content, city, consent_given, moderated_at, moderated_by) VALUES (:visitor_id, :artwork_id, :content, :city, :consent_given, :moderated_at, :moderated_by) RETURNING *",
            &Self::map_row,
        );
        insert_query.set_bindings(vec![
            (
                ":visitor_id",
                visitor_id.map(Value::from).unwrap_or(Value::Null),
            ),
            (":artwork_id", artwork_id.into()),
            (":content", content.into()),
            (
                ":city",
                city.map(Value::from).unwrap_or(Value::Null),
            ),
            (":consent_given", 1.into()),
            (":moderated_at", Value::Null),
            (":moderated_by", Value::Null),
        ]);
        insert_query.execute().map(|r| r.into())
    }

    /// Moderates a testimony: sets its status (`validated` or `censored`), `moderated_at`
    /// to now, and `moderated_by` to the pseudo-staff row for `moderator_city` (see
    /// `staff::resolve_kiosk_id` — no individual staff-identity concept exists yet, so
    /// moderation is attributed to "the kiosk at <city>").
    pub fn update_status(id: i64, status: &str, moderator_city: &str) -> Result<Self> {
        if status != "validated" && status != "censored" {
            bail!("invalid status {status:?}: must be \"validated\" or \"censored\"");
        }
        let moderated_by = staff::resolve_kiosk_id(moderator_city)?;

        let mut query = Query::new(
            "UPDATE testimonies SET status = :status, moderated_at = datetime('now'), moderated_by = :moderated_by \
             WHERE id = :id RETURNING *",
            &Self::map_row,
        );
        query.set_bindings(vec![
            (":status", status.into()),
            (":moderated_by", moderated_by.into()),
            (":id", id.into()),
        ]);
        query.execute().map(|r| r.into())
    }
}
