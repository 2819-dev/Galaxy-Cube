#!/usr/bin/env python3
"""Galaxy Cube — one asyncio process.

Boot → (Wi-Fi setup if needed) → UI. Pairing, BedrockConnect broadcast and
voice plug in here in later sections.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from cube import config
from cube.net.portal import SetupPortal
from cube.net.wifi import WifiManager
from cube.ui.input import Event, Input
from cube.ui.menu import UI, UiState
from cube.ui.screen import Screen

log = logging.getLogger("cube")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Galaxy Cube")
    p.add_argument(
        "--sim",
        action="store_true",
        help="Force desktop simulator (pygame window + keyboard)",
    )
    p.add_argument(
        "--skip-boot",
        action="store_true",
        help="Skip the star-burst boot animation",
    )
    p.add_argument(
        "--scale",
        type=int,
        default=8,
        help="Simulator pixel scale (default 8 → 1024×512 window)",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Draw boot + menus once and exit (for automated checks)",
    )
    p.add_argument(
        "--force-wifi-setup",
        action="store_true",
        help="Always open the Wi-Fi hotspot setup flow",
    )
    p.add_argument(
        "--skip-wifi",
        action="store_true",
        help="Skip the Wi-Fi wait/setup on boot",
    )
    p.add_argument(
        "--wifi-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for saved Wi-Fi before starting hotspot (default 20)",
    )
    return p.parse_args(argv)


class App:
    def __init__(self, scale: int = 8) -> None:
        self.wifi = WifiManager()
        self.screen = Screen(scale=scale)
        self.inp = Input()
        st = self.wifi.status()
        self.state = UiState(
            device_id=config.device_id(),
            wifi_ok=st.connected,
            linked_user=None,
            voice_user="—",
            voice_group="—",
            ip=st.ip or ("127.0.0.1" if config.SIMULATOR else "—"),
            wifi_ssid=st.ssid,
        )
        self._wifi_setup_requested = False
        self.ui = UI(self.screen, self.inp, self.state, on_action=self._on_menu_action)
        self.portal: SetupPortal | None = None

    def _on_menu_action(self, action: str) -> None:
        if action == "settings_wifi":
            self._wifi_setup_requested = True

    def _sync_wifi_state(self) -> None:
        st = self.wifi.status()
        self.state.wifi_ok = st.connected
        self.state.ip = st.ip or self.state.ip
        if st.ssid:
            self.state.wifi_ssid = st.ssid

    async def run_wifi_setup(self) -> bool:
        """Hotspot + captive portal until the phone saves home Wi-Fi."""
        device_id = self.state.device_id
        self.state.mode = "wifi_setup"
        self.state.portal_url = (
            "http://127.0.0.1:8765/" if self.wifi.simulator else "http://10.42.0.1/"
        )
        self.ui.close_menu()
        self.ui.wake()
        self.ui.draw()

        await asyncio.to_thread(self.wifi.start_hotspot, device_id)

        async def on_connect(ssid: str, password: str) -> None:
            self.state.mode = "wifi_connecting"
            self.state.wifi_ssid = ssid
            self.ui.draw()
            await asyncio.to_thread(self.wifi.connect, ssid, password)

        portal = SetupPortal(self.wifi, device_id, on_connect=on_connect)
        self.portal = portal
        url = await portal.start()
        self.state.portal_url = url
        log.info("Wi-Fi setup portal at %s", url)
        if self.wifi.simulator:
            print(f"  Setup page: {url}")
            print(f"  Join hotspot SSID {device_id} / password galaxycube (simulated)")

        # Pump UI until the portal signals done (or user quits).
        while self.ui.running and not portal.done.is_set():
            for ev in self.inp.poll():
                self.ui.handle(ev)
            self.ui.draw()
            try:
                await asyncio.wait_for(portal.done.wait(), timeout=1 / 30)
            except asyncio.TimeoutError:
                pass

        await portal.stop()
        self.portal = None
        self._sync_wifi_state()
        self.state.mode = "home"
        ok = self.wifi.is_connected()
        if ok:
            self.ui._show_flash(f"On {self.state.wifi_ssid or 'Wi-Fi'}", 1.6)
        else:
            self.ui._show_flash("Wi-Fi failed", 1.6)
        return ok

    async def maybe_wifi_on_boot(self, timeout_s: float, force: bool) -> None:
        if force:
            await self.run_wifi_setup()
            return
        self.state.mode = "home"
        self.ui._show_flash("Checking Wi-Fi…", 1.0)
        self.ui.draw()
        ok = await self.wifi.wait_for_connection(timeout_s)
        self._sync_wifi_state()
        if not ok:
            await self.run_wifi_setup()
        else:
            log.info("Wi-Fi OK: %s (%s)", self.state.wifi_ssid, self.state.ip)

    async def run(
        self,
        skip_boot: bool = False,
        smoke: bool = False,
        skip_wifi: bool = False,
        force_wifi: bool = False,
        wifi_timeout: float = 20.0,
    ) -> None:
        config.ensure_state_dir()
        print("Galaxy Cube starting")
        print(f"  mode: {'SIMULATOR' if config.SIMULATOR else 'hardware'}")
        print(f"  device id: {self.state.device_id}")
        if config.SIMULATOR and not smoke:
            print("  keys: ↑↓ scroll  Enter select  T talk  M mute  Esc quit")

        try:
            if not skip_boot:
                await asyncio.to_thread(self.ui.run_boot)
            self.ui.wake()
            self.ui.draw()

            if smoke:
                await self._smoke()
                return

            if not skip_wifi:
                await self.maybe_wifi_on_boot(wifi_timeout, force_wifi)

            while self.ui.running:
                if self._wifi_setup_requested:
                    self._wifi_setup_requested = False
                    await self.run_wifi_setup()
                    continue
                for ev in self.inp.poll():
                    self.ui.handle(ev)
                self._sync_wifi_state()
                self.ui.draw()
                await asyncio.sleep(1 / 30)
        finally:
            if self.portal is not None:
                await self.portal.stop()
            try:
                if self.wifi.hotspot_active:
                    self.wifi.stop_hotspot()
            except Exception:
                pass
            self.inp.close()
            self.screen.close()

    async def _smoke(self) -> None:
        # Exercise Wi-Fi setup drawing + portal bind without waiting on a phone.
        self.state.mode = "wifi_setup"
        self.state.portal_url = "http://127.0.0.1:8765/"
        self.ui.draw()
        portal = SetupPortal(self.wifi, self.state.device_id)
        url = await portal.start()
        # Hit the page once
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                body = await resp.text()
                assert resp.status == 200, resp.status
                assert "Galaxy Cube" in body
            async with session.get(url + "api/networks") as resp:
                data = await resp.json()
                assert data.get("ok") and data.get("networks")
        await portal.stop()

        self.state.mode = "home"
        self.ui.handle(Event.CLICK)
        self.ui.draw()
        for _ in range(6):
            self.ui.handle(Event.TURN_CW)
            self.ui.draw()
        print("Smoke check OK")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)
    if args.sim or args.smoke:
        os.environ["GALAXY_CUBE_SIM"] = "1"
        config.SIMULATOR = True  # type: ignore[misc]

    app = App(scale=args.scale)
    try:
        asyncio.run(
            app.run(
                skip_boot=args.skip_boot,
                smoke=args.smoke,
                skip_wifi=args.skip_wifi,
                force_wifi=args.force_wifi_setup,
                wifi_timeout=args.wifi_timeout,
            )
        )
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
