use serde::Serialize;

#[derive(Clone, Serialize)]
pub struct InternationalizedString {
    en: String,
    fr: String,
    nl: String,
}

impl InternationalizedString {
    pub fn new<T>(en: T, fr: T, nl: T) -> Self
    where
        T: ToString,
    {
        InternationalizedString {
            en: en.to_string(),
            fr: fr.to_string(),
            nl: nl.to_string(),
        }
    }
}
