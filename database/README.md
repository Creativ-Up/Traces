# Adding your museum's collection to TRACES

TRACES shows visitors museum objects related to childhood, asks them a
question about their own memories and records their testimony. Memories
build up around each object over time.

The database already holds **230 artworks from five institutions** (Maison
des collections of the City of Mons, Abby, Le Fresnoy, Huis van Alijn and
MUMONS) and 150 recorded interviews. Every text exists in **French, Dutch and
English**.

This guide explains how your museum can add its own artworks to that
collection and show them on its own TRACES kiosk. You do everything
yourselves, with the scripts in this folder: there is no central team to
send your data to.

## Overview

Two people in your museum are involved: someone from the **collections**
team, who knows the objects, and a **technical** person comfortable with a
terminal, Git and Python.

| Step | Who | What |
| --- | --- | --- |
| [1](#1-before-you-start) | Technical | Get your own copy of TRACES and install the tools |
| [2](#2-choose-the-artworks) | Collections | Choose the artworks and the question each one is linked to |
| [3](#3-fill-in-the-spreadsheet) | Collections | Fill in a copy of the spreadsheet template |
| [4](#4-prepare-the-media) | Both | Gather the images and videos, then convert them |
| [5](#5-import-the-artworks) | Technical | Import the artworks into the database |
| [6](#6-translate-with-deepl) | Technical | Translate the texts into the other two languages with DeepL |
| [7](#7-review-the-translations) | Collections | Review the translations in an Excel workbook |
| [8](#8-load-compute-check) | Technical | Load the reviewed texts, compute the vectors, run the final check |
| [9](#9-publish-and-deploy) | Technical | Commit, push and update the kiosk |

## 1. Before you start

### Your own copy of TRACES

1. **Fork** [Creativ-Up/Traces](https://github.com/Creativ-Up/Traces) on
   GitHub. Your fork is where you commit your artworks, and where your kiosk
   downloads its updates from.
2. **Clone your fork onto your work computer** (Windows, macOS or Linux):
   ```bash
   git clone https://github.com/<your-account>/Traces.git
   ```
3. **Install your kiosk (a Mac mini) from your fork**, outside the Desktop
   folder, then follow "For kiosk administrators" in the root
   [README](../README.md):
   ```bash
   git clone --recurse-submodules https://github.com/<your-account>/Traces.git ~/Traces
   cd ~/Traces && ./scripts/install.sh
   ```
   A kiosk installed from the original repository would never receive your
   artworks.

A fork of a public repository is public: everything you commit (artworks,
images, texts) can be seen by anyone.

### Rights

- **Your artworks**: you must be allowed to show the images and texts in the
  installation **and** to publish them in a public GitHub repository. For
  photographs of identifiable living people, check that their consent covers
  this use.
- **The 230 existing artworks and the 150 interviews** belong to the partner
  institutions and to the people interviewed; they are not covered by the code
  licence. Ask the TRACES project partners before showing them in your own
  installation. The scripts cannot hide or remove them.

### Tools on the work computer

- [Git](https://git-scm.com) and Python 3.9 or newer. On macOS the commands
  are `python3` and `python3 -m pip`; a
  [virtual environment](https://docs.python.org/3/library/venv.html) avoids
  conflicts with the system Python.
- The Python packages (`sentence-transformers` also installs PyTorch, a
  download of a few GB):
  ```bash
  pip install openpyxl pillow deepl sentence-transformers sqlite-vec numpy
  ```
- [ffmpeg](https://ffmpeg.org), only if you have videos (it creates their
  thumbnails).
- A **DeepL API key**: create an account on
  [deepl.com/pro-api](https://www.deepl.com/pro-api). New accounts get the
  free "Developer" plan, a **one-time credit of 1,000,000 characters that
  never renews**; older accounts may still have the former "API Free" plan
  (500,000 characters per month). A collection of 100 artworks needs between
  50,000 and 200,000 characters, depending on the length of the texts. The
  translation script shows the credit DeepL reports for your key.

Give the key to the scripts through an environment variable, in the terminal
where you run them (it is lost when you close the terminal):

```bash
export DEEPL_AUTH_KEY="your-key"        # macOS / Linux
$env:DEEPL_AUTH_KEY = "your-key"        # Windows PowerShell
```

Never write the key in any file in the repository.

### Good habits

- Run the scripts **from the `database/` folder** of your clone.
- **Close the Excel workbooks** before running a script that reads or writes
  them.
- `import_collection.py` and `translate_collection.py` have a `--dry-run`
  option: it checks everything and writes nothing. Use it first.
- The database and the review workbook are tracked by Git. Until you have
  committed, this command, run from the **root** of the repository, undoes
  all your changes to them (media files copied into `assets/` must be deleted
  by hand):
  ```bash
  git restore --source=HEAD --staged --worktree database/pp1_collection.db database/review_translations.xlsx
  ```

## 2. Choose the artworks

Existing partners contributed between 4 and 99 artworks each. Look for:

- **a link with childhood**: toys, school, family photographs, clothing,
  archives (certificates, letters), celebrations, everyday objects…
- **good images**: artworks are shown large, on a 44-inch screen.

Each artwork is linked to **one of 12 questions**. During a visit, the kiosk
asks a question and shows a few artworks linked to it; the visitor chooses
one, explores it and the testimonies already left about it, then records
their own answer. Pick the question that fits each artwork best:

| No. | Question (English version, as shown on the kiosk) |
| --- | --- |
| 1 | What about you? What was your childhood like? Was it happy, sad, boring? What is the first memory that comes to mind when you think about your childhood? |
| 2 | If you had a very limited space to store memories, what are 3 memories you would keep? |
| 3 | And you? Do you keep a special or symbolic object from your childhood inherited by your parents? Can you share it's story? |
| 4 | Do you have childhood memories of waking up at night because of a nightmare? Or what was a memorable pleasant dream you remember still? |
| 5 | Did you have pets when you were a kid? What's your best childhood memory with a pet? |
| 6 | What was your favorite game when you were a child? |
| 7 | Do you have a childhood memory related to a letter, written, sent or received, that made an impression on you? Can you share your story? |
| 8 | Do you know why your parents choose your name? What's the story behind? |
| 9 | Do you have a childhood memory linked to a special piece of clothes of yours or a uniform you were wearing when you were little? |
| 10 | What's your best childhood memory linked with a celebration like Saint-Nicolas's day or christmas? |
| 11 | What is the first memorable childhood memory related to reuniting with loved ones that comes to mind? |
| 12 | And you, when you were a child and in need of being conforted or protected, did your parents or grandparents invoked a specific saint, relative or character, real or imaginary? Did you have a protective figure? Who was it? |

The French and Dutch versions are in the "Questions" sheet of the template.

## 3. Fill in the spreadsheet

**Make a copy** of `template_collection.xlsx`, for example
`database/collections/<your-museum>.xlsx`, and fill in its **"Artworks"**
sheet, one row per artwork, starting at row 3. Keep this file: you need it
again to correct or add artworks, and you commit it at step 9. Row 1 explains
each column and row 2 holds the headers: do not change them. The "Example"
sheet shows a filled-in row.

| Column | Required | Content | Example |
| --- | --- | --- | --- |
| Database ID | no | **Leave empty**: TRACES assigns the IDs | |
| Museum ID | yes | Inventory number of the object in your museum | `INV.1987.042` |
| Origin | yes | Name of your institution, spelled the same on every row and in every later spreadsheet | `Museum of Example` |
| Language | yes | Language of the texts of the row: `fr`, `nl` or `en` | `en` |
| Type of object | yes | A category from the "Types" sheet (drop-down list) | `Toy or game` |
| Date /period | yes | Date or period, in a readable form | `1935`, `1870-1880`, `19th century` |
| Title | yes | Title shown to visitors | `Teddy bear` |
| Author | no | Author, artist or maker | |
| Name | no | People related to the object (sitter, recipient…) | |
| Storage place | no | City or place where the object is kept | `Mons` |
| Keywords | yes | Keywords about the shape **and** the content, comma-separated | `teddy bear, plush, toy, worn fabric` |
| Emotions | yes | 2 to 4 emotions from the "Emotions" sheet, comma-separated | `Joy, Trust` |
| Explanation | yes | Text read by visitors | 3 to 8 sentences |
| Question | yes | Question number (1 to 12, see step 2) | `3` |
| Media | yes | Names of the image or video files, comma-separated | `INV_1987_042_front.jpg` |

Tips:

- **One language per row.** Write the texts for each artwork in the language
  you are most comfortable with; rows can use different languages. The other
  two languages are prepared at step 6.
- **The Explanation** is read on screen, standing up, by visitors of all
  ages: short sentences, no jargon. Describe concretely what the object shows
  and its story. This text is also used to find artworks that resemble each
  other.
- **Emotions** come from Plutchik's wheel of emotions: joy, trust, sadness,
  serenity… ("nostalgia", for instance, is not one of them). French, Dutch and
  English labels from the "Emotions" sheet are all accepted. Emotions are
  used to suggest related artworks to the visitor.
- **An object type missing from the list** is accepted and created, but it
  then has to be translated like the other texts: use an existing category
  when you can.

**Objects that carry a text** (letter, certificate, inscription, label): also
fill in the optional **"Transcriptions"** sheet. Copy the text as it is
written on the object (original spelling), add a short explanation for
visitors, and use the same Museum ID as in "Artworks".

## 4. Prepare the media

| Media | Expected format | Notes |
| --- | --- | --- |
| Images | JPG, PNG or TIF, at least 1,500 px on the long side | Converted to JPG, at most 2,000 px on the long side. One image per view; the **first image** in the Media column is the thumbnail |
| Videos | MP4 (H.264 codec), **under 100 MB** per file | An excerpt of 30 seconds to 3 minutes is enough. A thumbnail is created automatically |

- **Videos play without sound** and with no playback controls. If speech
  matters, provide a subtitled version (subtitles burnt into the image).
- MOV files and camera RAW files (NEF, CR2…) are not supported: export them to
  MP4 or JPG first.
- You do not need to rename your files: give their exact names in the Media
  column, and the script and the import apply the same naming rule. **But
  avoid names already used in `assets/`** by another museum (simple numbers
  such as `1972-158.jpg` already exist): adding your museum's name to your
  file names is the safest choice.

Put all the media files in one folder, then convert them into a **working
folder outside the repository**:

```bash
python prepare_media.py "<folder with your media>" "<working folder>" --assets ../assets
```

The script prints the number of files prepared, the files skipped and any
warning: missing ffmpeg, video codec other than H.264, file over 100 MB, or a
file name that **already exists in `assets/`**. In that last case, do not
copy: rename your file, update the Media column and prepare it again.

Then **copy the images and videos (not the `_media_mapping.csv` file) into
the `assets/` folder** at the root of the repository.

## 5. Import the artworks

Check first:

```bash
python import_collection.py pp1_collection.db "collections/<your-museum>.xlsx" --assets ../assets --dry-run
```

**Fix every line starting with ⚠ during the dry run** (see
[Troubleshooting](#troubleshooting)), then import:

```bash
python import_collection.py pp1_collection.db "collections/<your-museum>.xlsx" --assets ../assets
```

Expected output (example with two artworks):

```
  • artworks created: 2, updated: 0, already in the database and left unchanged: 0
  • new TRACES ids: 235-236 (give them to your reviewers; use --ids 235-236 with translate_collection.py)
  • transcriptions imported: 1
  • collection: 232 artworks
  • artworks to translate: 2
  • artworks without a vector: 2 (compute_embeddings.py, REQUIRED before deploying: ...)
    Museum ID → TRACES id
    INV.1987.042 → 235
    INV.1987.043 → 236
  → next step: python translate_collection.py pp1_collection.db review_translations.xlsx --ids 235-236 --dry-run
```

**Keep the list of TRACES IDs**: your reviewers need it at step 7, and you
need the range at step 6. If new object types were created, the report also
gives their IDs.

Running the import again never creates duplicates, but **it leaves imported
artworks unchanged**. To apply a fix to an artwork already imported (or a
Transcriptions row added afterwards), run the same command with `--update`.

## 6. Translate with DeepL

```bash
python translate_collection.py pp1_collection.db review_translations.xlsx --ids 235-236 --dry-run
python translate_collection.py pp1_collection.db review_translations.xlsx --ids 235-236
```

Replace `235-236` with your own range. The dry run lists the texts to
translate and the number of characters, without calling DeepL. The real run
shows your remaining DeepL credit, then:

```
  • workbook updated: rows added 8, rows updated 0, cells translated 16
```

The translations are written into `review_translations.xlsx`, **not into the
database**. To show them on the kiosk before the review, run steps 8 and 9
now, then again after the review.

Option: `--keep-titles` copies titles unchanged into the three languages
(film titles, proper names) instead of translating them.

## 7. Review the translations

This step is for the collections team. Machine translation is not good enough
on its own for texts shown to the public: **the review is essential**. A real
example: DeepL translated the Dutch title "Kinderen spelen school" (children
pretending to be at school) as "Children playing at school".

Send `database/review_translations.xlsx` to your reviewers. While they work on
it, do not run `translate_collection.py`. When they send it back, put it in
`database/` under the same name. The workbook's "Lisez-moi" sheet sums up the
rules, in French and then in English.

In the workbook:

- each sheet holds one kind of text: `Titres` (titles), `Descriptions`,
  `Description - Key words` (keywords), `Transcriptions` and
  `Transcriptions Explications` (explanations of the transcriptions),
  `Types d'objets` (object types);
- the workbook holds the texts of every partner: **only review the rows whose
  `id` is one of your TRACES IDs** (at the bottom of each sheet). In
  `Types d'objets`, the `id` is the ID of the object type, given by the import
  report;
- **correct only the yellow cells**. Those with the comment "Machine
  translation (DeepL), to review" have not been reviewed by anyone yet; you
  can delete the comment once a cell is reviewed;
- grey cells (ID, original text) must not be changed, and rows must not be
  added, deleted or moved.

What to check: the meaning, the vocabulary of your field, proper names,
titles (should they be translated or kept as they are?), and the register
(formal or informal address), consistent with the rest of your texts.

## 8. Load, compute, check

```bash
python import_translations.py pp1_collection.db review_translations.xlsx
python compute_embeddings.py pp1_collection.db
python check_collection.py --db pp1_collection.db --images ../assets
```

- `import_translations.py` loads the workbook into the database. A line
  "1 id(s) not in the database" for descriptions and keywords is normal: it
  refers to an artwork that was removed from the collection.
- `compute_embeddings.py` computes the vectors used to suggest related
  artworks. **It is required**: without them the kiosk server does not
  start. The first run downloads a model of about 1 GB.
- `check_collection.py` is the final check. It must end with:
  ```
  DATABASE READY TO DEPLOY
  ```
  It also lists "files in assets/ that no artwork uses". Most come from the
  existing collection; if one of your files is listed, check its Media cell.

## 9. Publish and deploy

From the root of your clone:

```bash
git add database/pp1_collection.db database/review_translations.xlsx database/collections/ assets/
git commit -m "Add the collection of <your museum>"
git push
```

Then update your kiosk with [`docs/update-collection.md`](../docs/update-collection.md).
That page was written for the pilot kiosk: replace `~/Desktop/Traces` with
the folder of your kiosk's clone (for example `~/Traces`). The procedure
keeps the testimonies already left by visitors, and stops without changing
anything if testimonies would be lost or if an artwork has no vector.

> **Never push a kiosk's database to GitHub**: it contains the visitors'
> testimonies, and the repository is public.

## Adapting the kiosk to your venue

A few settings depend on where the kiosk stands. They belong to the frontend
(the `frontend/` folder), a separate repository included as a Git submodule:
you cannot push changes to it, so you make them **on the kiosk**, in
`~/Traces/frontend/public/`, then run `./scripts/build.sh` and restart.

- `config.json`, key `SESSION.city`: a short lowercase ID for your location
  (for example `ghent`), stored with each visitor testimony and used by the
  moderation tool. `update.sh` keeps this change.
- `languages/fr.json`, `nl.json` and `en.json`, in `translations`: add a key
  `"city.<your-id>"` with the name of your city (without it, no location is
  shown next to the testimonies), and adapt `"credits"`.
- `images/partners.png` (credits screen) and `receipt-partners.svg` (printed
  ticket): the partner logos.

**`update.sh` does not keep the changes to the language files and images**,
and they can make it stop (`would be overwritten`). Before each update, keep
a copy of the files you changed and undo them with
`git -C frontend checkout -- public/languages public/images public/receipt-partners.svg`;
after the update, copy your versions back and run `./scripts/build.sh`.

## Later changes

- **Correct a translation**: correct it in `review_translations.xlsx`, then
  repeat steps 8 and 9.
- **Correct an original text** (title, explanation, keywords…): correct your
  spreadsheet, run the import with `--update`, translate again (step 6: only
  the changed texts are translated), review, then steps 8 and 9. `--update`
  only accepts your own spreadsheet, never `PP1-Collection_Database.xlsx`. A
  value it does not recognise (question, type, emotion, missing media file)
  never replaces the current one.
- **Add more artworks**: add rows to your spreadsheet and follow steps 4 to 9
  again. Artworks already imported are left unchanged.
- **Remove an artwork**: not handled by the scripts.
- **Syncing your fork with the original repository**: Git cannot merge two
  versions of the database or of the review workbook. Keep your own versions
  (`git checkout --ours database/pp1_collection.db database/review_translations.xlsx`);
  they already contain the original collection.

## Troubleshooting

| Message | What to do |
| --- | --- |
| `ModuleNotFoundError` | Install the Python packages (step 1) |
| `database not found` / `workbook not found` | Run the command from the `database/` folder and check the file name |
| `media "…" not found in assets/` | Copy the prepared media into `assets/` (step 4) and check the name in the Media column |
| `thumbnail "…-thumb.jpg" not found in assets/` | Video without a thumbnail: install ffmpeg and run `prepare_media.py` again |
| `… already exists in ../assets` (prepare_media) | Rename your file, update the Media column, prepare it again |
| `produced by several files` (prepare_media) | Two of your files get the same name: rename one |
| `emotion "…" is not in the reference list, ignored` | Use a label from the "Emotions" sheet of the template |
| `no recognised emotion` | Fill in "Emotions" with labels from the "Emotions" sheet |
| `question not recognised` | Use a question number from 1 to 12 |
| `unknown language` | Use `fr`, `nl` or `en` in the Language column |
| `unreadable date` | Write the date as a year, a range (`1870-1880`) or a century |
| `object type missing, row skipped` | Fill in "Type of object" |
| `"Database ID" or "Museum ID" is required` | Fill in "Museum ID" |
| `id … already belongs to "…"` | Leave "Database ID" empty |
| `artwork listed twice in the spreadsheet` | Two rows share the same Museum ID |
| `column "…" empty for N artwork(s)` | Fill in that column for the artworks listed |
| `already in the database and left unchanged` after a fix | Run the import again with `--update` |
| `missing DeepL key` | Set `DEEPL_AUTH_KEY` in the same terminal (step 1) |
| `DeepL refused the key` | The key is wrong: copy it again from your DeepL account |
| `cannot reach DeepL` | Check the internet connection |
| `not enough DeepL credit` / `DeepL credit used up` | Switch to a paid DeepL plan, or translate fewer artworks at a time with `--ids` |
| `cannot write …: close it in Excel` | Close the workbook in Excel and run the command again |
| `row(s) skipped because the source text changed after translation` | Run `translate_collection.py` before `import_translations.py` |
| `still missing a title or description` / `object types without a translation` | Run `translate_collection.py`, review, then `import_translations.py` |
| `sqlite-vec not loaded … final check skipped` | Harmless: the vectors are written anyway |
| `missing media files: N` / `artworks without a vector` / `BLOCKING ERROR(S)` | Copy the missing media, or run `compute_embeddings.py`, then the check again |
| `PP1-Collection_Database.xlsx must not be used to update existing artworks` | Use `--update` with your own spreadsheet only |

## Contents of this folder

| File | Role |
| --- | --- |
| `pp1_collection.db` | The SQLite database read by the kiosk server |
| `template_collection.xlsx` | The spreadsheet template for a new collection (copy it, do not fill it in directly) |
| `PP1-Collection_Database.xlsx` | The source spreadsheet of the 230 current artworks (same format, read-only) |
| `review_translations.xlsx` | The review workbook: the source of every FR / NL / EN text |
| `prepare_media.py` | Converts and renames the media files of a collection |
| `import_collection.py` | Imports the artworks of a spreadsheet into the database |
| `translate_collection.py` | Translates the missing texts with DeepL, into the review workbook |
| `import_translations.py` | Loads the review workbook into the database |
| `compute_embeddings.py` | Computes the vectors used to suggest related artworks |
| `check_collection.py` | Final check before deploying: media, vectors, translations |
| `schema.sql`, `SCHEMA.md` | The database schema and its technical documentation (in French) |

The database history (migrations V3 to V11, and the scripts removed in
October 2026) is summarised in [`SCHEMA.md`](SCHEMA.md).
