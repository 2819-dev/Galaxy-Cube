"""Voice WebSocket + WebRTC (aiortc). (Not implemented yet.)

Endpoint: wss://galaxymc.us/api/cube/voice with Authorization: Bearer <deviceToken>.
"""

from __future__ import annotations


class VoiceClient:
    def __init__(self) -> None:
        self.connected = False

    async def connect(self, url: str, device_token: str) -> None:
        raise NotImplementedError("Voice connect — Coming soon")

    async def disconnect(self) -> None:
        raise NotImplementedError("Voice disconnect — Coming soon")

    async def set_talking(self, talking: bool) -> None:
        raise NotImplementedError("Voice talking state — Coming soon")
