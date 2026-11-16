#!/bin/bash
# Installs everything the Galaxy Cube needs on a fresh Raspberry Pi OS Lite (64-bit, Bookworm).
# Run it from the repo folder:  sudo bash setup/install.sh
set -e
if [ "$EUID" -ne 0 ]; then echo "Please run with sudo:  sudo bash setup/install.sh"; exit 1; fi
DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "== Galaxy Cube install (repo: $DIR) =="

echo "-- System packages"
apt-get update
apt-get install -y python3-venv python3-pip python3-gpiozero python3-lgpio python3-pil python3-numpy \
  libopenjp2-7 libportaudio2 alsa-utils i2c-tools git curl

echo "-- Python packages"
mkdir -p /opt/galaxy-cube
python3 -m venv --system-site-packages /opt/galaxy-cube/venv
/opt/galaxy-cube/venv/bin/pip install -r "$DIR/requirements.txt"

echo "-- Phantom (lets consoles see GalaxySMP under LAN Games)"
curl -fL -o /opt/galaxy-cube/phantom-linux-arm8 \
  https://github.com/jhead/phantom/releases/latest/download/phantom-linux-arm8
chmod +x /opt/galaxy-cube/phantom-linux-arm8

echo "-- Screen (I2C) and sound (I2S)"
CFG=/boot/firmware/config.txt
for line in "dtparam=i2c_arm=on" "dtparam=i2s=on" "dtoverlay=googlevoicehat-soundcard"; do
  grep -qxF "$line" "$CFG" || echo "$line" >> "$CFG"
done
grep -qxF "i2c-dev" /etc/modules || echo "i2c-dev" >> /etc/modules

echo "-- Setup page opens by itself on phones (captive portal)"
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
echo "address=/#/10.42.0.1" > /etc/NetworkManager/dnsmasq-shared.d/galaxy-cube.conf

echo "-- Data folder"
mkdir -p /var/lib/galaxy-cube
chmod 700 /var/lib/galaxy-cube

echo "-- Start the Cube on every boot"
sed "s|@DIR@|$DIR|" "$DIR/systemd/galaxy-cube.service" > /etc/systemd/system/galaxy-cube.service
systemctl daemon-reload
systemctl enable galaxy-cube.service

echo
echo "Done! Restart the Cube with:  sudo reboot"
echo "After that, the screen should show Galaxy Cube."
echo "Check the hardware any time with:  sudo bash setup/check.sh"
