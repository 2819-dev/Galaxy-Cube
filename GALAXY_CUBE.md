# Galaxy Cube — build guide

The Galaxy Cube is a small 3D-printed box that lets **Xbox, Nintendo Switch and PlayStation** players
join the GalaxySMP Minecraft Bedrock server and use **GalaxySMP voice chat**. It has a small screen and a
rotary knob (turn to scroll, press to select), plus two buttons for voice chat.

This file is the complete spec. Open this repo in Cursor and build it section by section (each section ends
with what "done" means). The website side (pairing, accounts, voice server) **already exists and is live**
on galaxymc.us; this repo is only the Cube itself.

- Version 1 (this guide): **Galaxy Cube** — Raspberry Pi Zero 2 W. Console joining + voice chat.
- Later: **Galaxy Cube Lite** — ESP32-S3, console joining only (see §11).

**Status:** §3–§10 and §13 are built and tested in fake mode (`python3 dev/drive.py`). §11 (Lite) is for later.

---

## 1. How it works (big picture)

```
 Console (Xbox/Switch/PS) ── home Wi-Fi ──► Galaxy Cube ── internet ──► GalaxySMP server (galaxymc.smp.live:9030, UDP)
                                              │
                                              └── internet ──► galaxymc.us (pairing, voice chat)
```

**Console joining (“Server Broadcast”).** Consoles can't add custom servers, but they *do* show **LAN games**
under *Play → Friends → LAN Games*. Minecraft finds LAN games by broadcasting a small UDP "ping" on port
**19132**. The Cube answers that ping with GalaxySMP's name, so GalaxySMP appears in the LAN list. When the
player taps it, the console connects to the Cube, and the Cube relays every UDP packet to the real server and
back. To the server it looks like a normal player. Works on every console, with no settings to change on the
console. (This is the same idea as the open-source project **Phantom** — see §5.)

**Voice chat.** The Cube signs in to galaxymc.us as its owner (after pairing), opens the voice WebSocket and
sends/receives audio over WebRTC, exactly like the website's voice page does. Proximity works automatically:
the server knows where the owner's Minecraft player is.

**Both run at the same time** — the broadcast is a background service; voice is controlled with the two buttons.

---

## 2. Parts list (built-in mic + speaker, no soldering, ≈ $55)

Everything plugs together with jumper wires; the speaker's two wires go into a screw terminal. When buying,
check each board's listing says **pre-soldered** / **header soldered** (and for the amp: **with terminal block
soldered**). If a photo shows the pins lying loose next to the board, it needs soldering: skip that one.

| Part | Search for | Approx. price |
|---|---|---|
| Raspberry Pi Zero 2 W **with header** | "Raspberry Pi Zero 2 WH" | $15–18 |
| microSD card, 16 GB or bigger | "SanDisk 16GB A1 microSD" | $5 |
| Power supply, 5 V 2.5 A, micro-USB | "Raspberry Pi micro USB power supply" | $6–8 |
| 1.3" OLED 128×64, I2C, SH1106, 4 pins soldered | "1.3 inch OLED I2C SH1106" | $4–6 |
| Rotary encoder board with push | "KY-040 rotary encoder" | $2 |
| Knob cap, 6 mm D-shaft, 20–25 mm wide (if not included) | "6mm D shaft knob" | $1 |
| 2 × button boards with 3 pins (TALK, MUTE) | "KY-004 button module" | $2 |
| **Microphone board**, pins soldered | "INMP441 I2S microphone pre-soldered" | $4–6 |
| **Speaker amplifier board**, pins + screw terminal soldered | "MAX98357A I2S amplifier pre-soldered" | $5–8 |
| **Speaker**, 28 mm, 8 Ω, 0.5–1 W, with wires attached | "28mm 8 ohm speaker with wire" | $2 |
| Mini breadboard, 170 holes | "mini breadboard 170" | $1–2 |
| Jumper wires, 20 cm: female-female **and** male-female | "dupont jumper wires 40 pin" (one pack each) | $3–4 |
| Screws: 4 × M2.5 × 8 + 4 × M2.5 × 5 | "M2.5 screw kit" | $2–5 |
| Double-sided foam tape | | $1–2 |
| 3D-printed case (~80 g dark PLA + a little clear PLA/PETG) | files in `case/` | $2 |
| *Optional:* USB headset adapter + micro-USB OTG adapter | "USB sound card CM108", "micro USB OTG adapter" | $5–8 |

The optional headset adapter is for private voice chat: plug it in (with a headset) and the Cube uses it;
unplug it and the Cube uses its own mic and speaker (Audio: Auto).

**If you can't find pre-soldered mic/amp boards:** use a plug-in **USB microphone** (the tiny "mini USB mic"
dongles) and a small **USB speaker** instead, with a **micro-USB OTG hub** to plug both in. The Cube uses them
by itself. They're bulkier and don't fit the speaker ring in the base, so tape them inside.

---

## 3. Wiring (no soldering)

Pin numbers are the Pi's physical pin numbers. Pin 1 is at the end of the header nearest the SD card slot,
and it's the pin with a **square** solder pad on the back of the board. Odd pins (1, 3, 5 …) are on the row
toward the middle of the board, even pins (2, 4, 6 …) on the row along the board's edge.

Wires into the breadboard need a **male** end (male-female wires); wires from a board straight to the Pi are
female-female.

**3.3 V for four boards through the breadboard** (the Pi only has two 3.3 V pins):
Pi **pin 1** → one row of the breadboard (male-female wire). Then the screen's **VCC**, the knob's **+** and
both button boards' **+** each go into that same row.

Everything else goes straight from the board to the Pi with female-female wires:

| Board | Pin on board | Pi pin |
|---|---|---|
| Screen (OLED) | GND / SDA / SCL | 6 / 3 / 5 |
| Knob (KY-040) | GND / CLK / DT / SW | 9 / 11 / 13 / 15 |
| TALK button board | − / S | 25 / 29 |
| MUTE button board | − / S | 30 / 31 |
| Microphone (INMP441) | VDD / GND / L/R / SD | 17 / 14 / 20 / 38 |
| Microphone (INMP441) | SCK / WS | breadboard row C / row D (see below) |
| Amplifier (MAX98357A) | VIN / GND / DIN | 2 / 34 / 40 |
| Amplifier (MAX98357A) | BCLK / LRC | breadboard row C / row D (see below) |
| Speaker | its two wires | the amp's screw terminal: red → +, black → − |

The mic and the amp share two signals, and each Pi pin only takes one wire, so they meet on the breadboard:
Pi **pin 12** → row C, and the mic's **SCK** and the amp's **BCLK** into row C. Pi **pin 35** → row D, and the
mic's **WS** and the amp's **LRC** into row D. Leave the amp's **SD** and **GAIN** pins empty.

Button boards are made two ways (some give LOW when pressed, some HIGH). The Cube checks which kind it has
when it starts, so **don't hold a button while plugging the Cube in**.

**Mounting:** drop a printed `button_cap.stl` into each top hole from inside, then tape the button boards
under them. The speaker sits in the ring on the base (face down, over the grille holes); tape the amp next to
it. Tape the mic board behind the 3 × 3 mic holes on the front, with its little hole facing them.

`setup/install.sh` turns on the screen (I2C) and the mic + amp (I2S) in `/boot/firmware/config.txt`:

```
dtparam=i2c_arm=on
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard
```

**Done when:** `sudo bash setup/check.sh` says the screen and the built-in speaker/mic are found, and
Menu → Voice Chat → Join voice, then holding TALK, is heard on the website's voice page.

---

## 4. Software stack

- **Raspberry Pi OS Lite (64-bit, Bookworm)**. Python 3.11.
- Python packages: `luma.oled` (screen), `gpiozero` (knob + buttons), `aiohttp` (HTTP + WebSocket),
  `aiortc` (WebRTC), `sounddevice` + `numpy` (audio), `qrcode` (optional, QR for pairing).
- **NetworkManager** (`nmcli`) for Wi-Fi and the setup hotspot (default on Bookworm).
- Broadcast engine: **Phantom** binary (MIT license) — `phantom-linux-arm8` from github.com/jhead/phantom releases.

Repo layout:

```
galaxy-cube/
  GALAXY_CUBE.md          ← this file
  cube/
    main.py               ← starts everything (asyncio)
    config.py             ← device id, API base, paths
    ui/screen.py          ← OLED drawing (text, menus, icons, big code)
    ui/input.py           ← encoder + buttons → events
    ui/menu.py            ← menu tree and screens
    net/wifi.py           ← nmcli helpers, setup hotspot
    net/portal.py         ← captive setup web page (aiohttp)
    api.py                ← galaxymc.us API (pairing, /me)
    broadcast.py          ← starts/stops Phantom, status
    voice/client.py       ← voice WebSocket + WebRTC (aiortc)
    voice/audio.py        ← picks headset / built-in, mixing, volume
  systemd/galaxy-cube.service
  setup/install.sh        ← installs packages, Phantom, service
  setup/update.sh         ← git pull + restart
  dev/mock_site.py        ← pretend galaxymc.us for testing on a computer
  case/                   ← STL / 3MF files for the body
```

One process (`main.py`) with asyncio tasks is simplest; Phantom runs as a child process.

---

## 5. Server Broadcast (console joining)

**Use Phantom** rather than writing a RakNet relay from scratch:

```
./phantom-linux-arm8 -server galaxymc.smp.live:9030 -bind 0.0.0.0 -bind_port 19132
```

- Get host/port from `GET /api/cube/me` → `server.host`, `server.port` (don't hard-code; the owner may move servers).
- Phantom answers LAN pings with the real server's name and player count, and relays traffic.
- Start it when the user selects **Xbox / Switch / PlayStation Server Broadcast**; stop it when they select
  "Stop broadcast". Restart it automatically if it exits. Show "Broadcasting" + a dot on the home screen.
- All three menu items start the same broadcast (it works for every console); they exist so players know
  it's for them, and each shows short console-specific join instructions on the screen:
  - Xbox / Switch / PlayStation: *Minecraft → Play → Friends → LAN Games → GalaxySMP*.
- Firewall: allow UDP 19132 and 19133 in, and UDP out.
- The console must be on the **same Wi-Fi** as the Cube (some routers block broadcasts on "guest" networks —
  show a hint in the manual).

**Done when:** an Xbox or Switch on the same Wi-Fi sees "GalaxySMP" under LAN Games and can play.

---

## 6. First-time setup (Wi-Fi hotspot + setup page)

1. On boot, if no saved Wi-Fi connects within 20 s → start a hotspot:
   `nmcli dev wifi hotspot ifname wlan0 ssid CUBE-XXXX password galaxycube` (or open, no password).
   `XXXX` = last 4 hex digits of the Pi's serial (`/proc/cpuinfo`). This is also the **device id**: `CUBE-XXXX`.
2. Screen: "Join Wi-Fi CUBE-XXXX on your phone".
3. Run a small web page on `http://10.42.0.1/` (aiohttp). Make it a captive portal: run `dnsmasq` with
   `address=/#/10.42.0.1` while in hotspot mode, so phones open the page automatically.
4. The page lists nearby networks (`nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list`), user picks one and types
   the password. Save with `nmcli dev wifi connect "<ssid>" password "<pw>"`.
5. Stop the hotspot, connect, then go to **pairing** (§7).
6. Menu item **Settings → Change Wi-Fi** starts the hotspot again.

Style the setup page in GalaxySMP colors (dark navy, cyan→blue→purple gradient), mobile-first.

**Done when:** a fresh Cube can be put on home Wi-Fi from a phone without a keyboard.

---

## 7. Pairing with galaxymc.us (already live)

All endpoints are on `https://galaxymc.us`. JSON in, JSON out. Errors are `{ "ok": false, "error": "…" }`
with a 4xx status — show `error` on the screen.

1. `POST /api/cube/pair/start` `{ "deviceId": "CUBE-7F3A", "model": "cube" }`
   → `{ ok, code: "K7Q-29M", pollToken, expiresAt, url: "galaxymc.us/cube" }`
2. Screen: big **K7Q-29M**, "Go to cube.galaxymc.us and type this code". (Optional: QR code of
   `https://galaxymc.us/cube?code=K7Q29M` — the page fills the code in.)
3. Every 3 s: `POST /api/cube/pair/poll` `{ "pollToken": "…" }`
   → `{ status: "waiting" }` | `{ status: "linked", deviceToken, username }` | `{ status: "expired" }`
   On `expired`, get a new code. On `linked`, **save `deviceToken`** to `/var/lib/galaxy-cube/token`
   (chmod 600) and show "Linked to <username>!".
4. From then on send `Authorization: Bearer <deviceToken>` (and `X-Cube-Firmware: 1.0.0`).
   `GET /api/cube/me` →
   ```json
   { "ok": true,
     "device": { "id": 1, "deviceId": "CUBE-7F3A", "name": "Living room", "model": "cube" },
     "user": { "id": 14, "username": "Steve", "gamertag": "Steve" },
     "server": { "name": "GalaxySMP", "motd": "GalaxySMP", "host": "galaxymc.smp.live", "port": 9030 },
     "voice": { "url": "wss://galaxymc.us/api/cube/voice" } }
   ```
   Call it on boot and every 2 minutes (it's also the "online" heartbeat shown on the website).
   A **401** means the owner unlinked the Cube → delete the token and go back to pairing.

Owners manage Cubes at **galaxymc.us/cube** (rename, unlink, online status).
`cube.galaxymc.us` forwards there once that address is added in Cloudflare (see §12).

---

## 8. Voice chat

### Controls
- **TALK** (hold) = push-to-talk. **MUTE** (press) = mute/unmute mic. Long-press MUTE = deafen.
- Menu **Voice Chat** → *Join voice / Leave voice*, *Mode: Push-to-talk / Open mic*, *Group* (join / leave),
  *Global Mic* (only for people who have it), *Who's here*, *Audio: Auto / Headset / Speaker*, *Volume* (20–100 %).
- Groups are **made on the website**; the Cube joins and leaves them. A group with a password can only be
  joined from the Cube if its owner invited you (there's no keyboard to type a password).
- Home screen shows a small mic icon (talking / muted / deafened / off) and the group name.

### Connection
WebSocket `wss://galaxymc.us/api/cube/voice` with header `Authorization: Bearer <deviceToken>`.
It's the same protocol the website uses. Every request has a `req` number; the server answers
`{ "type": "reply", "req": n, ...data }` or `{ "type": "reply", "req": n, "error": "…" }`.

Server → Cube messages:
- `hello` `{ you: <userId>, range: 48, voiceMutedUntil }`
- `roster` `{ users: [{ id, username, inGame, dim, group, mic, deafened, talking, voiceMuted, global, published }], groups: [{ id, name, locked, room, staffOnly, members }] }`
- `pos` `{ list: [[userId, x, y, z, yaw, dim], …] }` (a few times a second)
- `talk` `{ id, on }`, `voice_muted` `{ until, reason }`, `closed` `{ reason }` (stop and show the reason)

Cube → server requests (`{ "type": …, "req": n, … }`):
- `state` `{ mic: true|false, deafened, talking }` (no reply; send `talking` on TALK press/release)
- `rtc.session` → creates the WebRTC session (call once after connecting)
- `rtc.push` `{ sdp, mid }` → `{ answer }` — publish your mic (sendonly audio transceiver)
- `rtc.pull` `{ owners: [userId, …] }` → `{ tracks: [{ mid, owner }], offer }` — receive people you can hear;
  if `offer` is set: set it as remote description, create an answer, then `rtc.renegotiate` `{ sdp }`
- `rtc.close` `{ mids, sdp }` → `{ answer }` — stop receiving tracks
- `group.join` `{ id, password? }`, `group.leave`, `group.create` `{ name, password? }`

### WebRTC with aiortc (same steps as `public/js/voice.js` on the website)
1. `RTCPeerConnection()`; add the mic as a **sendonly** audio track (48 kHz Opus).
2. `rtc.session`, then create an offer → `rtc.push { sdp, mid }` → set the `answer`.
3. Whenever the roster changes: pull everyone you can hear (same group, Global Mic, or in game nearby —
   the server checks, so just ask for everyone who is `published` and not you), close tracks of people who left.
4. Volume per person = proximity, with the website's curve (`distanceMix` in voice.js): full volume within
   4 blocks, fading smoothly to silence at the range (48), 0 in another dimension. Group members and Global Mic
   are full volume. Mix all received tracks to the output device.
5. PTT: keep the track published; send silence (or disable the track) when TALK isn't held, and send
   `state { talking }` on press/release so others see the talking icon in game.

### Audio devices
- **Auto**: if the USB headset card is present → use it (mic + headphones); otherwise use I2S mic + speaker.
- With the built-in speaker, use PTT by default (prevents echo), and apply a simple noise gate on the mic.

**Done when:** holding TALK on the Cube is heard on the website voice page, and website users are heard on the Cube.

---

## 9. Screen + menu

128×64 monochrome. Font: a pixel font (e.g. "Silkscreen" or "Press Start 2P" at 8 px) for a Minecraft feel.

Boot: animated star burst → **"Galaxy Cube"** wordmark (1 s) → status.

Home screen (each row has a 7×7 pixel icon; the same icons are in the phone simulator):
```
 Steve                  (·) ≋     ← account name; broadcast + Wi-Fi icons
 ─────────────────────────────
 (·) Broadcasting
 🎤  Builders - hold TALK          ← or Talking / Mic off / Deafened / Voice off
 ●   Online
                        MENU >
```

Menu (turn = move, press = select, "◂ Back" item at the top of each list):
```
▸ Xbox Broadcast
▸ Nintendo Broadcast
▸ PlayStation Broadcast
▸ Stop Broadcast            (only while broadcasting)
▸ Voice Chat ▸ Join / Leave · Push-to-talk / Open mic · Groups · Audio · Volume
▸ Account ▸ Linked to Steve · Unlink this Cube · Pair again
▸ Settings ▸ Wi-Fi · Brightness · Screen timeout · About (version, CUBE-XXXX, IP)
```
Screen dims after 60 s idle and turns off after 5 min (OLEDs burn in); any input wakes it.
The screen-off time can be changed in Settings (1 / 5 / 10 min / Never).
Menu labels are shortened ("Xbox Broadcast", not "Xbox Server Broadcast") so they fit the 128-px screen.

---

## 10. Reliability

- systemd service `galaxy-cube.service` (`Restart=always`), starts after `network-online.target`.
- Read-only root or at least `fsck` safe: write only token + settings to `/var/lib/galaxy-cube/`.
- Reconnect voice WebSocket with backoff (1 s → 30 s). Restart Phantom if it exits.
- Updates: `setup/update.sh` does `git pull` + restart; later, a menu item "Check for updates".
- Never log the device token.

---

## 11. Galaxy Cube Lite (later): ESP32-S3, broadcast only

- ESP32-S3 DevKit (~$7) + 0.96" OLED + encoder. No voice.
- Firmware in Arduino/ESP-IDF: Wi-Fi setup via **WiFiManager** captive portal (same CUBE-XXXX flow),
  pairing via the same `/api/cube/pair/*` with `"model": "lite"`.
- Broadcast: answer RakNet *Unconnected Ping* (0x01) / *Open Connection* on UDP 19132 with the server's pong,
  then relay UDP per client to `server.host:server.port`. One or two players at a time is realistic.

---

## 12. Things the owner does once (not code)

1. Create this GitHub repo and open it in Cursor.
2. **cube.galaxymc.us**: in the Cloudflare dashboard → Workers & Pages → *galaxysmp* → Settings →
   Domains & Routes → **Add → Custom domain** → `cube.galaxymc.us`. The website already sends that address
   to galaxymc.us/cube.
3. Print the case (§13), assemble, flash the SD card, run `setup/install.sh`.

---

## 13. Case (3D print) notes

The printable files are made by `case/make_case.py` (change a measurement at the top and run it again):
`case/shell.stl`, `case/base.stl`, `case/light_strip.stl`, `case/button_cap.stl` (print 2), and `case/preview.png`.

- 70 × 70 × 70 mm cube, rounded top and side edges (r = 8 mm), flat bottom. Shell ≈ 62 g, base ≈ 16 g PLA.
- Base plate slides into the bottom and is held by 4 × M2.5 × 8 screws from below into posts in the corners.
  The Pi sits on 4 posts on the base (M2.5 × 5 screws), its ports facing the back.
- Front: window for the OLED (30 × 15.5 mm, with a 1 mm bezel and a pocket behind it for the module), knob
  hole (7.4 mm, the encoder's nut holds it), 3 × 3 mic holes bottom right.
- Top: TALK and MUTE (12.6 mm holes). Print `button_cap.stl` twice: the caps drop in from inside and press
  the button boards taped underneath. Slot for the light strip.
- Back: one opening for the Pi's USB port (headset adapter) and power port.
- Base: ring for the 28 mm speaker with grille holes, 4 feet so the sound gets out.
- Print shell and base upside down / flat with no supports except the screen pocket (or use "supports on build
  plate only"). 0.2 mm layers, 3 walls, 15 % infill.
- Print the shell in dark PLA and `light_strip.stl` in clear/translucent PLA or PETG; optional: an addressable LED
  behind it that glows when broadcasting/talking (extra $1, GPIO12).

---

## 14. Manual (what goes in the box)

1. Plug in the Cube. The screen says **Galaxy Cube**.
2. On your phone, join the Wi-Fi **CUBE-XXXX** shown on the screen. A page opens: pick your home Wi-Fi.
3. The Cube shows a code. Go to **cube.galaxymc.us**, sign in, and type the code.
4. Turn the knob to your console's **Server Broadcast** and press it. In Minecraft: **Play → Friends → LAN Games → GalaxySMP**.
5. Voice chat: plug in a headset (or use the built-in mic and speaker), choose **Voice Chat → Join**, hold **TALK** to speak.

Your console and the Cube must be on the same Wi-Fi.
