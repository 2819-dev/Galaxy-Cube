"""Picks headset vs built-in I2S, mixing, volume. (Not implemented yet.)"""

from __future__ import annotations


def pick_devices(mode: str = "auto") -> tuple[str | None, str | None]:
    """Return (input_device, output_device) names."""
    raise NotImplementedError("Audio devices — Coming soon")
