"""galaxymc.us API: pairing and /api/cube/me (spec §7). Only the endpoints that exist on the website."""
import asyncio

import aiohttp

from . import config


class ApiError(Exception):
    """Something went wrong. The message is safe to show on the screen. status 0 = no connection."""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class Unlinked(Exception):
    """The owner unlinked this Cube (website answered 401)."""


class Api:
    def __init__(self):
        self.session = None
        self.token = config.load_token()

    async def _request(self, method, path, body=None, auth=False):
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        headers = {"X-Cube-Firmware": config.VERSION}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            async with self.session.request(method, config.API_BASE + path, json=body, headers=headers) as r:
                try:
                    data = await r.json(content_type=None)
                except ValueError:
                    data = {}
                if not isinstance(data, dict):
                    data = {}
                if r.status == 401 and auth:
                    raise Unlinked()
                if r.status >= 400 or data.get("ok") is False:
                    raise ApiError(data.get("error") or f"Website error {r.status}", r.status)
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ApiError("Can't reach galaxymc.us")

    async def pair_start(self):
        return await self._request("POST", "/api/cube/pair/start",
                                   {"deviceId": config.device_id(), "model": config.MODEL})

    async def pair_poll(self, poll_token):
        return await self._request("POST", "/api/cube/pair/poll", {"pollToken": poll_token})

    async def me(self):
        return await self._request("GET", "/api/cube/me", auth=True)

    def set_token(self, token):
        self.token = token
        if token:
            config.save_token(token)
        else:
            config.delete_token()

    async def close(self):
        if self.session:
            await self.session.close()
