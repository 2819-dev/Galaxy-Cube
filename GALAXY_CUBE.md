# Galaxy Cube — build guide

The Galaxy Cube is a small 3D-printed box that lets **Xbox, Nintendo Switch and PlayStation** players
join the GalaxySMP Minecraft Bedrock server and use **GalaxySMP voice chat**. It has a small screen and a
rotary knob (turn to scroll, press to select), plus two buttons for voice chat.

This file is the complete spec. Open this repo in Cursor and build it section by section (each section ends
with what "done" means). The website side (pairing, accounts, voice server) **already exists and is live**
on galaxymc.us; this repo is only the Cube itself.

- Version 1 (this guide): **Galaxy Cube** — Raspberry Pi Zero 2 W. Console joining + voice chat.
- Later: **Galaxy Cube Lite** — ESP32-S3, console joining only (see the last section).

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

## 2. Parts list (target ≤ $50)

| Part | Example | Approx. price |
|---|---|---|
| Raspberry Pi Zero 2 W (with header) | Pi Zero 2 WH | $15–18 |
| microSD card 16 GB (A1) | SanDisk 16 GB | $5 |
| 1.3" OLED 128×64, I2C (SH1106) — or 0.96" SSD1306 | | $4 (0.96" is $3) |
| Rotary encoder with push (KY-040 or bare EC11) | | $1–2 |
| 2 × 12 mm tactile buttons (TALK, MUTE) | | $0.50 |
| I2S microphone INMP441 | | $3 |
| I2S amplifier MAX98357A + 28 mm 8 Ω speaker | | $4 + $1.50 |
| USB headset adapter (CM108 "USB sound card" with mic + headphone jacks, or a TRRS 4-pole one) | | $4 |
| Micro-USB OTG adapter (for the USB sound card) | | $1 |
| Power: 5 V 2.5 A micro-USB supply | | $6 |
| Wires, screws, 3D-printed body (~60 g PLA) | | $2–3 |
| **Total** | | **≈ $45–50** |

**Ways to make it cheaper**
- **Headset only** (drop the I2S mic + amp + speaker): −$8.5 → ≈ $38.
- **0.96" OLED** instead of 1.3": −$1.
- Buy the Pi Zero 2 W **without** header and solder pins: −$2.
- Ship without a power supply ("use any phone charger"): −$6 → ≈ $32 with headset-only.
- The **Lite** (ESP32-S3, no voice) is ≈ $15–20 in parts (§11).

---

## 3. Wiring (Pi Zero 2 W, BCM pin numbers)

| Part | Pin on part | Pi pin |
|---|---|---|
| OLED (I2C) | VCC / GND / SDA / SCL | 3.3V (pin 1) / GND (6) / GPIO2 (3) / GPIO3 (5) |
| Encoder | CLK / DT / SW / + / GND | GPIO17 (11) / GPIO27 (13) / GPIO22 (15) / 3.3V / GND |
| TALK button | one side / other side | GPIO5 (29) / GND |
| MUTE button | one side / other side | GPIO6 (31) / GND |
| I2S bus (mic + amp share it) | BCLK / LRCLK (WS) | GPIO18 (12) / GPIO19 (35) |
| INMP441 mic | SD (data out) / L/R / VDD / GND | GPIO20 (38) / GND / 3.3V / GND |
| MAX98357A amp | DIN / VIN / GND / SD | GPIO21 (40) / 5V (pin 2) / GND / leave unconnected |
| USB sound card | — | the Pi's **USB** micro port (not PWR) via OTG adapter |

Buttons use the Pi's internal pull-ups (pressed = LOW). Enable I2C and I2S in `/boot/firmware/config.txt`:

```
dtparam=i2c_arm=on
dtparam=i2s=on
dtoverlay=googlevoicehat-soundcard   # works for INMP441 + MAX98357A on the pins above
```

**Done when:** `i2cdetect -y 1` shows the OLED (0x3c), and `arecord -l` / `aplay -l` list both the I2S card
and the USB card.

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
- Menu **Voice Chat** → *Join voice / Leave voice*, *Mode: Push-to-talk / Open mic*, *Groups* (list, join,
  leave), *Audio: Auto / Headset / Speaker*, *Volume*.
- Home screen shows a small mic icon (talking / muted / off) and the group name.

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
4. Volume per person = proximity: `1 - distance / 48` (0 if farther or other dimension), using `pos`; group
   members and Global Mic are full volume. Mix all received tracks to the output device.
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

Home screen (rotating every few seconds if idle):
```
 GALAXY CUBE        ◉ Wi-Fi
 Broadcast: ON  ● 3 online
 Voice: Steve  🎤  Group: —
```

Menu (turn = move, press = select, "◂ Back" item at the top of each list):
```
▸ Xbox Server Broadcast
▸ Nintendo Server Broadcast
▸ PlayStation Server Broadcast
▸ Stop Broadcast            (only while broadcasting)
▸ Voice Chat ▸ Join / Leave · Push-to-talk / Open mic · Groups · Audio · Volume
▸ Account ▸ Linked to Steve · Unlink this Cube · Pair again
▸ Settings ▸ Wi-Fi · Brightness · Screen timeout · About (version, CUBE-XXXX, IP)
```
Screen dims after 60 s idle and turns off after 5 min (OLEDs burn in); any input wakes it.

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

- ~70 × 70 × 70 mm cube, rounded corners (r = 8 mm), two parts: shell + base plate (4 × M2.5 screws into Pi standoffs).
- Front: window for the OLED (bezel 1 mm), knob below it. Top: TALK (big) and MUTE (small) buttons.
- Side: 3.5 mm/USB headset opening, micro-USB power opening. Grille holes for mic (front) and speaker (bottom, with feet).
- Print in dark PLA with a translucent purple/cyan "galaxy" strip or top for style; optional: an addressable LED
  behind it that glows when broadcasting/talking (extra $1, GPIO12).

---

## 14. Manual (what goes in the box)

1. Plug in the Cube. The screen says **Galaxy Cube**.
2. On your phone, join the Wi-Fi **CUBE-XXXX** shown on the screen. A page opens: pick your home Wi-Fi.
3. The Cube shows a code. Go to **cube.galaxymc.us**, sign in, and type the code.
4. Turn the knob to your console's **Server Broadcast** and press it. In Minecraft: **Play → Friends → LAN Games → GalaxySMP**.
5. Voice chat: plug in a headset (or use the built-in mic and speaker), choose **Voice Chat → Join**, hold **TALK** to speak.

Your console and the Cube must be on the same Wi-Fi.
