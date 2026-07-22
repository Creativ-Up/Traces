# TRACES kiosk — production setup

## Layout

```
./
├── scripts/    install.sh, build.sh, run.sh, update.sh, uninstall.sh, .env
├── backend/    pp1-backend-rust-master checkout
├── frontend/   traces checkout (built output at frontend/build/)
├── assets/     artwork images, served at /assets
└── logs/
```

Copy `scripts/.env.example` to `scripts/.env` and adjust if your layout differs.

## Scripts

Run from the project root:

```
scripts/install.sh     one-time setup (needs connectivity): toolchains, deps,
                        first build, registers the TRACES LaunchAgent. Safe to re-run.
scripts/build.sh        builds backend + frontend, offline.
scripts/run.sh          starts the backend, opens Chrome in kiosk mode.
scripts/update.sh       pulls latest changes and rebuilds (needs connectivity).
scripts/uninstall.sh    unregisters the TRACES LaunchAgent. Removes nothing else.
```

The kiosk itself runs offline (it's the one providing wifi, not consuming
it) — only `install.sh` and `update.sh` touch the network.

## What the backend serves

- `/` — the kiosk app
- `/moderation` — moderation tool, for a phone on the kiosk's wifi
- `/assets/*` — artwork images
- `/api/*` — backend routes

## Troubleshooting

- **binary/build not found** — run `scripts/build.sh` (or `scripts/install.sh` on a fresh machine).
- **server never ready** — check `logs/server.log`; Ollama not running is a common cause for `/api/summary` (the server still boots regardless).
- **TRACES not starting at login** — check Console.app or `logs/launchagent.log`.
