"""nmcli helpers and the CUBE-XXXX setup hotspot.

On a real Pi this talks to NetworkManager. In simulator mode it fakes
networks so the setup page can be tried on a normal computer.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cube import config

log = logging.getLogger("cube.wifi")

HOTSPOT_PASSWORD = "galaxycube"
HOTSPOT_GATEWAY = "10.42.0.1"
DNSMASQ_DROPIN = Path("/etc/NetworkManager/dnsmasq-shared.d/galaxy-cube-captive.conf")

# Fake networks for the desktop simulator
_SIM_NETWORKS = [
    {"ssid": "HomeWifi", "signal": 88, "security": "WPA2"},
    {"ssid": "CafeGuest", "signal": 64, "security": "WPA2"},
    {"ssid": "GalaxyLab", "signal": 72, "security": "WPA3"},
    {"ssid": "OpenPark", "signal": 41, "security": ""},
]


@dataclass
class WifiStatus:
    connected: bool
    ssid: Optional[str] = None
    ip: Optional[str] = None
    hotspot: bool = False


class WifiManager:
    def __init__(self) -> None:
        self.hotspot_active = False
        self.hotspot_ssid: Optional[str] = None
        self._sim_connected_ssid: Optional[str] = None
        self._sim_ip = "192.168.1.50"
        self._use_sim = config.SIMULATOR or not shutil.which("nmcli")
        if self._use_sim:
            # Remember a previous sim connection across restarts of the process.
            saved = _load_sim_ssid()
            if saved:
                self._sim_connected_ssid = saved

    @property
    def simulator(self) -> bool:
        return self._use_sim

    def status(self) -> WifiStatus:
        if self._use_sim:
            if self.hotspot_active:
                return WifiStatus(connected=False, hotspot=True, ip=HOTSPOT_GATEWAY)
            if self._sim_connected_ssid:
                return WifiStatus(
                    connected=True,
                    ssid=self._sim_connected_ssid,
                    ip=self._sim_ip,
                )
            return WifiStatus(connected=False)

        if self.hotspot_active:
            return WifiStatus(connected=False, hotspot=True, ip=HOTSPOT_GATEWAY)

        ssid = self._nm_active_ssid()
        ip = self._nm_ipv4()
        return WifiStatus(connected=bool(ssid and ip), ssid=ssid, ip=ip)

    def is_connected(self) -> bool:
        st = self.status()
        return st.connected and not st.hotspot

    async def wait_for_connection(self, timeout_s: float = 20.0) -> bool:
        """Wait until home Wi-Fi is up (or timeout)."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.is_connected():
                return True
            await asyncio.sleep(1.0)
        return self.is_connected()

    def list_networks(self) -> list[dict]:
        if self._use_sim:
            return list(_SIM_NETWORKS)

        # Rescan (best effort), then list.
        self._run(["nmcli", "dev", "wifi", "rescan"], check=False)
        time.sleep(1.0)
        out = self._run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
            check=False,
        )
        networks: list[dict] = []
        seen: set[str] = set()
        for line in (out or "").splitlines():
            parts = line.split(":")
            if len(parts) < 3:
                continue
            # SSIDs can contain ":" — signal is second-to-last numeric-ish field
            # nmcli -t uses \: escapes; keep it simple: last two are SIGNAL, SECURITY
            security = parts[-1]
            signal_s = parts[-2]
            ssid = ":".join(parts[:-2]).replace("\\:", ":").strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal = int(signal_s)
            except ValueError:
                signal = 0
            networks.append({"ssid": ssid, "signal": signal, "security": security})
        networks.sort(key=lambda n: n["signal"], reverse=True)
        return networks

    def start_hotspot(self, device_id: str) -> None:
        ssid = device_id  # CUBE-XXXX
        self.hotspot_ssid = ssid
        if self._use_sim:
            self.hotspot_active = True
            log.info("SIM hotspot up: %s (password %s)", ssid, HOTSPOT_PASSWORD)
            return

        self._ensure_captive_dns_dropin()
        # Tear down any previous hotspot connection name we use.
        self._run(["nmcli", "connection", "down", "GalaxyCubeHotspot"], check=False)
        # Create / start hotspot. NetworkManager names it; we force a stable id.
        self._run(
            [
                "nmcli",
                "dev",
                "wifi",
                "hotspot",
                "ifname",
                "wlan0",
                "con-name",
                "GalaxyCubeHotspot",
                "ssid",
                ssid,
                "password",
                HOTSPOT_PASSWORD,
            ],
            check=True,
        )
        self.hotspot_active = True
        log.info("Hotspot up: %s", ssid)

    def stop_hotspot(self) -> None:
        if self._use_sim:
            self.hotspot_active = False
            self.hotspot_ssid = None
            return
        self._run(["nmcli", "connection", "down", "GalaxyCubeHotspot"], check=False)
        self._run(["nmcli", "connection", "delete", "GalaxyCubeHotspot"], check=False)
        self._remove_captive_dns_dropin()
        self.hotspot_active = False
        self.hotspot_ssid = None

    def connect(self, ssid: str, password: str = "") -> None:
        """Leave hotspot mode and join a home network."""
        if self._use_sim:
            self.hotspot_active = False
            self.hotspot_ssid = None
            self._sim_connected_ssid = ssid
            _save_sim_ssid(ssid)
            log.info("SIM connected to %s", ssid)
            return

        self.stop_hotspot()
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
        self._run(cmd, check=True)
        # Give DHCP a moment
        for _ in range(15):
            if self.is_connected():
                return
            time.sleep(1)
        if not self.is_connected():
            raise RuntimeError(f"Connected to {ssid} but no IP yet")

    def local_ip(self) -> str:
        st = self.status()
        return st.ip or "—"

    def _ensure_captive_dns_dropin(self) -> None:
        """Make NM's shared dnsmasq send every name to the portal gateway."""
        try:
            DNSMASQ_DROPIN.parent.mkdir(parents=True, exist_ok=True)
            DNSMASQ_DROPIN.write_text(
                "# Galaxy Cube captive portal — all DNS → setup page\n"
                f"address=/#/{HOTSPOT_GATEWAY}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("Could not write captive DNS drop-in: %s", exc)

    def _remove_captive_dns_dropin(self) -> None:
        try:
            if DNSMASQ_DROPIN.exists():
                DNSMASQ_DROPIN.unlink()
        except OSError:
            pass

    def _nm_active_ssid(self) -> Optional[str]:
        out = self._run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev", "status"],
            check=False,
        )
        for line in (out or "").splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            dev, typ, state, conn = parts[0], parts[1], parts[2], parts[3]
            if typ == "wifi" and state == "connected" and conn and conn != "GalaxyCubeHotspot":
                return conn
        # Fallback: general field
        out2 = self._run(
            ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "dev", "show", "wlan0"],
            check=False,
        )
        if out2 and ":" in out2:
            name = out2.split(":", 1)[1].strip()
            if name and name != "GalaxyCubeHotspot":
                return name
        return None

    def _nm_ipv4(self) -> Optional[str]:
        out = self._run(
            ["nmcli", "-t", "-f", "IP4.ADDRESS", "dev", "show", "wlan0"],
            check=False,
        )
        for line in (out or "").splitlines():
            if ":" not in line:
                continue
            val = line.split(":", 1)[1].strip()
            if val:
                return val.split("/")[0]
        return None

    @staticmethod
    def _run(cmd: list[str], check: bool = True) -> str:
        try:
            proc = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return (proc.stdout or "").strip()
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(err or f"Command failed: {' '.join(cmd)}") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("nmcli not found") from exc


def _sim_ssid_path() -> Path:
    config.ensure_state_dir()
    return config.STATE_DIR / "sim_wifi_ssid"


def _load_sim_ssid() -> Optional[str]:
    path = _sim_ssid_path()
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    return None


def _save_sim_ssid(ssid: str) -> None:
    try:
        _sim_ssid_path().write_text(ssid, encoding="utf-8")
    except OSError:
        pass
