"""galaxymc.us Cube API — pairing and /me heartbeat. (Not implemented yet.)

Uses only the live endpoints in GALAXY_CUBE.md §7. Never log the device token.
"""

from __future__ import annotations

from typing import Any, Optional


async def pair_start(device_id: str) -> dict[str, Any]:
    raise NotImplementedError("Pair start — Coming soon")


async def pair_poll(poll_token: str) -> dict[str, Any]:
    raise NotImplementedError("Pair poll — Coming soon")


async def me(device_token: str) -> dict[str, Any]:
    raise NotImplementedError("/api/cube/me — Coming soon")


def load_token() -> Optional[str]:
    raise NotImplementedError("Load token — Coming soon")


def save_token(token: str) -> None:
    raise NotImplementedError("Save token — Coming soon")


def clear_token() -> None:
    raise NotImplementedError("Clear token — Coming soon")
