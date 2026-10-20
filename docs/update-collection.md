# How to update the kiosk's collection

Use this procedure when **the collection itself has changed** in the repo
(new artworks, a new partner museum, new media, corrected translations), and
you need those changes on a kiosk **without losing the visitors' data**
collected on site (testimonies, visits, receipts).

For a code-only update, [update.md](update.md) is enough.

## Why a separate procedure?

The kiosk's database (`database/pp1_collection.db`) holds two kinds of data:

- **reference data** (artworks, translations, media, the recorded
  interviews), maintained in the repo;
- **visitors' data** (testimonies, visits, summaries), which only exists on
  the kiosk.

`update.sh` always keeps the kiosk's own database, so visitors' data is
never overwritten — but for the same reason, a new collection never
reaches the kiosk. `scripts/apply-remote-db.sh` merges the two: it takes
the reference data from the repo and carries over the visitors' data from
the kiosk.

> **Never run `scripts/sync-db.sh` while the repo is public.** It pushes the
> kiosk's database — visitors' testimonies included — to GitHub.

## You'll need

- A keyboard and mouse (wireless with a USB dongle is easiest)
- Internet access: Ethernet cable, wifi, or a phone hotspot
- An empty **USB key** (100 MB is plenty) for the database backup
- The Mac mini's administrator password
- About 1 hour, including 10–20 minutes of build time

Tell the staff on site that the kiosk and the moderation tool will be
unavailable during that time.

## Steps

### 1. Leave kiosk mode

1. [ ] Plug in the keyboard and mouse. If you unplug something from the
   USB hub to make room, **note what it was** (it is often the receipt
   printer).
2. [ ] Press `Cmd + Q` to quit the kiosk app. This only closes Chrome: the
   backend keeps running in the background, which is expected.
3. [ ] **Turn off Internet Sharing**: Apple menu → System Settings →
   General → Sharing → **Internet Sharing** off.
4. [ ] **Connect to the internet** (Ethernet, wifi or hotspot) and check
   that a web page loads.
5. [ ] **Open Terminal** (`Cmd + Space`, type `Terminal`, Enter). Run
   everything below in that same window.

### 2. Fetch the update

```bash
cd ~/Desktop/Traces && ./scripts/update.sh
```

(Adjust the path if the repo lives elsewhere, e.g. `~/Traces`.)

- This takes 10–20 minutes, most of it compiling. **Do not restart the Mac
  mini** while it runs.
- It is done when the `%` or `$` prompt comes back with no `error` line
  just above it.
- Network error (`Could not resolve host`, `unable to access`): check the
  connection and run the same command again.
- Any other error, especially one mentioning `conflict` or
  `would be overwritten`: stop and ask a developer.

At this point the kiosk still runs on its **old** database.

### 3. Merge the databases

```bash
./scripts/apply-remote-db.sh
```

Nothing is replaced until you answer `y` at the end.

1. [ ] The script stops the backend and saves a backup of the kiosk's
   database: `Backup of the live db: ~/Desktop/kiosk_db_backup_YYYYMMDD-HHMM.db`.
2. [ ] It compares the two databases, for example:
   ```
   Live db (kiosk)      : 116 artworks, 42 visitor testimonies
   Reference db (repo)  : 230 artworks
   ```
3. [ ] It prints the merge report, for example:
   ```
     • visiteurs repris : …
     • consultations reprises : …
     • témoignages visiteurs repris : 42 (ids réattribués à partir de 156)
     • résumés repris : …
     • résultat : 230 œuvres, 150 interviews, 42 témoignages visiteurs
     • références d’œuvres cassées : 0
     • vecteurs d’embedding : 230/230
   ```
4. [ ] It stops on `Apply this database to the kiosk? [y/N]`. **Don't
   answer yet.**
5. [ ] **Copy the backup to the USB key**: in Finder, drag
   `kiosk_db_backup_….db` from the Desktop to the key, wait for the copy to
   finish, eject the key.
6. [ ] **Check the report**:
   - the artwork count matches the repo (`Reference db` line);
   - `témoignages visiteurs repris` equals the number on the
     `Live db (kiosk)` line;
   - `références d’œuvres cassées : 0`;
   - `vecteurs d’embedding` shows every artwork (e.g. `230/230`).
7. [ ] All good: type `y`, Enter. The script ends with
   `Done: … artworks, … visitor testimonies kept.`
8. [ ] Anything off: type `N`, Enter. Nothing is changed. Take a photo of
   the screen and ask a developer.

Two messages that are acceptable:

- *consultations ignorées*: visits to an artwork that was removed from the
  collection. Expected.
- *N testimony(ies) set aside*: testimonies about a removed artwork. They
  are not lost: the script saved them to
  `~/Desktop/temoignages_orphelins_….csv`. Copy that file to the USB key
  too and pass it on to a developer.

The USB key contains visitors' testimonies: keep it with you, don't leave
it on site.

### 4. Back to kiosk mode

1. [ ] **Disconnect the internet** (unplug Ethernet, turn off the hotspot
   or leave the wifi).
2. [ ] **Turn Internet Sharing back on** (Apple menu → System Settings →
   General → Sharing). Without it, staff can't reach the moderation tool.
3. [ ] **Restart the Mac mini.** The kiosk starts again on its own after
   1–2 minutes.

### 5. Check

Do a short test visit and tick each item:

- [ ] Full screen, no cursor, no window open.
- [ ] The new artworks show up.
- [ ] A video artwork plays on its page (videos start on their own, muted
  and without controls — that's expected) while its grid thumbnail stays a
  photo.
- [ ] A receipt prints at the end of the visit, in the visit's language
  (test at least FR and EN).
- [ ] An artwork that had validated visitor testimonies still shows them.
- [ ] Staff can open the moderation tool and still see the testimonies
  collected before the update.

Don't leave a testimony during the test, or ask the staff to reject it in
the moderation tool.

Finally, unplug the keyboard and mouse and plug back in whatever you
removed from the USB hub in step 1.

## Troubleshooting

Whatever happens, take a photo of the Terminal before trying anything
else.

| Message or symptom | What to do |
| --- | --- |
| `Could not resolve host` during `update.sh` | Check the internet connection, run `./scripts/update.sh` again |
| `conflict` or `would be overwritten` during `update.sh` | Stop, ask a developer |
| `ABORTED: the backend is still running on port 8000` | Run `lsof -ti tcp:8000 \| xargs kill`, then `./scripts/apply-remote-db.sh` again |
| `WARNING: the reference db has no more artworks than the kiosk` | Answer `N`: `update.sh` did not complete. Run it again, then `apply-remote-db.sh` |
| `ABORTED: merged db has … visitor testimonies` | Nothing was changed. Keep the backup, ask a developer |
| `vecteurs d’embedding` lower than the artwork count | Answer `N`, ask a developer |
| Kiosk doesn't come back, or shows a blank page | Wait 2 minutes, restart once; otherwise ask a developer |
| `Cannot print receipt` at the end of a visit | The backend can't find the printer: see below |

### Receipt printer

The backend talks to the Epson thermal printer directly over USB
(Vendor ID `0x04b8`, Product ID `0x0e28`).

1. **Check the printer**: powered on, paper loaded, cover closed, USB cable
   plugged in (directly into the Mac mini if possible, rather than the
   hub). Unplugging and replugging it is often enough.
2. **Self-test**, without the Mac: switch the printer off, hold the
   **FEED** button, switch it on, release after 1–2 seconds. A test page
   should print. Nothing comes out: paper jam, cutter or paper exit
   blocked. A blank page comes out: the paper roll is upside down (thermal
   paper only prints on one side).
3. **Check that the Mac sees it**: hold **Option**, click the Apple menu →
   **System Information** → Hardware → **USB**. Or, in Terminal:
   ```bash
   system_profiler SPUSBDataType SPUSBHostDataType 2>/dev/null | grep -i -A8 epson
   ```
   A different Product ID means a different printer model: it is hard-coded
   in `backend/src/print.rs`, ask a developer.
4. **Print a test receipt without a full visit** (the backend must be
   running, i.e. the kiosk has started; `Cmd + Q` keeps it running):
   ```bash
   sips -Z 576 ~/Desktop/Traces/frontend/public/images/partners.png --out /tmp/t.png
   curl -i -H "Content-Type: image/png" --data-binary @/tmp/t.png http://127.0.0.1:8000/api/print_png
   ```
   `HTTP/1.1 200 OK` and a receipt with the partner logos: everything
   works. `200 OK` but no receipt: the problem is in the printer (paper,
   roll). `500`: send the message and the output of
   `tail -30 ~/Desktop/Traces/logs/server.log` to a developer.

### Rolling back to the previous database

Only if a developer asks you to. Quit the kiosk (`Cmd + Q`), then in
Terminal, replacing `YYYYMMDD-HHMM` with the backup's date:

```bash
lsof -ti tcp:8000 | xargs kill
cp ~/Desktop/kiosk_db_backup_YYYYMMDD-HHMM.db ~/Desktop/Traces/database/pp1_collection.db
rm -f ~/Desktop/Traces/database/pp1_collection.db-journal
```

Then restart the Mac mini.

## Don't

- **Don't run `sync-db.sh`** (see above).
- Don't type `git` commands yourself (`pull`, `reset`, `checkout`,
  `stash`): the two scripts handle Git without touching visitors' data.
- Don't restart the Mac mini during `update.sh`, or before answering the
  question at the end of `apply-remote-db.sh`.
- Don't answer `y` before copying the backup to the USB key and checking
  the report.
- Don't delete `kiosk_db_backup_….db` from the Desktop until a developer
  has confirmed the update.
- Don't forget to turn Internet Sharing back on (step 4).
