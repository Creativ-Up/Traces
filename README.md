# TRACES

TRACES is a museum "photomaton" kiosk: visitors are guided through a short
session where they look at artworks and record spoken testimonies about
them. It runs as a single, self-contained kiosk machine (a Mac mini in
production) — no server infrastructure beyond that one machine, no
multi-kiosk concurrency to account for.

A session, roughly: a visitor picks a language, is shown a series of
artworks (selected via a scoring algorithm in the backend), records a short
voice testimony for each, and receives a printed thermal-paper receipt with
an AI-generated summary of their visit at the end. A separate `/moderation`
page (opened on a phone connected to the kiosk's own wifi hotspot) lets
staff approve or reject testimonies before they're shown to future
visitors.

---

## For kiosk administrators

### Scripts

Run from the project root:

```
scripts/install.sh     one-time setup (needs connectivity): creates .env from
                        .env.example if missing, initializes the frontend
                        submodule if empty, installs toolchains/deps, does the
                        first build (including pre-downloading the speech
                        model — see below), registers the TRACES LaunchAgent.
                        Safe to re-run.
scripts/build.sh        builds backend + frontend, offline.
scripts/run.sh          starts the backend, opens Chrome in kiosk mode.
scripts/update.sh       pulls the latest monorepo commits, syncs the frontend
                        submodule to whatever commit is currently pinned, and
                        rebuilds. Needs connectivity.
scripts/uninstall.sh    unregisters the TRACES LaunchAgent. Removes nothing else.
```

The kiosk itself runs offline (it's the one providing wifi, not consuming
it) — only `install.sh` and `update.sh` touch the network.

Copy `.env.example` to `.env` (done automatically by `install.sh` if
missing) and adjust if your layout differs.

**Run these directly (`./scripts/run.sh`, or double-click), not via
`bash scripts/run.sh` or `sh scripts/run.sh`.** `run.sh` specifically needs
zsh (macOS's default shell since Catalina, always present) — the others
are plain bash. Invoking `run.sh` with an explicit `bash`/`sh` bypasses its
`#!/bin/zsh` shebang and fails outright (`${0:A}` is a zsh-only
expansion). Running any of these scripts the normal way (double-click, or
`./scripts/whatever.sh`) always uses the correct interpreter automatically.

**Double-clicking these in Finder instead of running them from a
terminal is fine.** They're executable `.sh` files, so macOS opens them in
Terminal.app on double-click (not a text editor), and Terminal starts them
with the script's own folder as the working directory — every script here
resolves all its paths from its own location (`scripts/`), never from the
inherited working directory, so it behaves the same either way. One thing
to know: Terminal.app closes its window automatically once a script exits
successfully, so for a script that finishes quickly (e.g. `uninstall.sh`)
you may only see the window flash briefly — check `logs/server.log` (or
the relevant script's own output, scroll back if the window is still open)
if you're not sure something worked.

### The speech-to-text model download

The backend uses a local speech-to-text model (Qwen3-ASR, ~1.8GB) to
transcribe testimonies. `install.sh` downloads and caches it into
`backend/models/` explicitly (via `cargo run --example fetch_model`) as
part of setup, rather than letting it download lazily on the first
`run.sh` launch — the latter would risk `run.sh`'s `READY_TIMEOUT_SECS`
timing out during a slow first-time download on a fresh machine. Re-running
`install.sh` is safe; the download is skipped if the model is already
cached.

### Editable-in-production files

These can be changed on the deployed kiosk without touching source code or
rebuilding, and take effect on the next restart (or, for the frontend
config files, sometimes without even that — check the specific file):

- **`.env`** (project root) — machine-local paths, ports, Chrome profile
  location, etc. See `.env.example` for the full list with comments.
- **`frontend/build/config.json`** — kiosk behavior/tuning: session length,
  gamepad button mapping, particle/voice presets, printer settings, API
  mock mode, etc. This is `frontend/public/config.json` at build time,
  copied verbatim into the build output by Vite — editing the built copy
  directly works, but will be overwritten by the next `scripts/build.sh`.
  For a permanent change, edit `frontend/public/config.json` in source and
  rebuild.
- **`frontend/build/languages/{en,fr,nl}.json`** — all on-screen and
  printed text, per language. Same build-vs-source caveat as `config.json`
  above: edit `frontend/public/languages/*.json` for a change that
  survives a rebuild.

### What the backend serves

- `/` — the kiosk app
- `/moderation` — moderation tool, for a phone on the kiosk's wifi
- `/assets/*` — artwork images
- `/api/*` — backend routes

### Troubleshooting

- **binary/build not found** — run `scripts/build.sh` (or `scripts/install.sh` on a fresh machine).
- **server never ready** — check `logs/server.log`; Ollama not running is a common cause for `/api/summary` (the server still boots regardless).
- **TRACES not starting at login** — check Console.app or `logs/launchagent.log`.
- **`frontend/` is empty after cloning** — run `git submodule update --init` (see "The frontend submodule" below).

---

## For developers

### Repository structure

This is a monorepo combining three previously separate projects, plus the
scripts and static files needed to run the kiosk:

```
./
├── backend/     Rust/Rocket API server (own README: build details, routes)
├── database/    SQLite schema + Python migration pipeline (own README, in French)
├── frontend/    the kiosk UI — a git SUBMODULE, see "The frontend submodule" below
├── scripts/     install/build/run/update/uninstall — see "For kiosk administrators" above
├── assets/      artwork images, served at /assets
├── logs/        server.log, launchagent.log (gitignored; directory itself is tracked)
├── .env         local machine config, copied from .env.example — not tracked
└── .env.example template for .env
```

`backend/` and `database/` are plain subdirectories of this monorepo (no
history of their own beyond `backend/.git-patches/` — see below).
`frontend/` is different: it's a **git submodule**, its own independent
repository with its own remote. See the dedicated section below before
touching it.

### The frontend submodule

`frontend/` is `https://github.com/machines-studio/traces`, checked out at
whatever commit this monorepo currently pins it to — **not** automatically
the latest commit on its `main` branch. This is the normal, slightly
unintuitive thing about git submodules: the parent repo (this one) records
one exact commit, and that pin only moves when someone deliberately updates
it.

**Cloning this repo for the first time:**

```bash
git clone --recurse-submodules git@github.com:Creativ-Up/Traces.git
```

If you already cloned without `--recurse-submodules`, `frontend/` will
exist but be empty — run:

```bash
git submodule update --init
```

(`scripts/install.sh` does this for you automatically if it detects
`frontend/` is empty.)

**Updating the frontend submodule to a newer version:**

The frontend's own release flow is `yarn version` (bumps `package.json`,
tags the commit, pushes both — see `frontend/package.json`'s `postversion`
script). Pushing a tag on `frontend`'s repo triggers a GitHub Actions
workflow (`frontend/.github/workflows/bump-monorepo.yml`) that
automatically opens a commit on **this** repo bumping the submodule pointer
to that tag. In other words: cutting a new frontend release on its own repo
is normally enough — this monorepo picks it up on its own shortly after,
no manual step needed.

If you ever need to do it manually instead:

```bash
cd frontend
git fetch --tags
git checkout <tag-or-commit>
cd ..
git add frontend
git commit -m "Bump frontend submodule to <tag>"
git push
```

**Editing frontend code directly:** commit and push inside `frontend/`
itself (to `machines-studio/traces`, not this repo), then separately bump
and commit the pointer here, as above — two commits, two repos. Forgetting
the second step leaves this repo silently pointing at a stale frontend
commit. Also note `frontend/` sits in a detached-HEAD state after
`git submodule update` — run `git checkout main` inside it before
committing there.

### backend's squashed history

`backend/` was originally its own repository, handed over by its author as
a plain (non-versioned) directory and then git-tracked locally before
being folded into this monorepo. Its commit-by-commit history isn't in
`git log` here — instead, it's preserved as patch files in
`backend/.git-patches/` (one file per original commit, generated via
`git format-patch --root`), so the original author can see exactly what
changed since the handoff.
