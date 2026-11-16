# Galaxy Cube: notes for Claude Code

The Galaxy Cube is a small 3D-printed box (Raspberry Pi Zero 2 W) that lets Xbox, Nintendo Switch and
PlayStation players join the **GalaxySMP** Minecraft Bedrock server and use GalaxySMP voice chat.
It has a 128×64 OLED, a rotary knob (turn to scroll, press to select) and two buttons (TALK, MUTE).

**`GALAXY_CUBE.md` is the full spec.** Read the section you're working on before you write code.
Build it section by section; each section ends with what "done" means. If something in the spec has to
change, update `GALAXY_CUBE.md` in the same commit.

## Who you're working with

- The owner is **not a programmer** and often works from a phone. Explain things in plain words: what to
  plug in where, what to type, and what they should see when it works. Avoid jargon.
- Do the work yourself (write, run and test the code). Ask only when a decision is really theirs, and
  give a recommended option.
- Prefer short, simple, readable code over clever code.

## Target

- Raspberry Pi Zero 2 W, **Raspberry Pi OS Lite 64-bit (Bookworm)**, **Python 3.11**.
- **One asyncio process**: `cube/main.py` starts everything. Phantom (the console broadcast relay) runs as
  a child process.
- Python packages: `luma.oled`, `gpiozero`, `aiohttp`, `aiortc`, `sounddevice`, `numpy`, `qrcode`.
- Wi-Fi and the setup hotspot use NetworkManager (`nmcli`).
- It must work **without a keyboard or monitor**: screen + knob + buttons + the phone setup page only.
- It runs as the systemd service `galaxy-cube.service` (`Restart=always`). It writes only to
  `/var/lib/galaxy-cube/` (token and settings).

## Repo layout (from the spec, §4)

```
cube/main.py            starts everything (asyncio)
cube/config.py          device id, API base, paths
cube/ui/screen.py       OLED drawing
cube/ui/input.py        encoder + buttons → events
cube/ui/menu.py         menu tree and screens
cube/net/wifi.py        nmcli helpers, setup hotspot
cube/net/portal.py      captive setup web page (aiohttp)
cube/api.py             galaxymc.us API (pairing, /me)
cube/broadcast.py       starts/stops Phantom, status
cube/voice/client.py    voice WebSocket + WebRTC (aiortc)
cube/voice/audio.py     headset / built-in audio, mixing, volume
systemd/galaxy-cube.service
setup/install.sh        installs packages, Phantom, the service
setup/update.sh         git pull + restart
case/                   STL / 3MF files
```

## Fake mode (so it runs on a normal computer)

All hardware access (GPIO, I2C screen, I2S audio, `nmcli`, Phantom) must have a **fake / simulator mode**,
so the code can be run and tested here in Claude Code without a Pi.

- Turn it on with the environment variable `CUBE_FAKE=1`, e.g. `CUBE_FAKE=1 python3 -m cube.main`.
- Fake screen: draw to a PNG file (or print the text) instead of the OLED.
- Fake input: read keys from the terminal (for example ↑/↓ = turn the knob, Enter = press, t = TALK, m = MUTE).
- Fake Wi-Fi and Phantom: pretend they succeed and log what would have run.
- In fake mode, use a temp folder instead of `/var/lib/galaxy-cube/`.

Test every change in fake mode before saying it's done. Then tell the owner what to try on the real Cube.
`dev/mock_site.py` is a pretend galaxymc.us (including voice), and `python3 dev/drive.py` runs the full check
against it by reading the fake screen and turning the knob like a person would.
The phone simulator (`simulator/app.html`) mirrors `cube/main.py`: when menus or screens change, change both.

## The website (already live, don't change it from here)

The website side is on **https://galaxymc.us** and lives in a different repo (`2819-dev/galaxysmp`,
`src/routes/cube.js`). **Do not invent new endpoints.** Use only these (details in spec §7 and §8):

| Endpoint | Used for |
|---|---|
| `POST /api/cube/pair/start` `{ deviceId, model }` | get a pairing code |
| `POST /api/cube/pair/poll` `{ pollToken }` (every 3 s) | wait for the owner to link it |
| `GET /api/cube/me` (on boot + every 2 min) | account, server host/port, voice URL; also the "online" heartbeat |
| `wss://galaxymc.us/api/cube/voice` | voice chat (same protocol as the website's voice page) |

- After pairing, send `Authorization: Bearer <deviceToken>` and `X-Cube-Firmware: <version>` on every request.
- A **401** from `/api/cube/me` means the owner unlinked the Cube. Delete the token and go back to pairing.
- Errors come back as `{ "ok": false, "error": "…" }`. Show `error` on the screen.
- Take the server host and port from `/api/cube/me` (`server.host`, `server.port`). Never hard-code them.
- If the Cube really needs something new from the website, write down exactly what in a note for the owner
  instead of guessing an endpoint.

## Security rules

- **Never log, print or show the device token.** Store it only in `/var/lib/galaxy-cube/token` (chmod 600).
- Never commit secrets, tokens or Wi-Fi passwords. `.gitignore` already ignores `token` and `*.log`.
- The setup hotspot page only saves Wi-Fi. It never asks for galaxymc.us passwords (pairing uses the code).

## Style

- Screen and setup page text: short, friendly and professional. Use GalaxySMP colors on the setup page
  (dark navy, with a cyan → blue → purple gradient), mobile-first.
- Don't copy another game's or company's look, names or assets.
- Reconnect with backoff (1 s → 30 s) instead of crashing. Restart Phantom if it exits.

## Git

- Small, clear commits. Push to `main` when a section works, unless the owner says otherwise.
- Don't open pull requests unless asked.
