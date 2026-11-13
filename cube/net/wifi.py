"""nmcli helpers and the CUBE-XXXX setup hotspot. (Not implemented yet.)"""

from __future__ import annotations


def list_networks() -> list[dict]:
    """Return nearby Wi-Fi networks from `nmcli`."""
    raise NotImplementedError("Wi-Fi list — Coming soon")


def connect(ssid: str, password: str) -> None:
    raise NotImplementedError("Wi-Fi connect — Coming soon")


def start_hotspot(device_id: str) -> None:
    raise NotImplementedError("Setup hotspot — Coming soon")


def stop_hotspot() -> None:
    raise NotImplementedError("Stop hotspot — Coming soon")
