"""Console joining via BedrockConnect (Minecraft 26.60+ / NetherNet).

Phantom (RakNet LAN relay) does not work after Bedrock 26.60. The Cube runs a
local BedrockConnect instance with GalaxySMP in custom_servers.json instead.

Join (same Wi-Fi as the Cube):
  Xbox / PlayStation — Minecraft → Play → Friends → Worlds / LAN → BedrockConnect
                       → GalaxySMP
  Switch — set console DNS to the Cube's IP (shown on screen), then
           Servers → any featured server → GalaxySMP
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from typing import Optional

from cube import config

log = logging.getLogger("cube.broadcast")


class Broadcast:
    def __init__(self) -> None:
        self.running = False
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._supervise_task: Optional[asyncio.Task] = None

    async def start(self, host: str, port: int, name: str = "GalaxySMP") -> None:
        await self.stop()
        self._host = host
        self._port = port
        work = config.BEDROCK_CONNECT_DIR
        work.mkdir(parents=True, exist_ok=True)
        servers_path = work / "custom_servers.json"
        servers_path.write_text(
            json.dumps(
                [
                    {
                        "name": name,
                        "address": host,
                        "port": int(port),
                    }
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        config_path = work / "config.yml"
        config_path.write_text(
            "\n".join(
                [
                    "db_type: none",
                    "user_servers: false",
                    "featured_servers: false",
                    "fetch_featured_ips: false",
                    f"custom_servers: {servers_path}",
                    "net_mode: nethernet",
                    "port: 19132",
                    "webrtc_port: 19132",
                    "stun_discovery: false",
                    "kick_inactive: false",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        jar = config.BEDROCK_CONNECT_JAR
        if not jar.exists():
            raise FileNotFoundError(
                f"BedrockConnect jar missing at {jar}. Run setup/install.sh on the Pi."
            )

        java = os.environ.get("GALAXY_CUBE_JAVA", "java")
        # Pi Zero 2 W has 512 MB RAM — keep the heap small.
        cmd = [
            java,
            "-Xms64M",
            "-Xmx192M",
            "-jar",
            str(jar),
        ]
        log.info("Starting BedrockConnect → %s:%s", host, port)
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(work),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.running = True
        self._supervise_task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self.running = False
        if self._supervise_task is not None:
            self._supervise_task.cancel()
            try:
                await self._supervise_task
            except asyncio.CancelledError:
                pass
            self._supervise_task = None
        if self._proc is not None and self._proc.returncode is None:
            try:
                self._proc.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._proc.kill()
            except ProcessLookupError:
                pass
        self._proc = None

    async def _supervise(self) -> None:
        """Restart BedrockConnect if it exits while we still want it on."""
        while self.running:
            proc = self._proc
            if proc is None:
                return
            code = await proc.wait()
            if not self.running:
                return
            log.warning("BedrockConnect exited (%s); restarting in 2s", code)
            await asyncio.sleep(2)
            if self.running and self._host is not None and self._port is not None:
                try:
                    # Avoid recursive supervise tasks
                    self._supervise_task = None
                    await self.start(self._host, self._port)
                    return
                except Exception:
                    log.exception("BedrockConnect restart failed")
                    await asyncio.sleep(5)

    @property
    def status(self) -> str:
        return "on" if self.running else "off"
