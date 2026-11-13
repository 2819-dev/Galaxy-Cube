"""Device identity, API base URL, and on-disk paths.

Token is stored only at TOKEN_PATH (chmod 600). Never log or print it.
"""

from __future__ import annotations

import os
from pathlib import Path

FIRMWARE_VERSION = "1.0.0"
API_BASE = "https://galaxymc.us"
MODEL = "cube"

# On the Pi: /var/lib/galaxy-cube. For the desktop simulator: ./data under the repo.
_DEFAULT_STATE = Path("/var/lib/galaxy-cube")
_SIM_STATE = Path(__file__).resolve().parent.parent / "data"

STATE_DIR = Path(os.environ.get("GALAXY_CUBE_STATE", str(
    _DEFAULT_STATE if _DEFAULT_STATE.parent.exists() and os.access(_DEFAULT_STATE.parent, os.W_OK)
    else _SIM_STATE
)))
TOKEN_PATH = STATE_DIR / "token"
SETTINGS_PATH = STATE_DIR / "settings.json"

# BedrockConnect (Minecraft 26.60+ / NetherNet). Phantom no longer works.
_INSTALL_ROOT = Path(os.environ.get("GALAXY_CUBE_HOME", "/opt/galaxy-cube"))
BEDROCK_CONNECT_DIR = Path(os.environ.get(
    "GALAXY_CUBE_BC_DIR",
    str(_INSTALL_ROOT / "bedrock-connect"),
))
BEDROCK_CONNECT_JAR = Path(os.environ.get(
    "GALAXY_CUBE_BC_JAR",
    str(BEDROCK_CONNECT_DIR / "BedrockConnect-1.0-SNAPSHOT.jar"),
))
# Kept for older docs/scripts; unused at runtime.
PHANTOM_PATH = Path(os.environ.get(
    "GALAXY_CUBE_PHANTOM",
    str(_INSTALL_ROOT / "phantom-linux-arm8"),
))

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64
SCREEN_IDLE_DIM_S = 60
SCREEN_IDLE_OFF_S = 300

# True when not running on a Raspberry Pi (desktop simulator).
SIMULATOR = os.environ.get("GALAXY_CUBE_SIM", "").lower() in ("1", "true", "yes") or (
    not Path("/proc/device-tree/model").exists()
    and os.environ.get("GALAXY_CUBE_FORCE_HW", "").lower() not in ("1", "true", "yes")
)


def device_id() -> str:
    """CUBE-XXXX from the Pi serial (last 4 hex digits), or CUBE-SIMU in simulator."""
    if SIMULATOR and not Path("/proc/cpuinfo").exists():
        return "CUBE-SIMU"
    try:
        serial = ""
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Serial"):
                    serial = line.split(":")[-1].strip()
                    break
        if serial:
            return f"CUBE-{serial[-4:].upper()}"
    except OSError:
        pass
    return "CUBE-SIMU"


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(STATE_DIR, 0o700)
    except OSError:
        pass
