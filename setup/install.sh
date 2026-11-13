#!/usr/bin/env bash
# Install Galaxy Cube on a Raspberry Pi Zero 2 W (64-bit Bookworm).
# Run as root (or with sudo) from the repo root, or pass the repo path:
#   sudo bash setup/install.sh
#   sudo bash setup/install.sh /home/pi/galaxy-cube
set -euo pipefail

REPO_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
INSTALL_DIR="/opt/galaxy-cube"
STATE_DIR="/var/lib/galaxy-cube"
PHANTOM_VERSION="${PHANTOM_VERSION:-0.5.4}"
PHANTOM_URL="https://github.com/jhead/phantom/releases/download/v${PHANTOM_VERSION}/phantom-linux-arm8"
SERVICE_SRC="${REPO_DIR}/systemd/galaxy-cube.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root:  sudo bash setup/install.sh"
  exit 1
fi

echo "==> Galaxy Cube install"
echo "    repo:    ${REPO_DIR}"
echo "    install: ${INSTALL_DIR}"

echo "==> Apt packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-pil \
  python3-numpy \
  git \
  curl \
  ca-certificates \
  i2c-tools \
  libportaudio2 \
  network-manager

echo "==> Enable I2C (and remind about I2S in config.txt)"
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_i2c 0 || true
fi
CFG="/boot/firmware/config.txt"
if [[ -f "${CFG}" ]]; then
  grep -q '^dtparam=i2c_arm=on' "${CFG}" || echo 'dtparam=i2c_arm=on' >> "${CFG}"
  grep -q '^dtparam=i2s=on' "${CFG}" || echo 'dtparam=i2s=on' >> "${CFG}"
  grep -q 'googlevoicehat-soundcard' "${CFG}" || \
    echo 'dtoverlay=googlevoicehat-soundcard' >> "${CFG}"
fi

echo "==> Copy software to ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude 'data' \
  "${REPO_DIR}/" "${INSTALL_DIR}/"

echo "==> Python packages (system / break-system-packages for Lite)"
python3 -m pip install --break-system-packages -r "${INSTALL_DIR}/requirements.txt"

echo "==> Download Phantom (ARM64) ${PHANTOM_VERSION}"
curl -fsSL -o "${INSTALL_DIR}/phantom-linux-arm8" "${PHANTOM_URL}"
chmod +x "${INSTALL_DIR}/phantom-linux-arm8"

echo "==> State directory ${STATE_DIR}"
mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"
# token file is created later at pair time (chmod 600)

echo "==> systemd service"
install -m 644 "${SERVICE_SRC}" /etc/systemd/system/galaxy-cube.service
systemctl daemon-reload
systemctl enable galaxy-cube.service
systemctl restart galaxy-cube.service || systemctl start galaxy-cube.service

echo
echo "Done."
echo "  Service:  systemctl status galaxy-cube"
echo "  Logs:     journalctl -u galaxy-cube -f"
echo "  OLED:     i2cdetect -y 1   (should show 3c)"
echo "  Reboot once if this was the first time enabling I2C/I2S."
