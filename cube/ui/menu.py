"""Menu tree and screen states (boot → home → menus).

Items that are not wired up yet show a short "Coming soon" page.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from cube import config
from cube.ui.input import Event, Input
from cube.ui.screen import Screen, boot_starburst


@dataclass
class UiState:
    wifi_ok: bool = True
    broadcasting: bool = False
    online_count: int = 0
    voice_user: str = "—"
    voice_group: str = "—"
    mic: str = "off"  # off | muted | talking
    linked_user: Optional[str] = None
    device_id: str = field(default_factory=config.device_id)
    ip: str = "—"
    brightness: float = 1.0
    screen_timeout: bool = True
    message: Optional[str] = None
    message_until: float = 0.0


@dataclass
class MenuItem:
    label: str
    action: Optional[str] = None  # built-in action id
    children: Optional[list["MenuItem"]] = None
    visible_if: Optional[Callable[[UiState], bool]] = None


def build_menu() -> list[MenuItem]:
    return [
        MenuItem("Xbox Server Broadcast", action="broadcast_xbox"),
        MenuItem("Nintendo Server Broadcast", action="broadcast_switch"),
        MenuItem("PlayStation Server Broadcast", action="broadcast_ps"),
        MenuItem(
            "Stop Broadcast",
            action="broadcast_stop",
            visible_if=lambda s: s.broadcasting,
        ),
        MenuItem(
            "Voice Chat",
            children=[
                MenuItem("◂ Back", action="back"),
                MenuItem("Join voice", action="voice_join"),
                MenuItem("Leave voice", action="voice_leave"),
                MenuItem("Mode: Push-to-talk", action="voice_mode"),
                MenuItem("Groups", action="voice_groups"),
                MenuItem("Audio: Auto", action="voice_audio"),
                MenuItem("Volume", action="voice_volume"),
            ],
        ),
        MenuItem(
            "Account",
            children=[
                MenuItem("◂ Back", action="back"),
                MenuItem("Linked status", action="account_status"),
                MenuItem("Unlink this Cube", action="account_unlink"),
                MenuItem("Pair again", action="account_pair"),
            ],
        ),
        MenuItem(
            "Settings",
            children=[
                MenuItem("◂ Back", action="back"),
                MenuItem("Wi-Fi", action="settings_wifi"),
                MenuItem("Brightness", action="settings_brightness"),
                MenuItem("Screen timeout", action="settings_timeout"),
                MenuItem("About", action="settings_about"),
            ],
        ),
    ]


COMING_SOON = {
    "broadcast_xbox",
    "broadcast_switch",
    "broadcast_ps",
    "broadcast_stop",
    "voice_join",
    "voice_leave",
    "voice_mode",
    "voice_groups",
    "voice_audio",
    "voice_volume",
    "account_status",
    "account_unlink",
    "account_pair",
    "settings_wifi",
    "settings_brightness",
    "settings_timeout",
}


class UI:
    """Owns the screen + input and runs the home / menu loop."""

    ROW_H = 10
    VISIBLE_ROWS = 5

    def __init__(self, screen: Screen, inp: Input, state: Optional[UiState] = None) -> None:
        self.screen = screen
        self.inp = inp
        self.state = state or UiState()
        self.root = build_menu()
        self.stack: list[tuple[list[MenuItem], int]] = []  # (items, selected)
        self.in_menu = False
        self.home_page = 0
        self._last_input = time.monotonic()
        self._last_home_rotate = time.monotonic()
        self._flash: Optional[str] = None
        self._flash_until = 0.0
        self._about = False
        self.running = True

    def visible_items(self, items: list[MenuItem]) -> list[MenuItem]:
        out = []
        for it in items:
            if it.visible_if is None or it.visible_if(self.state):
                out.append(it)
        return out

    def wake(self) -> None:
        self._last_input = time.monotonic()
        self.screen.set_power(True)
        self.screen.set_brightness(1.0)

    def update_power(self) -> None:
        if not self.state.screen_timeout:
            self.screen.set_power(True)
            self.screen.set_brightness(1.0)
            return
        idle = time.monotonic() - self._last_input
        if idle >= config.SCREEN_IDLE_OFF_S:
            self.screen.set_power(False)
        elif idle >= config.SCREEN_IDLE_DIM_S:
            self.screen.set_power(True)
            self.screen.set_brightness(0.35)
        else:
            self.screen.set_power(True)
            self.screen.set_brightness(1.0)

    def open_menu(self) -> None:
        self.in_menu = True
        self.stack = [(self.visible_items(self.root), 0)]
        self._about = False
        self._flash = None

    def close_menu(self) -> None:
        self.in_menu = False
        self.stack.clear()
        self._about = False
        self._flash = None

    def handle(self, ev: Event) -> None:
        self.wake()
        if ev == Event.QUIT:
            self.running = False
            return
        if ev == Event.TALK_DOWN:
            self.state.mic = "talking"
            return
        if ev == Event.TALK_UP:
            # After releasing TALK, go back to muted if they had muted, else off.
            self.state.mic = "off"
            return
        if ev == Event.MUTE:
            self.state.mic = "off" if self.state.mic == "muted" else "muted"
            return
        if ev == Event.MUTE_LONG:
            self._show_flash("Deafen — Coming soon")
            return

        if self._flash and time.monotonic() < self._flash_until:
            if ev == Event.CLICK:
                self._flash = None
            return

        if self._about:
            if ev in (Event.CLICK, Event.TURN_CW, Event.TURN_CCW):
                self._about = False
            return

        if not self.in_menu:
            if ev == Event.CLICK:
                self.open_menu()
            elif ev in (Event.TURN_CW, Event.TURN_CCW):
                self.home_page = (self.home_page + 1) % 2
            return

        items, sel = self.stack[-1]
        items = self.visible_items(items)
        if not items:
            self.close_menu()
            return
        sel = min(sel, len(items) - 1)

        if ev == Event.TURN_CW:
            sel = (sel + 1) % len(items)
            self.stack[-1] = (items, sel)
        elif ev == Event.TURN_CCW:
            sel = (sel - 1) % len(items)
            self.stack[-1] = (items, sel)
        elif ev == Event.CLICK:
            self._activate(items[sel])

    def _activate(self, item: MenuItem) -> None:
        if item.action == "back":
            self.stack.pop()
            if not self.stack:
                self.close_menu()
            return
        if item.children:
            kids = self.visible_items(item.children)
            self.stack.append((kids, 0))
            return
        action = item.action or ""
        if action == "settings_about":
            self._about = True
            return
        if action in COMING_SOON:
            self._show_flash("Coming soon")
            return
        self._show_flash("Coming soon")

    def _show_flash(self, text: str, seconds: float = 1.4) -> None:
        self._flash = text
        self._flash_until = time.monotonic() + seconds

    def draw(self) -> None:
        self.update_power()
        if self.screen._off:
            self.screen.show()
            return

        if self._flash and time.monotonic() < self._flash_until:
            self._draw_flash(self._flash)
            self.screen.show()
            return
        self._flash = None

        if self._about:
            self._draw_about()
            self.screen.show()
            return

        if self.in_menu and self.stack:
            self._draw_menu()
        else:
            # Rotate home pages while idle
            if time.monotonic() - self._last_home_rotate > 4.0 and not self.in_menu:
                self.home_page = (self.home_page + 1) % 2
                self._last_home_rotate = time.monotonic()
            self._draw_home()
        self.screen.show()

    def _draw_flash(self, text: str) -> None:
        self.screen.clear()
        self.screen.text_centered(28, text)
        self.screen.show()

    def _draw_about(self) -> None:
        s = self.state
        self.screen.clear()
        self.screen.text(2, 2, "About")
        self.screen.line((0, 11, 127, 11))
        self.screen.text(2, 16, f"v{config.FIRMWARE_VERSION}")
        self.screen.text(2, 28, s.device_id)
        self.screen.text(2, 40, f"IP {s.ip}")
        self.screen.text(2, 52, "Press = back")

    def _draw_home(self) -> None:
        s = self.state
        self.screen.clear()
        self.screen.text(2, 2, "GALAXY CUBE")
        self.screen.text(108, 2, "◉" if s.wifi_ok else "○")
        self.screen.line((0, 12, 127, 12))

        if self.home_page == 0:
            bc = "ON" if s.broadcasting else "OFF"
            self.screen.text(2, 18, f"Broadcast: {bc}")
            if s.broadcasting:
                self.screen.text(110, 18, "●")
            self.screen.text(2, 30, f"{s.online_count} online")
            mic = {"off": "off", "muted": "MUTE", "talking": "TALK"}.get(s.mic, s.mic)
            self.screen.text(2, 42, f"Voice: {s.voice_user}")
            group = s.voice_group if s.voice_group != "—" else "-"
            self.screen.text(2, 54, f"Mic:{mic} Grp:{group}")
        else:
            linked = s.linked_user or "not linked"
            self.screen.text(2, 18, f"Account: {linked}")
            self.screen.text(2, 30, s.device_id)
            self.screen.text(2, 42, "Press knob = Menu")
            if config.SIMULATOR:
                self.screen.text(2, 54, "Arrows+Enter T/M")

    def _draw_menu(self) -> None:
        items, sel = self.stack[-1]
        items = self.visible_items(items)
        if not items:
            return
        sel = min(sel, len(items) - 1)
        self.stack[-1] = (items, sel)

        self.screen.clear()
        title = "Menu" if len(self.stack) == 1 else "Submenu"
        self.screen.text(2, 1, title)
        self.screen.line((0, 10, 127, 10))

        top = 0
        if sel >= self.VISIBLE_ROWS:
            top = sel - self.VISIBLE_ROWS + 1
        for i in range(self.VISIBLE_ROWS):
            idx = top + i
            if idx >= len(items):
                break
            it = items[idx]
            y = 12 + i * self.ROW_H
            label = it.label
            if len(label) > 20:
                label = label[:19] + "…"
            prefix = "▸ " if idx == sel else "  "
            self.screen.text(2, y, prefix + label)
            if idx == sel:
                self.screen.invert_region(0, y - 1, 128, self.ROW_H)

    def run_boot(self) -> None:
        boot_starburst(self.screen)
