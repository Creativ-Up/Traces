use crate::database::{self, Query};
use anyhow::Result;

const KIOSK_STAFF_NAME: &str = "Kiosk";
const KIOSK_STAFF_ROLE: &str = "kiosk";

/// Resolves `city` (a kiosk's location id, e.g. "tourcoing") to a `staff.id`, creating a
/// pseudo-staff row for it if one doesn't exist yet. Used as a stand-in `moderated_by` until
/// a real staff-identity concept exists — moderation is attributed to "the kiosk at <city>"
/// rather than an individual. `staff.city` has no UNIQUE constraint, so this reads first
/// rather than relying on an upsert.
pub fn resolve_kiosk_id(city: &str) -> Result<i64> {
    let mut find_query = Query::new(
        "SELECT id FROM staff WHERE city = :city AND role = :role LIMIT 1",
        &|row| <i64 as database::MapRowField<i64>>::read(&row, "id"),
    );
    find_query.set_bindings(vec![
        (":city", city.into()),
        (":role", KIOSK_STAFF_ROLE.into()),
    ]);
    if let Some(id) = find_query.execute()?.into_iter().next() {
        return Ok(id);
    }

    let mut insert_query = Query::new(
        "INSERT INTO staff(name, city, role) VALUES (:name, :city, :role) RETURNING id",
        &|row| <i64 as database::MapRowField<i64>>::read(&row, "id"),
    );
    insert_query.set_bindings(vec![
        (":name", KIOSK_STAFF_NAME.into()),
        (":city", city.into()),
        (":role", KIOSK_STAFF_ROLE.into()),
    ]);
    insert_query
        .execute()?
        .into_iter()
        .next()
        .ok_or_else(|| anyhow::anyhow!("insert into staff returned no row"))
}
