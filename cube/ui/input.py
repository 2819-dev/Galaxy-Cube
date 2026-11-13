"""Knob + TALK/MUTE buttons → high-level UI events.

Simulator keys (when not on a Pi):
  ↑ / ↓     turn the knob
  Enter     press the knob
  T         hold = TALK (push-to-talk)
  M         press = MUTE toggle
  Esc / Q   quit (simulator only)
"""

from __future__ import annotations

import asyncio
import enum
import time
from collections import deque
from typing import Deque, Optional

from cube import config


class Event(enum.Enum):
    TURN_CW = "turn_cw"
    TURN_CCW = "turn_ccw"
    CLICK = "click"
    TALK_DOWN = "talk_down"
    TALK_UP = "talk_up"
    MUTE = "mute"
    MUTE_LONG = "mute_long"
    QUIT = "quit"


class Input:
    """Non-blocking event source for the UI loop."""

    def __init__(self) -> None:
        self._queue: Deque[Event] = deque()
        self._talk_held = False
        self._mute_down_at: Optional[float] = None
        self._hw = None
        self._pygame = None
        if config.SIMULATOR:
            self._init_simulator()
        else:
            self._init_hw()

    def _init_hw(self) -> None:
        try:
            from gpiozero import Button, RotaryEncoder

            # Encoder: CLK=GPIO17, DT=GPIO27, SW=GPIO22
            enc = RotaryEncoder(17, 27, max_steps=0)
            btn = Button(22, pull_up=True, bounce_time=0.05)
            talk = Button(5, pull_up=True, bounce_time=0.05)
            mute = Button(6, pull_up=True, bounce_time=0.05)

            enc.when_rotated_clockwise = lambda: self._queue.append(Event.TURN_CW)
            enc.when_rotated_counter_clockwise = lambda: self._queue.append(Event.TURN_CCW)
            btn.when_pressed = lambda: self._queue.append(Event.CLICK)
            talk.when_pressed = lambda: self._on_talk(True)
            talk.when_released = lambda: self._on_talk(False)
            mute.when_pressed = lambda: self._on_mute(True)
            mute.when_released = lambda: self._on_mute(False)
            self._hw = (enc, btn, talk, mute)
        except Exception as exc:  # pragma: no cover
            print(f"GPIO init failed ({exc}); using simulator keys.")
            config.SIMULATOR = True  # type: ignore[misc]
            self._init_simulator()

    def _init_simulator(self) -> None:
        import pygame

        if not pygame.get_init():
            pygame.init()
        self._pygame = pygame
        self._keys_talk = False
        self._keys_mute = False

    def _on_talk(self, down: bool) -> None:
        self._talk_held = down
        self._queue.append(Event.TALK_DOWN if down else Event.TALK_UP)

    def _on_mute(self, down: bool) -> None:
        if down:
            self._mute_down_at = time.monotonic()
        else:
            if self._mute_down_at is None:
                return
            held = time.monotonic() - self._mute_down_at
            self._mute_down_at = None
            self._queue.append(Event.MUTE_LONG if held >= 0.8 else Event.MUTE)

    def poll(self) -> list[Event]:
        """Drain new events (also pumps pygame in simulator)."""
        if self._pygame is not None:
            self._poll_pygame()
        # Check long-press mute while held (HW path also uses release; this covers mid-hold)
        out: list[Event] = []
        while self._queue:
            out.append(self._queue.popleft())
        return out

    def _poll_pygame(self) -> None:
        assert self._pygame is not None
        for ev in self._pygame.event.get():
            if ev.type == self._pygame.QUIT:
                self._queue.append(Event.QUIT)
            elif ev.type == self._pygame.KEYDOWN:
                if ev.key in (self._pygame.K_UP, self._pygame.K_LEFT):
                    self._queue.append(Event.TURN_CCW)
                elif ev.key in (self._pygame.K_DOWN, self._pygame.K_RIGHT):
                    self._queue.append(Event.TURN_CW)
                elif ev.key in (self._pygame.K_RETURN, self._pygame.K_SPACE):
                    self._queue.append(Event.CLICK)
                elif ev.key == self._pygame.K_t:
                    if not self._keys_talk:
                        self._keys_talk = True
                        self._on_talk(True)
                elif ev.key == self._pygame.K_m:
                    if not self._keys_mute:
                        self._keys_mute = True
                        self._on_mute(True)
                elif ev.key in (self._pygame.K_ESCAPE, self._pygame.K_q):
                    self._queue.append(Event.QUIT)
            elif ev.type == self._pygame.KEYUP:
                if ev.key == self._pygame.K_t and self._keys_talk:
                    self._keys_talk = False
                    self._on_talk(False)
                elif ev.key == self._pygame.K_m and self._keys_mute:
                    self._keys_mute = False
                    self._on_mute(False)

    @property
    def talk_held(self) -> bool:
        return self._talk_held

    async def wait_event(self, timeout: float = 0.05) -> Optional[Event]:
        events = self.poll()
        if events:
            return events[0]
        await asyncio.sleep(timeout)
        events = self.poll()
        return events[0] if events else None

    def close(self) -> None:
        if self._hw is not None:
            for part in self._hw:
                try:
                    part.close()
                except Exception:
                    pass
