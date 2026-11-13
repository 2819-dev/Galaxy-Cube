#!/usr/bin/env bash
# Pull the latest Galaxy Cube code and restart the service.
#   sudo bash setup/update.sh
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/galaxy-cube}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root:  sudo bash setup/update.sh"
  exit 1
fi

cd "${INSTALL_DIR}"
git pull --ff-only
systemctl restart galaxy-cube.service
echo "Updated and restarted."
systemctl --no-pager status galaxy-cube.service || true
