"""Galaxy Cube: starts everything (spec §4). Run on a computer with:  CUBE_FAKE=1 python3 -m cube.main"""
import asyncio
import logging
import sys

from . import config
from .api import Api, ApiError, Unlinked
from .broadcast import Broadcast
from .net import wifi
from .net.portal import Portal
from .ui.input import Input
from .ui.menu import CLOSE, Item, confirm, info, run_menu
from .ui.screen import Screen

log = config.log
DIM_AFTER = 60
CONSOLES = {"Xbox": "Xbox", "Nintendo": "Switch", "PlayStation": "PlayStation"}
TIMEOUTS = [60, 300, 600, 0]


class Quit(Exception):
    """Fake mode: you typed q."""


class App:
    def __init__(self):
        self.settings = config.load_settings()
        self.screen = Screen()
        self.screen.set_brightness(self.settings["brightness"])
        self.api = Api()
        self.broadcast = Broadcast()
        self.input = None
        self.me = self.settings.get("me")
        self.online = None   # None = still checking
        self.has_wifi = True
        self.keep_awake = False
        self.last_input = 0

    # ---------- events, screen sleep ----------

    async def next_event(self, timeout=None):
        """Wait for the knob (or `timeout` seconds -> None). Also dims / turns off the screen when idle."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout if timeout is not None else None
        while True:
            wait = 5 if deadline is None else max(0, min(5, deadline - loop.time()))
            event = await self.input.get(wait)
            now = loop.time()
            if event is None:
                self._idle(now)
                if deadline is not None and now >= deadline:
                    return None
                continue
            if event == "quit":
                raise Quit()
            self.last_input = now
            if event in ("talk_down", "talk_up", "mute", "mute_long"):
                continue  # voice chat buttons: handled once voice chat is added (spec §8)
            if self.screen.is_off or self.screen.is_dim:
                was_off = self.screen.is_off
                self.screen.on()
                if was_off:
                    return "wake"  # the first touch only wakes the screen; callers redraw
            return event

    def _idle(self, now):
        if self.keep_awake:
            return
        idle = now - self.last_input
        timeout = self.settings["screen_timeout"]
        if timeout and idle >= timeout:
            self.screen.off()
        elif idle >= DIM_AFTER:
            self.screen.dim()

    async def wait(self, seconds):
        """Sleep, but keep handling buttons (and q in fake mode)."""
        loop = asyncio.get_running_loop()
        end = loop.time() + seconds
        while loop.time() < end:
            await self.next_event(end - loop.time())

    def save(self):
        config.save_settings(self.settings)

    # ---------- start ----------

    async def run(self):
        self.input = Input()
        self.last_input = asyncio.get_running_loop().time()
        config.ensure_data_dir()
        await self.screen.boot_animation(asyncio.sleep)
        self.screen.text(["Connecting to Wi-Fi..."], title="Galaxy Cube")
        if not await wifi.wait_connected(config.WIFI_WAIT_SECONDS):
            await self.wifi_setup(can_cancel=False)
        while True:
            if not self.api.token:
                await self.pair()
            try:
                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(self.heartbeat())
                    tasks.create_task(self.home())
            except* Unlinked:
                log.info("This Cube was unlinked")
                self.api.set_token(None)
                self.broadcast.stop()
                self.me = self.settings["me"] = None
                self.settings["broadcast"] = False
                self.save()
                self.screen.text(["This Cube was", "unlinked from", "your account.", "", "Let's link it again."])
                await self.wait(3)

    # ---------- Wi-Fi setup (spec §6) ----------

    async def wifi_setup(self, can_cancel):
        ssid = config.device_id()
        error = ""
        self.keep_awake = True
        try:
            while True:
                self.screen.text(["Looking for Wi-Fi", "networks..."], title="Wi-Fi setup")
                networks = await wifi.scan()
                await wifi.start_hotspot(ssid)
                portal = Portal(networks, error)
                await portal.start()
                lines = ["On your phone, join", f"Wi-Fi: {ssid}", f"Password: {config.HOTSPOT_PASSWORD}",
                         "A setup page opens."]
                if can_cancel:
                    lines.append("Press knob to cancel")
                self.screen.text(lines, title="Wi-Fi setup")
                cancelled = False
                while not portal.chosen.done():
                    event = await self.next_event(1)
                    if event == "press" and can_cancel:
                        cancelled = True
                        break
                    if event:
                        self.screen.text(lines, title="Wi-Fi setup")
                await asyncio.sleep(1.5)  # let the "Connecting..." page reach the phone first
                await portal.stop()
                await wifi.stop_hotspot()
                if cancelled:
                    self.screen.text(["Reconnecting to your", "old Wi-Fi..."], title="Wi-Fi setup")
                    await wifi.wait_connected(20)
                    return
                name, password = portal.chosen.result()
                self.screen.text(["Connecting to", name[:20] + "..."], title="Wi-Fi setup")
                ok, message = await wifi.connect(name, password)
                if ok and await wifi.wait_connected(15):
                    self.screen.text(["Connected to", name[:20], "", "All set!"], title="Wi-Fi setup")
                    await asyncio.sleep(2)
                    return
                error = f"{message or 'Could not connect'} for {name}. Try again."
                self.screen.text([message or "Couldn't connect.", "Join the CUBE Wi-Fi", "again on your phone."],
                                 title="Wi-Fi setup")
                await self.wait(4)
        finally:
            self.keep_awake = False

    # ---------- pairing (spec §7) ----------

    async def pair(self):
        self.keep_awake = True
        retry = 1
        try:
            while True:
                try:
                    start = await self.api.pair_start()
                except ApiError as e:
                    self.screen.text([str(e)[:21], "", f"Trying again in {retry}s"], title="Link your Cube")
                    await self.wait(retry)
                    retry = min(retry * 2, 30)
                    continue
                retry = 1
                code, poll_token = start["code"], start["pollToken"]
                url = start.get("url") or "galaxymc.us/cube"
                self.screen.big(code, f"Go to {url}", ["and type this code."])
                log.info("Pairing code ready")
                while True:
                    await self.wait(config.POLL_SECONDS)
                    try:
                        result = await self.api.pair_poll(poll_token)
                    except ApiError as e:
                        if e.status == 0:
                            continue      # no internet for a moment, keep the same code
                        break             # code unknown or expired: get a new one
                    status = result.get("status")
                    if status == "linked":
                        self.api.set_token(result["deviceToken"])
                        name = result.get("username") or "you"
                        log.info("Linked to %s", name)
                        self.screen.text(["", "Linked to", f"{name}!"], title="Galaxy Cube")
                        await self.wait(2)
                        return
                    if status == "expired":
                        break
        finally:
            self.keep_awake = False

    # ---------- staying linked: /api/cube/me (spec §7) ----------

    async def heartbeat(self):
        self.apply_broadcast()  # turn the broadcast back on after a restart, even before the website answers
        while True:
            try:
                me = await self.api.me()
                self.me = me
                self.online = True
                if me != self.settings.get("me"):
                    self.settings["me"] = me
                    self.save()
                self.apply_broadcast()
                wait = config.HEARTBEAT_SECONDS
            except ApiError as e:
                log.warning("galaxymc.us: %s", e)
                self.online = False
                wait = 30
            self.has_wifi = await wifi.connected()
            await asyncio.sleep(wait)

    def server(self):
        server = (self.me or {}).get("server") or {}
        if server.get("host") and server.get("port"):
            return server["host"], int(server["port"])
        return None

    def apply_broadcast(self):
        """Keep Phantom running (and pointed at the right server) while the broadcast is turned on."""
        server = self.server()
        if self.settings["broadcast"] and server:
            self.broadcast.start(*server)

    # ---------- home screen + menus (spec §9) ----------

    def draw_home(self):
        user = ((self.me or {}).get("user") or {}).get("username") or "-"
        if self.online is None:
            status = "Checking..."
        elif self.online:
            status = "Online"
        else:
            status = "No Wi-Fi" if not self.has_wifi else "Offline"
        self.screen.text([
            f"Account: {user}"[:21],
            "Broadcast: " + ("ON  *" if self.broadcast.on else "off"),
            "Voice: next update",
            f"Status: {status}",
            "Press for menu",
        ], title="GALAXY CUBE")

    async def home(self):
        while True:
            self.draw_home()
            if await self.next_event(5) == "press":
                await run_menu(self, "Menu", self.main_menu)

    def main_menu(self):
        items = [Item(f"{name} Broadcast", lambda c=console: self.start_broadcast(c))
                 for name, console in CONSOLES.items()]
        if self.broadcast.on:
            items.append(Item("Stop Broadcast", self.stop_broadcast))
        items += [
            Item("Voice Chat", lambda: info(self, "Voice Chat", ["Voice chat is coming", "in the next update."])),
            Item("Account", submenu=self.account_menu),
            Item("Settings", submenu=self.settings_menu),
        ]
        return items

    async def start_broadcast(self, console):
        server = self.server()
        if not server:
            await info(self, "Broadcast", ["Can't reach", "galaxymc.us yet.", "Try again soon."])
            return
        self.settings["broadcast"] = True
        self.save()
        self.broadcast.start(*server)
        await info(self, "Broadcasting!", [f"On your {console}:", "Minecraft > Play >", "Friends > LAN Games",
                                           "> GalaxySMP"])
        return CLOSE

    async def stop_broadcast(self):
        self.broadcast.stop()
        self.settings["broadcast"] = False
        self.save()
        return CLOSE

    def account_menu(self):
        user = ((self.me or {}).get("user") or {}).get("username") or "-"
        return "Account", [
            Item(f"Linked to {user}"[:21], lambda: info(self, "Account", [
                f"Linked to {user}"[:21], "Rename or unlink at", "galaxymc.us/cube"])),
            Item("Unlink this Cube", self.unlink),
            Item("Pair again", self.unlink),
        ]

    async def unlink(self):
        if not await confirm(self, "Unlink this Cube?"):
            return None
        await info(self, "Unlinked", ["Also remove it at", "galaxymc.us/cube", "if you won't use it."])
        raise Unlinked()

    def settings_menu(self):
        timeout = self.settings["screen_timeout"]
        timeout_label = "Never" if not timeout else f"{timeout // 60} min"
        return "Settings", [
            Item("Wi-Fi", self.change_wifi),
            Item(f"Brightness: {self.settings['brightness']}", self.next_brightness),
            Item(f"Screen off: {timeout_label}", self.next_timeout),
            Item("About", lambda: info(self, "About", [
                f"Version {config.VERSION}", config.device_id(), f"IP {wifi.ip_address()}"])),
        ]

    async def change_wifi(self):
        if await confirm(self, "Change Wi-Fi?"):
            await self.wifi_setup(can_cancel=True)
            return CLOSE

    async def next_brightness(self):
        order = ["Low", "Medium", "High"]
        name = order[(order.index(self.settings["brightness"]) + 1) % 3]
        self.settings["brightness"] = name
        self.screen.set_brightness(name)
        self.save()

    async def next_timeout(self):
        current = self.settings["screen_timeout"]
        index = TIMEOUTS.index(current) if current in TIMEOUTS else 0
        self.settings["screen_timeout"] = TIMEOUTS[(index + 1) % len(TIMEOUTS)]
        self.save()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stderr)
    app = App()

    async def run():
        try:
            await app.run()
        finally:
            app.broadcast.stop()
            await app.api.close()

    try:
        try:
            asyncio.run(run())
        except* Quit:
            print("Bye!")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
