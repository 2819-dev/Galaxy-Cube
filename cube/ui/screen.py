"""128×64 OLED drawing — real SH1106/SSD1306 on the Pi, pygame window in simulator."""

from __future__ import annotations

import math
import random
import time
from PIL import Image, ImageDraw

from cube import config
from cube.ui import fonts

WIDTH = config.SCREEN_WIDTH
HEIGHT = config.SCREEN_HEIGHT


class Screen:
    """Owns the framebuffer and pushes frames to the OLED or a pygame window."""

    def __init__(self, scale: int = 8) -> None:
        self.scale = scale
        self.image = Image.new("1", (WIDTH, HEIGHT), 0)
        self.draw = ImageDraw.Draw(self.image)
        self._device = None
        self._pygame = None
        self._surface = None
        self._window = None
        self.brightness = 1.0  # 1.0 = full, 0.3 = dim, 0.0 = off
        self._off = False
        if config.SIMULATOR:
            self._init_simulator()
        else:
            self._init_hw()

    def _init_hw(self) -> None:
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import sh1106, ssd1306

            serial = i2c(port=1, address=0x3C)
            try:
                self._device = sh1106(serial, width=WIDTH, height=HEIGHT)
            except Exception:
                self._device = ssd1306(serial, width=WIDTH, height=HEIGHT)
        except Exception as exc:  # pragma: no cover - falls back if wiring missing
            print(f"OLED init failed ({exc}); falling back to simulator.")
            config.SIMULATOR = True  # type: ignore[misc]
            self._init_simulator()

    def _init_simulator(self) -> None:
        import pygame

        pygame.init()
        pygame.display.set_caption("Galaxy Cube — simulator (128×64)")
        self._pygame = pygame
        size = (WIDTH * self.scale, HEIGHT * self.scale)
        self._window = pygame.display.set_mode(size)
        self._surface = pygame.Surface((WIDTH, HEIGHT))

    def clear(self, fill: int = 0) -> None:
        self.draw.rectangle((0, 0, WIDTH, HEIGHT), fill=fill)

    def text(self, x: int, y: int, s: str, scale: int = 1, fill: int = 1) -> None:
        fonts.draw_text(self.draw, (x, y), s, fill=fill, scale=scale)

    def text_centered(self, y: int, s: str, scale: int = 1, fill: int = 1) -> None:
        w = fonts.text_width(s, scale)
        self.text((WIDTH - w) // 2, y, s, scale=scale, fill=fill)

    def line(self, xy: tuple[int, int, int, int], fill: int = 1) -> None:
        self.draw.line(xy, fill=fill)

    def rect(self, xy: tuple[int, int, int, int], fill: int = 1, outline: int | None = None) -> None:
        self.draw.rectangle(xy, fill=fill, outline=outline)

    def pixel(self, x: int, y: int, fill: int = 1) -> None:
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.draw.point((x, y), fill=fill)

    def invert_region(self, x: int, y: int, w: int, h: int) -> None:
        """Highlight a menu row by inverting pixels."""
        for py in range(y, min(HEIGHT, y + h)):
            for px in range(x, min(WIDTH, x + w)):
                v = self.image.getpixel((px, py))
                self.image.putpixel((px, py), 0 if v else 1)

    def show(self) -> None:
        if self._off or self.brightness <= 0:
            blank = Image.new("1", (WIDTH, HEIGHT), 0)
            self._push(blank)
            return
        if self.brightness < 1.0:
            # Cheap dim: checkerboard-drop pixels
            dimmed = self.image.copy()
            step = 2 if self.brightness >= 0.5 else 3
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if (x + y) % step != 0 and dimmed.getpixel((x, y)):
                        dimmed.putpixel((x, y), 0)
            self._push(dimmed)
            return
        self._push(self.image)

    def _push(self, img: Image.Image) -> None:
        if self._device is not None:
            self._device.display(img)
            return
        if self._pygame is None or self._window is None or self._surface is None:
            return
        # 1-bit → RGB for pygame
        rgb = img.convert("RGB")
        pixels = self._pygame.image.fromstring(rgb.tobytes(), rgb.size, rgb.mode)
        scaled = self._pygame.transform.scale(
            pixels, (WIDTH * self.scale, HEIGHT * self.scale)
        )
        self._window.blit(scaled, (0, 0))
        self._pygame.display.flip()

    def set_power(self, on: bool) -> None:
        self._off = not on

    def set_brightness(self, level: float) -> None:
        self.brightness = max(0.0, min(1.0, level))

    def close(self) -> None:
        if self._pygame is not None:
            self._pygame.quit()


def boot_starburst(screen: Screen, duration_s: float = 1.6) -> None:
    """Animated star burst, then the Galaxy Cube wordmark for ~1 s."""
    cx, cy = WIDTH // 2, HEIGHT // 2
    stars = [
        (
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            random.uniform(0.4, 1.6),
            random.randint(0, 4),
        )
        for _ in range(28)
    ]
    # Normalize directions
    normed = []
    for dx, dy, speed, phase in stars:
        length = math.hypot(dx, dy) or 1.0
        normed.append((dx / length, dy / length, speed, phase))

    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        if t > duration_s:
            break
        screen.clear()
        progress = t / duration_s
        for dx, dy, speed, phase in normed:
            dist = (progress * speed * 48) + phase
            x = int(cx + dx * dist)
            y = int(cy + dy * dist)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                screen.pixel(x, y, 1)
                if progress > 0.35:
                    screen.pixel(x + 1, y, 1)
        # Expanding ring
        r = int(progress * 40)
        if 2 < r < 36:
            for a in range(0, 360, 12):
                rad = math.radians(a)
                screen.pixel(int(cx + math.cos(rad) * r), int(cy + math.sin(rad) * r), 1)
        # Center flash
        if progress < 0.25:
            screen.rect((cx - 1, cy - 1, cx + 1, cy + 1), fill=1)
        screen.show()
        time.sleep(1 / 30)

    # Wordmark
    screen.clear()
    screen.text_centered(18, "Galaxy Cube", scale=1)
    screen.line((24, 30, 103, 30))
    screen.text_centered(38, "galaxymc.us", scale=1)
    screen.show()
    time.sleep(1.0)


def draw_status_dot(screen: Screen, x: int, y: int, on: bool) -> None:
    if on:
        screen.text(x, y, "●")
    else:
        screen.text(x, y, "○")
