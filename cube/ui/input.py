"""Knob and buttons -> events (spec §8, §9).

Events: "up", "down", "press" (knob), "talk_down", "talk_up", "mute", "mute_long".
Fake mode reads the keyboard instead. Type a letter and press Enter:
  u / d  = turn the knob up / down (uuu = three steps)   Enter or p = press the knob
  t      = tap TALK    h = hold TALK down / let go (type h again)
  m      = MUTE        M = long-press MUTE (deafen)     q = quit
"""
import asyncio
import sys

from .. import config

FAKE_KEYS = {"u": ["up"], "d": ["down"], "p": ["press"], "t": ["talk_down", "talk_up"],
             "m": ["mute"], "M": ["mute_long"], "q": ["quit"]}


class Input:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self.talk_held = False
        if config.FAKE:
            self._start_fake()
        else:
            self._start_gpio()

    def _emit(self, event):
        self.loop.call_soon_threadsafe(self.queue.put_nowait, event)

    async def get(self, timeout=None):
        """Next event, or None after `timeout` seconds."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

    @staticmethod
    def button(pin, **options):
        """A button that works however it's wired: a plain button to GND, or a 3-pin button board
        (pressed = LOW or pressed = HIGH). Checked once at start, while nobody is pressing it."""
        from gpiozero import Button, DigitalInputDevice
        probe = DigitalInputDevice(pin, pull_up=True)
        idle_high = probe.pin.state == 1   # a board that pulls the pin down reads LOW here
        probe.close()
        return Button(pin, pull_up=idle_high, **options)

    def _start_gpio(self):
        from gpiozero import RotaryEncoder
        self.encoder = RotaryEncoder(17, 27, max_steps=0)
        self.encoder.when_rotated_clockwise = lambda: self._emit("down")
        self.encoder.when_rotated_counter_clockwise = lambda: self._emit("up")
        self.knob = self.button(22, bounce_time=0.05)
        self.knob.when_pressed = lambda: self._emit("press")
        self.talk = self.button(5, bounce_time=0.03)
        self.talk.when_pressed = lambda: self._emit("talk_down")
        self.talk.when_released = lambda: self._emit("talk_up")
        self.mute = self.button(6, bounce_time=0.05, hold_time=1.0)
        self._mute_was_held = False

        def held():
            self._mute_was_held = True
            self._emit("mute_long")

        def released():
            if not self._mute_was_held:
                self._emit("mute")
            self._mute_was_held = False

        self.mute.when_held = held
        self.mute.when_released = released

    def _start_fake(self):
        print(__doc__.split("\n\n", 1)[1], flush=True)

        def on_line():
            line = sys.stdin.readline()
            if line == "":           # stdin closed
                self.loop.remove_reader(sys.stdin)
                self.queue.put_nowait("quit")
                return
            line = line.strip()
            if not line:
                self.queue.put_nowait("press")
            for ch in line:
                if ch == "h":
                    self.talk_held = not self.talk_held
                    self.queue.put_nowait("talk_down" if self.talk_held else "talk_up")
                for event in FAKE_KEYS.get(ch, []):
                    self.queue.put_nowait(event)

        self.loop.add_reader(sys.stdin, on_line)
