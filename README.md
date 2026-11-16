# Galaxy Cube

A small 3D-printed box that lets Xbox, Nintendo Switch and PlayStation players join **GalaxySMP** and use
GalaxySMP voice chat. Raspberry Pi Zero 2 W, a 128×64 OLED, a rotary knob and two voice buttons.

- **Full build guide:** [GALAXY_CUBE.md](GALAXY_CUBE.md) (parts, wiring, software, website API, case, manual)
- Link a Cube: **galaxymc.us/cube**

## What works so far

| Part | Status |
|---|---|
| Boot screen, home screen, menus, settings (§9) | ✅ |
| Wi-Fi setup from a phone (§6) | ✅ |
| Linking to galaxymc.us with a code (§7) | ✅ |
| Console joining / Server Broadcast (§5) | ✅ |
| Install + auto-start on the Pi (§10) | ✅ |
| Voice chat (§8) | next |
| 3D-printed case files (§13) | later |

## Put it on the Cube

1. Flash **Raspberry Pi OS Lite (64-bit)** to the SD card with Raspberry Pi Imager (turn on SSH there).
2. Wire it up as in GALAXY_CUBE.md §3, put the SD card in and power it on.
3. Connect to it (`ssh pi@raspberrypi.local`) and run:

```bash
git clone https://github.com/2819-dev/Galaxy-Cube.git galaxy-cube
```

```bash
cd galaxy-cube && sudo bash setup/install.sh
```

```bash
sudo reboot
```

To get updates later: `sudo bash setup/update.sh`

## Try it on your phone

`simulator/` is a phone app that acts like the Cube: the screen, a knob you turn with your finger,
TALK and MUTE, plus pretend versions of the setup page, galaxymc.us/cube, a console and voice chat.
Open `simulator/index.html` from any web host and use **Share → Add to Home Screen** to install it.
It doesn't talk to the real website or a real console.

## Try it on a computer (no Pi needed)

```bash
pip install aiohttp pillow qrcode
```

```bash
python3 dev/mock_site.py
```

In a second window:

```bash
CUBE_FAKE=1 CUBE_API=http://localhost:8099 python3 -m cube.main
```

The screen is printed as text (and saved as `screen.png`). Type `u`/`d` + Enter to turn the knob,
just Enter to press it, `q` to quit. Open http://localhost:8099/dev/link to "link" the Cube.
