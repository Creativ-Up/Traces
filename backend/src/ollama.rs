use anyhow::{Context, Result, anyhow};
use serde::{Deserialize, Serialize};

const BASE_URL: &str = "http://localhost:11434";
const MODEL: &str = "gemma4:e4b";

const SYSTEM_PROMPT: &str = "Rôle et contexte :
Tu es le guide du parcours « TRACES », une exposition sur les souvenirs
d'enfance entre Mons, Lens et Courtrai. À la fin de la visite, tu rédiges un
court récit personnalisé résumant le parcours du visiteur, qui sera imprimé
sur un ticket souvenir.

Données d'entrée :
Tu reçois la langue de session, la liste des œuvres explorées (type d'objet
et description), et parfois le témoignage laissé par le visiteur.

Instructions :
- Synthétise le parcours : ne fais pas une simple liste des œuvres.
  Identifie le fil conducteur, l'ambiance ou les thèmes qui les relient,
  comme les étapes d'un voyage.
- Évoque 2 à 3 œuvres par ce qu'elles montrent (l'enfant de marbre perdu
  dans ses pensées, le billet plié en deux...). Les œuvres n'ont pas de
  titre : n'en invente jamais, et ne mentionne aucun numéro d'inventaire.
- Si un témoignage du visiteur est fourni, fais-y écho avec délicatesse,
  sans le citer intégralement ni le déformer.
- Adresse-toi directement au visiteur et remercie-le de sa visite. En
  français, vouvoie (« vous ») ; en néerlandais, utilise « u ».
- Ton inspirant, poétique et chaleureux, mais sobre : pas d'emphase
  excessive.
- Ne mentionne aucune donnée personnelle (nom, âge, origine...).

Contraintes strictes :
- Réponds UNIQUEMENT dans la langue de session indiquée.
- 100 mots maximum. Sois concis et percutant.
- Texte brut uniquement : pas de markdown, pas de titre, pas d'emoji,
  pas de liste.";

/// One artwork the visitor viewed, as sent by the frontend (already resolved
/// client-side, so the backend does no artwork lookups of its own — see
/// `Session.trace` on the frontend). `testimony` is the visitor's own transcript
/// for this specific artwork, if they left one — a visitor can leave one per
/// artwork, not just one for the whole session.
#[derive(Deserialize)]
pub struct VisitedArtwork {
    pub type_of_object: String,
    pub description: String,
    pub testimony: Option<String>,
}

fn build_user_prompt(lang: &str, artworks: &[VisitedArtwork]) -> String {
    let mut prompt = format!("Langue de session : {lang}\n");
    for artwork in artworks {
        prompt.push_str(&format!(
            "Œuvres vues pendant la visite : {} - {}\n",
            artwork.type_of_object, artwork.description
        ));
        if let Some(testimony) = artwork.testimony.as_deref().filter(|t| !t.is_empty()) {
            prompt.push_str(&format!(
                "Témoignage laissé par le visiteur (optionnel) : « {testimony} »\n"
            ));
        }
    }
    prompt.push_str("Rédige le texte du ticket.");
    prompt
}

#[derive(Serialize)]
struct ChatMessage {
    role: &'static str,
    content: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: &'static str,
    temperature: f32,
    top_p: f32,
    top_k: u32,
    max_tokens: u32,
    messages: Vec<ChatMessage>,
}

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<ChatChoice>,
}

#[derive(Deserialize)]
struct ChatChoice {
    message: ChatResponseMessage,
}

#[derive(Deserialize)]
struct ChatResponseMessage {
    content: String,
}

/// Checks that Ollama is reachable, without loading a model. Called once at server startup
/// so a misconfigured/not-running Ollama is reported clearly instead of failing silently
/// the first time a visitor reaches the end screen.
pub async fn check_reachable() -> Result<()> {
    reqwest::get(BASE_URL)
        .await
        .context("Ollama not reachable at http://localhost:11434 — is `ollama serve` running?")?;
    Ok(())
}

/// Generates the ticket summary text for a visitor's session via Ollama's
/// OpenAI-compatible /v1/chat/completions endpoint, using the recommended Gemma4 params.
pub async fn generate_summary(lang: &str, artworks: &[VisitedArtwork]) -> Result<String> {
    let user_prompt = build_user_prompt(lang, artworks);

    let request = ChatRequest {
        model: MODEL,
        temperature: 1.0,
        top_p: 0.95,
        top_k: 64,
        // gemma4:e4b is a reasoning model: it spends output tokens on an internal
        // `reasoning` field before writing `content`, and `think: false` doesn't suppress
        // this (tested directly against Ollama). 350 — the actual target length per the
        // system prompt's "100 mots maximum" — was getting consumed entirely by reasoning,
        // leaving nothing for the real answer (finish_reason: "length", empty content).
        // The final answer's length is still bounded by the prompt, not by this cap.
        max_tokens: 1500,
        messages: vec![
            ChatMessage {
                role: "system",
                content: SYSTEM_PROMPT.to_string(),
            },
            ChatMessage {
                role: "user",
                content: user_prompt,
            },
        ],
    };

    let response = reqwest::Client::new()
        .post(format!("{BASE_URL}/v1/chat/completions"))
        .json(&request)
        .send()
        .await
        .context("while calling Ollama")?
        .error_for_status()
        .context("Ollama returned an error status")?
        .json::<ChatResponse>()
        .await
        .context("while parsing Ollama's response")?;

    response
        .choices
        .into_iter()
        .next()
        .map(|choice| choice.message.content)
        .ok_or_else(|| anyhow!("Ollama returned no choices"))
}
