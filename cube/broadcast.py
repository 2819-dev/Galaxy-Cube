"""Server Broadcast (spec §5): runs Phantom so consoles see GalaxySMP under LAN Games."""
import asyncio

from . import config

log = config.log


class Broadcast:
    def __init__(self):
        self.task = None
        self.host = None
        self.port = None

    @property
    def on(self):
        return self.task is not None and not self.task.done()

    def start(self, host, port):
        if self.on and (host, port) == (self.host, self.port):
            return
        self.stop()
        self.host, self.port = host, port
        self.task = asyncio.create_task(self._run())

    def stop(self):
        if self.task:
            self.task.cancel()
        self.task = None

    async def _run(self):
        cmd = [config.PHANTOM, "-server", f"{self.host}:{self.port}", "-bind", "0.0.0.0", "-bind_port", "19132"]
        wait = 1
        while True:
            if config.FAKE:
                log.info("[fake] would run: %s", " ".join(cmd))
                await asyncio.Future()  # pretend it runs until stopped
            proc = None
            try:
                log.info("Starting broadcast to %s:%s", self.host, self.port)
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await proc.wait()
                log.warning("Phantom stopped (code %s), restarting in %ss", proc.returncode, wait)
            except FileNotFoundError:
                log.error("Phantom is missing at %s. Run setup/install.sh.", config.PHANTOM)
            except asyncio.CancelledError:
                if proc and proc.returncode is None:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), 3)
                    except asyncio.TimeoutError:
                        proc.kill()
                log.info("Broadcast stopped")
                raise
            await asyncio.sleep(wait)
            wait = min(wait * 2, 30)
