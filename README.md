# Galaxy Cube

A small 3D-printed box that lets Xbox, Nintendo Switch and PlayStation players join **GalaxySMP** and use
GalaxySMP voice chat. Raspberry Pi Zero 2 W, a 128×64 OLED, a rotary knob and two voice buttons.

- **Full build guide:** [GALAXY_CUBE.md](GALAXY_CUBE.md) (parts, wiring, software, website API, case, manual)
- Link a Cube: **galaxymc.us/cube**

## Run the screen simulator on your computer

You do **not** need a Pi for this. A window shows the same 128×64 screen the OLED will show.

```bash
cd galaxy-cube
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 -m cube.main --sim
```

**Keys**

| Key | What it does |
|---|---|
| ↑ / ↓ (or ← / →) | Turn the knob |
| Enter (or Space) | Press the knob |
| T (hold) | TALK |
| M | MUTE |
| Esc or Q | Quit |

You should see a short star animation, then **Galaxy Cube**, then the home screen. Press Enter to open the menu.

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
git clone https://github.com/<your-repo>/galaxy-cube.git
cd galaxy-cube
sudo bash setup/install.sh
```

That installs Python packages, downloads **Phantom** for ARM64, and starts the `galaxy-cube` systemd service.

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
