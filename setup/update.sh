#!/bin/bash
# Gets the newest Cube code and restarts it:  sudo bash setup/update.sh
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
git pull --ff-only
/opt/galaxy-cube/venv/bin/pip install -q -r requirements.txt
systemctl restart galaxy-cube.service
echo "Updated and restarted."
