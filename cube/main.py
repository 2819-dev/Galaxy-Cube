#!/usr/bin/env python3
"""Galaxy Cube — one asyncio process.

Right now this boots the OLED UI (or the pygame simulator) with the full menu tree.
Wi-Fi, pairing, Phantom broadcast and voice will plug in here later.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from cube import config
from cube.ui.input import Input
from cube.ui.menu import UI, UiState
from cube.ui.screen import Screen


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
    return p.parse_args(argv)


async def run_ui(skip_boot: bool = False, scale: int = 8, smoke: bool = False) -> None:
    config.ensure_state_dir()
    screen = Screen(scale=scale)
    inp = Input()
    state = UiState(
        device_id=config.device_id(),
        wifi_ok=True,
        linked_user=None,
        voice_user="—",
        voice_group="—",
        ip="127.0.0.1" if config.SIMULATOR else "—",
    )
    ui = UI(screen, inp, state)

    print("Galaxy Cube UI starting")
    print(f"  mode: {'SIMULATOR' if config.SIMULATOR else 'hardware'}")
    print(f"  device id: {state.device_id}")
    if config.SIMULATOR and not smoke:
        print("  keys: ↑↓ scroll  Enter select  T talk  M mute  Esc quit")

    try:
        if not skip_boot:
            # Boot animation is synchronous drawing; run in a thread so asyncio stays responsive.
            await asyncio.to_thread(ui.run_boot)
        ui.wake()
        ui.draw()

        if smoke:
            # Walk the menu tree once so drawing paths are exercised.
            from cube.ui.input import Event

            ui.handle(Event.CLICK)  # open menu
            ui.draw()
            for _ in range(6):
                ui.handle(Event.TURN_CW)
                ui.draw()
            ui.handle(Event.CLICK)  # open a submenu or coming soon
            ui.draw()
            ui.handle(Event.CLICK)
            ui.draw()
            print("Smoke check OK")
            return

        while ui.running:
            events = inp.poll()
            for ev in events:
                ui.handle(ev)
            ui.draw()
            await asyncio.sleep(1 / 30)
    finally:
        inp.close()
        screen.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.sim or args.smoke:
        # Force simulator before Screen/Input construct.
        import os

        os.environ["GALAXY_CUBE_SIM"] = "1"
        # Re-read flag (config.SIMULATOR was computed at import time).
        config.SIMULATOR = True  # type: ignore[misc]

    try:
        asyncio.run(run_ui(skip_boot=args.skip_boot, scale=args.scale, smoke=args.smoke))
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
