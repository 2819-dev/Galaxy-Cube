"""Settings, paths and the device id. Set CUBE_FAKE=1 to run on a normal computer."""
import json
import logging
import os
import tempfile
from pathlib import Path

FAKE = os.environ.get("CUBE_FAKE") == "1"
VERSION = "1.0.0"
MODEL = "cube"

API_BASE = os.environ.get("CUBE_API", "https://galaxymc.us").rstrip("/")
DATA_DIR = Path(os.environ.get("CUBE_DATA")
                or (Path(tempfile.gettempdir()) / "galaxy-cube" if FAKE else "/var/lib/galaxy-cube"))
TOKEN_FILE = DATA_DIR / "token"
SETTINGS_FILE = DATA_DIR / "settings.json"
PHANTOM = os.environ.get("CUBE_PHANTOM", "/opt/galaxy-cube/phantom-linux-arm8")

HOTSPOT_PASSWORD = "galaxycube"
WIFI_WAIT_SECONDS = 20
HEARTBEAT_SECONDS = int(os.environ.get("CUBE_HEARTBEAT", "120"))  # lower it only for testing
POLL_SECONDS = 3

DEFAULT_SETTINGS = {
    "brightness": "High",       # Low / Medium / High
    "screen_timeout": 300,      # seconds until the screen turns off, 0 = never
    "broadcast": False,         # was the broadcast on when the Cube was turned off?
    "me": None,                 # last /api/cube/me answer (no secrets in it)
}

log = logging.getLogger("cube")


def device_id():
    """CUBE-XXXX, from the last 4 hex digits of the Pi's serial number."""
    if os.environ.get("CUBE_DEVICE_ID"):
        return os.environ["CUBE_DEVICE_ID"]
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("Serial"):
                return "CUBE-" + line.split(":")[1].strip()[-4:].upper()
    except OSError:
        pass
    return "CUBE-F00D"


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(DATA_DIR, 0o700)
    except OSError:
        pass


# ---- device token (never log or print it) ----

def load_token():
    try:
        return TOKEN_FILE.read_text().strip() or None
    except OSError:
        return None


def save_token(token):
    ensure_data_dir()
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    os.chmod(TOKEN_FILE, 0o600)


def delete_token():
    try:
        TOKEN_FILE.unlink()
    except FileNotFoundError:
        pass


# ---- settings ----

def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        settings.update(json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    ensure_data_dir()
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=1))
    tmp.replace(SETTINGS_FILE)  # replace in one step so a power cut can't leave half a file
