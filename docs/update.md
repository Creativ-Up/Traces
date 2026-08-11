# How to update the kiosk

## You'll need

- A keyboard and mouse — wireless ones with a USB dongle receiver are
  easiest (no pairing, just plug in the dongle)
- Internet access: an Ethernet cable, a wifi network, or a phone hotspot

## Steps

1. [ ] **Plug in the keyboard and mouse** (or their USB dongle) — either
   directly into the Mac mini, or by unplugging something from the USB
   hub to free up a port.

2. [ ] **Quit the kiosk app.** Press `Cmd + Q`.

3. [ ] **Turn off Internet Sharing.** Apple menu → System Settings → General
   → Sharing → turn **Internet Sharing** off. If asked for a password, enter `traces`.

4. [ ] **Connect to the internet** — plug in Ethernet, or connect to wifi /
   a phone hotspot from the menu bar.

5. [ ] **Run the update.** On the Desktop, open the Traces folder, then navigate to `scripts`, and double-click **`update.sh`**. A Terminal
   window opens and runs for a few minutes. Wait until it finishes (the
   window closes, or the text stops and a `$` prompt appears).

   If it shows an error, check the internet connection and double-click
   `update.sh` again.

6. [ ] **Disconnect the internet** — unplug the Ethernet cable, turn off the
   phone hotspot, or disconnect the wifi from the menu bar.

7. [ ] **Turn Internet Sharing back on.** Apple menu → System Settings →
   General → Sharing → turn **Internet Sharing** back **on**. Without
   this, staff can't reach the moderation tool on site. If asked for a password, enter `traces`.

8. [ ] **Unplug the keyboard/mouse (or dongle)**, and plug back in
   whatever you unplugged from the USB hub in step 1 to make room for it.

9. [ ] **Restart the Mac mini.** The kiosk app starts back up on its own.

10. [ ] **Check it looks normal** — full-screen, no visible cursor, no
    windows open. If it doesn't, ask a developer for help rather than
    trying to fix it on site.
