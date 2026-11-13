"""Starts/stops the Phantom binary for console LAN joining. (Not implemented yet.)"""

from __future__ import annotations


class Broadcast:
    def __init__(self) -> None:
        self.running = False

    async def start(self, host: str, port: int) -> None:
        raise NotImplementedError("Phantom start — Coming soon")

    async def stop(self) -> None:
        raise NotImplementedError("Phantom stop — Coming soon")

    @property
    def status(self) -> str:
        return "on" if self.running else "off"
