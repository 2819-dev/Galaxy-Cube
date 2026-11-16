"""Wi-Fi with NetworkManager (nmcli), and the CUBE-XXXX setup hotspot (spec §6).

Fake mode: pretends Wi-Fi works. Set CUBE_FAKE_WIFI=setup to test the setup page instead.
"""
import asyncio
import os
import socket

from .. import config

log = config.log
HOTSPOT = "cube-setup"   # name of the hotspot connection in NetworkManager
_fake_connected = os.environ.get("CUBE_FAKE_WIFI") != "setup"


async def _nmcli(*args, timeout=40):
    """Run nmcli and return (ok, output). Never logs arguments (they can contain a Wi-Fi password)."""
    proc = await asyncio.create_subprocess_exec(
        "nmcli", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return False, "timed out"
    return proc.returncode == 0, out.decode(errors="replace").strip()


async def connected():
    """True when we're on a normal Wi-Fi network (not our own hotspot)."""
    if config.FAKE:
        return _fake_connected
    ok, out = await _nmcli("-t", "-f", "NAME,TYPE", "con", "show", "--active")
    if not ok:
        return False
    for line in out.splitlines():
        name, _, kind = line.rpartition(":")
        if kind == "802-11-wireless" and name != HOTSPOT:
            return True
    return False


async def wait_connected(seconds):
    for _ in range(seconds):
        if await connected():
            return True
        await asyncio.sleep(1)
    return False


async def scan():
    """Nearby networks as a list of {ssid, signal, secure}, strongest first."""
    if config.FAKE:
        return [{"ssid": "Home Wi-Fi", "signal": 80, "secure": True},
                {"ssid": "Neighbor 5G", "signal": 40, "secure": True},
                {"ssid": "Cafe", "signal": 25, "secure": False}]
    await _nmcli("dev", "wifi", "rescan")
    await asyncio.sleep(2)
    ok, out = await _nmcli("-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list")
    nets = {}
    for line in out.splitlines() if ok else []:
        parts = line.replace("\\:", "\0").split(":")
        if len(parts) < 3:
            continue
        ssid, signal, security = (p.replace("\0", ":") for p in parts[:3])
        if not ssid or ssid.startswith("CUBE-"):
            continue
        signal = int(signal or 0)
        if ssid not in nets or nets[ssid]["signal"] < signal:
            nets[ssid] = {"ssid": ssid, "signal": signal, "secure": security not in ("", "--")}
    return sorted(nets.values(), key=lambda n: -n["signal"])


async def start_hotspot(ssid):
    if config.FAKE:
        log.info("[fake] would start hotspot %s", ssid)
        return
    await _nmcli("con", "delete", HOTSPOT)
    ok, out = await _nmcli("dev", "wifi", "hotspot", "ifname", "wlan0", "con-name", HOTSPOT,
                           "ssid", ssid, "password", config.HOTSPOT_PASSWORD)
    if not ok:
        log.error("Hotspot failed: %s", out)


async def stop_hotspot():
    if config.FAKE:
        log.info("[fake] would stop hotspot")
        return
    await _nmcli("con", "down", HOTSPOT)


async def connect(ssid, password):
    """Join a network and save it. Returns (ok, message)."""
    global _fake_connected
    if config.FAKE:
        log.info("[fake] would connect to %s", ssid)
        _fake_connected = password != "wrong"
        return _fake_connected, "" if _fake_connected else "Wrong password"
    args = ["dev", "wifi", "connect", ssid, "ifname", "wlan0"]
    if password:
        args += ["password", password]
    ok, out = await _nmcli(*args, timeout=45)
    if not ok:
        log.warning("Wi-Fi connect to %s failed", ssid)
        if "Secrets were required" in out or "password" in out.lower():
            return False, "Wrong password"
        return False, "Couldn't join that Wi-Fi"
    return True, ""


def ip_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "-"
