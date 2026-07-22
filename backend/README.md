# PP1-backend-rust

## How to build

Prerequisites:

- install the [Rust toolchain](https://rust-lang.org/tools/install/)
- adapt `Cargo.toml` depending on the GPU (see [qwen3-asr documentation on `crates.io`](https://crates.io/crates/qwen3-asr))
- install `sqlite3`?

Run `cargo build` (with `--release` for production) from the project root directory.
Then, run `cargo run` from the same directory to launch the server.
The server displays the connection address and port.

## Routes (exemples with cURL)

Checking the server is OK:

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl http://127.0.0.1:8000/
Server ok
```

Getting the list of questions:

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl http://127.0.0.1:8000/questions
[{"id":1,"content":"What about you? What was your childhood like? Was it happy, sad, boring? What is the first memory that comes to mind when you think about your childhood?"},...]
```

Getting the set of artworks related to a question:

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl http://127.0.0.1:8000/artworks?q=1
[{"id":1,"keywords":"child abuse, sadness, childhood, children drawings, family photo archive, autobiography","description":"Making this film at this time in my life seems essential for me. I have always felt great shame talking about my childhood, even if it always made me sad.\" This creative documentary made in animation from children's drawings, films and family photographs, uniquely evokes the traumas of a painful childhood in the small town of Frătăuții Vechi in Romania","media_url":"IMadeYou_01_053, IMadeYou_02_220, IMadeYou_03_406, IMadeYou_04_710, IMadeYou_05_828,","date_period":"2016","date_year_min":2016,"date_year_max":2016,"type_of_object_id":6,"emotions":"Anger, Sadness","origin":"Le Fresnoy","author_name":"Alexandru","birthday":null,"places":null,"storage_place":"Tourcoing","popularity":0,"question_id":1},...]
```

Getting the set of artworks related to a profile (set of already chosen artworks given by ids):

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl http://127.0.0.1:8000/artworks?h=1,53
[...]
```

Getting the testimonies related to an artwork:

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl http://127.0.0.1:8000/testimonies?a=1
[]
```

Transcription of an audio WAV file (the request body is the raw WAV file bytes, not a file path):

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl -X POST http://127.0.0.1:8000/transcript -H "Content-Type: audio/wav" --data-binary @sample1.wav
"The quick brown fox jumps over the lazy dog."
```

From a browser, this can be done with `fetch` by sending the WAV `Blob` directly as the request body:

```js
await fetch("http://127.0.0.1:8000/transcript", {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wavBlob,
});
```

Registration of a new testimony:

```
lonca@DESKTOP-H4UIK9I:~/projects/creativ-up/pp1-backend-rust$ curl -X POST http://127.0.0.1:8000/testimony?a=1 -H "Content-Type: text/plain" -d 'this is my first testimony'
[{"id":1,"visitor_id":null,"artwork_id":1,"content":"this is my first testimony","status":"pending","consent_given":true,"created_at":"2026-06-03 10:02:23","moderated_at":null,"moderated_by":null}]
```

Printing a PNG on a thermal printer managed by the [escpos](https://crates.io/crates/escpos) crate:

```
curl -X POST http://127.0.0.1:8000/print_png -H "Content-Type: image/png" --data-binary @image1.png
```

From a browser, this can be done with `fetch` by sending the PNG `Blob` directly as the request body:

```js
await fetch("http://127.0.0.1:8000/print_png", {
    method: "POST",
    headers: { "Content-Type": "image/png" },
    body: pngBlob,
});
```

## Transcription model

The first time the server is launched, it downloads the model used for transcription and place it into the `models` directory.
After each server launch, the model is lazily loaded: first transcription will take noticeably more time than for subsequent calls. It may be desired to trigger an initial "dry" transcription in order to improve the computation time for the first real transcription.

## Licence

PP1-backend-rust is developed at CRIL (Univ. Artois & CNRS).
It is made available under the terms of the GNU GPLv3 license.