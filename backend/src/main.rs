mod artworks;
mod common;
mod database;
mod emotions;
mod ollama;
mod print;
mod questions;
mod scoring;
mod staff;
mod summaries;
mod testimonies;
mod transcription;
mod types_of_object;

use crate::{
    artworks::{Artworks, ResultArtwork},
    ollama::VisitedArtwork,
    print::LocalPrinter,
    questions::{Questions, QuestionsState},
    summaries::Summary,
    testimonies::Testimonies,
    transcription::TranscriptionState,
};
use rocket::{
    Request, Responder, Response, State,
    data::{Capped, Data, ToByteUnit},
    fairing::{Fairing, Info, Kind},
    fs::{FileServer, NamedFile},
    get,
    http::Header,
    launch, options, patch, post, routes,
    serde::json::Json,
};
use serde::Deserialize;
use std::path::PathBuf;

const SERVER_FRONTEND_DIR_VAR: &str = "SERVER_FRONTEND_DIR_VAR";
const SERVER_ASSETS_DIR_VAR: &str = "SERVER_ASSETS_DIR_VAR";

#[derive(Responder)]
#[response(status = 500, content_type = "json")]
struct ErrorResponse {
    error_msg: String,
}

#[get("/")]
fn index_route() -> &'static str {
    "Server ok"
}

// Catch-all preflight responder: browsers require CORS preflight (OPTIONS) requests to
// get a successful status before sending the actual request (e.g. any POST with a
// non-"simple" Content-Type like audio/wav or text/plain triggers one) — a 404 here, even
// with the Cors fairing's headers attached, still fails the preflight and blocks the real
// request. The Cors fairing (on_response) attaches the actual CORS headers below.
#[options("/<_path..>")]
fn options_route(_path: std::path::PathBuf) {}

#[get("/questions")]
fn questions_route(questions: &State<QuestionsState>) -> Json<Questions> {
    Json(questions.questions().clone())
}

#[get("/artworks?<q>&<h>")]
fn artworks_question_route(
    q: usize,
    h: Option<&str>,
) -> Result<Json<Vec<ResultArtwork>>, ErrorResponse> {
    let mut artworks = Artworks::read_matching_question_id(q as i64)
        .map(Json)
        .map_err(|e| ErrorResponse {
            error_msg: format!("{e:?}"),
        });
    if let Some(history) = h {
        let indices = history
            .split(',')
            .map(str::parse::<i64>)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| ErrorResponse {
                error_msg: format!("syntax error in param list: {e:?}"),
            })?;
        artworks = scoring::proposals_from_history(&indices)
            .map(Json)
            .map_err(|e| ErrorResponse {
                error_msg: format!("{e:?}"),
            });
    }
    artworks
}

#[get("/testimonies?<a>")]
fn testimonies_route(a: usize) -> Result<Json<Testimonies>, ErrorResponse> {
    Testimonies::read_matching_artwork_id(a as i64)
        .map(Json)
        .map_err(|e| ErrorResponse {
            error_msg: format!("{e:?}"),
        })
}

// Global moderation queue: every testimony across every artwork, any status — unlike
// GET /testimonies, no server-side status filtering (moderators need to see validated/
// censored testimonies too, e.g. to re-censor one that was validated by mistake).
#[get("/testimonies/all")]
fn testimonies_all_route() -> Result<Json<Testimonies>, ErrorResponse> {
    Testimonies::read_all().map(Json).map_err(|e| ErrorResponse {
        error_msg: format!("{e:?}"),
    })
}

// `city` is the moderating kiosk's location id — stands in for an individual moderator's
// identity until a real staff-identity concept exists (see staff::resolve_kiosk_id).
#[patch("/testimony/<id>?<status>&<city>")]
fn moderate_testimony_route(
    id: i64,
    status: &str,
    city: &str,
) -> Result<Json<Testimonies>, ErrorResponse> {
    Testimonies::update_status(id, status, city)
        .map(Json)
        .map_err(|e| ErrorResponse {
            error_msg: format!("{e:?}"),
        })
}

#[post("/transcript", format = "audio/wav", data = "<data>")]
async fn transcript_route(
    data: Data<'_>,
    transcription: &State<TranscriptionState>,
) -> Result<Json<String>, ErrorResponse> {
    let bytes: Capped<Vec<u8>> = data
        .open(20_i32.mebibytes())
        .into_bytes()
        .await
        .map_err(|e| ErrorResponse {
            error_msg: format!("while reading request body: {e:?}"),
        })?;
    let result = transcription
        .transcription()
        .transcript_bytes(&bytes.into_inner());
    result.map(Json).map_err(|e| ErrorResponse {
        error_msg: format!("{e:?}"),
    })
}

// `c` is the recording machine's location id, stamped by the client from its own config
// (not visitor input). Optional: defaults to None if the client doesn't send it.
// `v` is the client's session id (Session.id on the frontend), used as visitors.id.
#[post("/testimony?<a>&<c>&<v>", format = "plain", data = "<data>")]
fn new_testimony_route(
    a: usize,
    c: Option<String>,
    v: Option<String>,
    data: String,
) -> Result<Json<Testimonies>, ErrorResponse> {
    Testimonies::new_testimony(a as i64, data, c, v)
        .map(Json)
        .map_err(|e| ErrorResponse {
            error_msg: format!("{e:?}"),
        })
}

#[post("/print_png", format = "image/png", data = "<data>")]
async fn print_png_route(data: Data<'_>) -> Result<(), ErrorResponse> {
    let bytes: Capped<Vec<u8>> = data
        .open(20_i32.mebibytes())
        .into_bytes()
        .await
        .map_err(|e| ErrorResponse {
            error_msg: format!("while reading request body: {e:?}"),
        })?;
    LocalPrinter::print_bit_image_bytes(&bytes).map_err(|e| ErrorResponse {
        error_msg: format!("while reading request body: {e:?}"),
    })?;
    Ok(())
}

#[derive(Deserialize)]
struct SummaryRequest {
    visitor_id: String,
    lang: String,
    artworks: Vec<VisitedArtwork>,
}

// The frontend already has everything needed for the prompt (visited artworks, each with
// its own optional testimony, and the session language) — the backend's only jobs are
// calling Ollama and storing the result.
#[post("/summary", format = "json", data = "<request>")]
async fn summary_route(request: Json<SummaryRequest>) -> Result<Json<Summary>, ErrorResponse> {
    let SummaryRequest {
        visitor_id,
        lang,
        artworks,
    } = request.into_inner();

    let content = ollama::generate_summary(&lang, &artworks)
        .await
        .map_err(|e| ErrorResponse {
            error_msg: format!("{e:?}"),
        })?;

    Summary::store(visitor_id, content)
        .map(Json)
        .map_err(|e| ErrorResponse {
            error_msg: format!("{e:?}"),
        })
}

// Falls back to `<path>.html` when the frontend FileServer (mounted at "/", rank 11)
// doesn't find an exact match — lets e.g. /moderation resolve to moderation.html, so the
// built frontend's multiple HTML entries don't need their extension typed out. Lower rank
// number in Rocket means higher priority, so this must rank after FileServer's rank 11;
// anything looking like a file (has a '.') or an API call is left alone.
#[get("/<path..>", rank = 20)]
async fn html_fallback_route(path: PathBuf) -> Option<NamedFile> {
    let dir = std::env::var(SERVER_FRONTEND_DIR_VAR).ok()?;
    if path.extension().is_some() {
        return None;
    }
    let mut with_extension = path;
    with_extension.set_extension("html");
    NamedFile::open(std::path::Path::new(&dir).join(with_extension))
        .await
        .ok()
}

struct Cors;

#[rocket::async_trait]
impl Fairing for Cors {
    fn info(&self) -> Info {
        Info {
            name: "CORS",
            kind: Kind::Response,
        }
    }

    async fn on_response<'r>(&self, request: &'r Request<'_>, response: &mut Response<'r>) {
        if let Some(origin) = request.headers().get_one("Origin") {
            response.set_header(Header::new("Access-Control-Allow-Origin", origin.to_string()));
        }
        response.set_header(Header::new(
            "Access-Control-Allow-Methods",
            "GET, POST, PATCH, PUT, DELETE, OPTIONS",
        ));
        response.set_header(Header::new("Access-Control-Allow-Headers", "*"));
        response.set_header(Header::new("Access-Control-Allow-Credentials", "true"));
    }
}

#[launch]
async fn rocket() -> _ {
    Questions::read_all().expect("cannot read questions");
    Artworks::read_all().expect("cannot read artworks");
    Testimonies::read_all().expect("cannot read testimonies");
    // Ollama runs as its own persistent background service (started by its installer,
    // not something this server manages) — a summary request will fail loudly on its own
    // if it's down, but we also check once at boot so a misconfigured setup is obvious
    // immediately rather than only surfacing at the first visitor's end screen.
    if let Err(e) = ollama::check_reachable().await {
        eprintln!("warning: {e:?}");
    }
    let mut r = rocket::build()
        .manage(QuestionsState::default())
        .manage(TranscriptionState::default())
        .attach(Cors)
        // The CORS preflight catch-all must cover the whole server, not just /api, since
        // the built frontend served below is also fetched cross-origin during development
        // (Vite dev server on a different port than this backend).
        .mount("/", routes![options_route])
        .mount(
            "/api",
            routes![
                index_route,
                questions_route,
                artworks_question_route,
                testimonies_route,
                testimonies_all_route,
                moderate_testimony_route,
                transcript_route,
                new_testimony_route,
                print_png_route,
                summary_route,
            ],
        );
    if let Ok(dir) = std::env::var(SERVER_FRONTEND_DIR_VAR) {
        // Ranked after the assets FileServer below (default rank 10) so an explicit
        // /assets/<path..> mount wins that prefix outright — both would otherwise
        // ambiguously match the same requests at the same default rank and Rocket
        // refuses to launch.
        r = r
            .mount("/", FileServer::from(dir).rank(11))
            .mount("/", routes![html_fallback_route]);
    }
    if let Ok(dir) = std::env::var(SERVER_ASSETS_DIR_VAR) {
        r = r.mount("/assets", FileServer::from(dir));
    }
    r
}
