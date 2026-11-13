# Galaxy Cube

A small 3D-printed box that lets Xbox, Nintendo Switch and PlayStation players join **GalaxySMP** and use
GalaxySMP voice chat. Raspberry Pi Zero 2 W, a 128×64 OLED, a rotary knob and two voice buttons.

- **Full build guide:** [GALAXY_CUBE.md](GALAXY_CUBE.md) (parts, wiring, software, website API, case, manual)
- Link a Cube: **galaxymc.us/cube**
- Console join uses **BedrockConnect 1.72+** (Minecraft **26.60** / NetherNet). Phantom is not used.

## Run the screen simulator on your computer

You do **not** need a Pi for this. A window shows the same 128×64 screen the OLED will show.

```bash
cd galaxy-cube
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 -m cube.main --sim --skip-wifi
```

To also try the **Wi-Fi setup page** on your PC:

```bash
python3 -m cube.main --sim --force-wifi-setup --wifi-timeout 0
```

Then open the URL it prints (usually http://127.0.0.1:8765/), pick a fake network, and connect.

**Keys**

| Key | What it does |
|---|---|
| ↑ / ↓ (or ← / →) | Turn the knob |
| Enter (or Space) | Press the knob |
| T (hold) | TALK |
| M | MUTE |
| Esc or Q | Quit |

## Flash the SD card and run on the Pi

1. On your computer, use [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Choose **Raspberry Pi OS Lite (64-bit)** (Bookworm).
3. In Imager settings: set hostname, enable SSH, set a username/password, and (optional) prefill Wi-Fi.
4. Write the image to a 16 GB+ microSD card, put the card in the Pi Zero 2 W, plug in power.
5. SSH in (`ssh pi@<ip>` or the hostname you set).
6. Get this repo and install:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/2819-dev/Galaxy-Cube.git
cd Galaxy-Cube
sudo bash setup/install.sh
```

That installs Python packages, **Java 17**, **BedrockConnect**, and starts the `galaxy-cube` service.

### First-time Wi-Fi (no keyboard needed)

1. If the Cube has no Wi-Fi within ~20 seconds, the screen says **Wi-Fi setup**.
2. On your phone, join Wi-Fi **CUBE-XXXX** (password `galaxycube`).
3. A page should open (or go to http://10.42.0.1/). Pick your home Wi-Fi and type the password.
4. The Cube joins home Wi-Fi. Next comes pairing (later section).

**Settings → Wi-Fi** on the knob menu starts this again.

**Wire the screen and knob** (BCM pins — see GALAXY_CUBE.md §3):

| Part | Pi pins |
|---|---|
| OLED VCC / GND / SDA / SCL | 3.3V (1) / GND (6) / GPIO2 (3) / GPIO3 (5) |
| Encoder CLK / DT / SW / + / GND | GPIO17 (11) / GPIO27 (13) / GPIO22 (15) / 3.3V / GND |
| TALK button | GPIO5 (29) and GND |
| MUTE button | GPIO6 (31) and GND |

After install, reboot once so I2C/I2S are on. Check the OLED: `i2cdetect -y 1` should show `3c`.

```bash
systemctl status galaxy-cube
journalctl -u galaxy-cube -f
```
