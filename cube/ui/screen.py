"""Drawing on the 128x64 OLED (spec §9). Fake mode saves screen.png and prints the text instead."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import config

log = config.log
W, H = 128, 64
ROW = 10          # pixels per text line
ROWS = H // ROW   # 6 lines
BRIGHTNESS = {"Low": 30, "Medium": 120, "High": 255}
FONT_FILE = Path(__file__).resolve().parent.parent / "fonts" / "Silkscreen-Regular.ttf"


def _font(size):
    """Silkscreen: a pixel font that stays sharp on a 1-bit screen (sizes 8 and 16)."""
    try:
        return ImageFont.truetype(str(FONT_FILE), size)
    except OSError:
        return ImageFont.load_default()


FONT = _font(8)
BIG = _font(16)

# 7x7 icons, drawn pixel by pixel. The phone simulator uses the same ones.
ICONS = {
    "wifi":      [".#####.", "#.....#", "..###..", ".#...#.", "...#...", "...#...", "......."],
    "nowifi":    ["#.....#", ".#...#.", "..#.#..", "...#...", "..#.#..", ".#...#.", "#.....#"],
    "broadcast": ["#.....#", ".#...#.", "#..#..#", "#.###.#", "#..#..#", ".#...#.", "#.....#"],
    "mic":       ["..###..", "..###..", "..###..", "#.###.#", "#.....#", ".#####.", "...#..."],
    "muted":     ["#.###..", ".####..", "..###..", "#.##..#", "#...#.#", ".####..", "...#..#"],
    "talking":   ["..###.#", "..###..", "..###.#", "#.###.#", "#.....#", ".#####.", "...#..."],
    "deafened":  ["#.###..", ".#...#.", "#.#..##", "##.#.##", "##..#.#", "......#", "......."],
    "user":      ["..###..", ".#####.", ".#####.", "..###..", ".......", ".#####.", "#######"],
    "dot":       [".......", "..###..", ".#####.", ".#####.", ".#####.", "..###..", "......."],
    "ring":      [".......", "..###..", ".#...#.", ".#...#.", ".#...#.", "..###..", "......."],
}


def _icon(d, name, x, y, fill=1):
    for row, line in enumerate(ICONS[name]):
        for col, ch in enumerate(line):
            if ch == "#":
                d.point((x + col, y + row), fill=fill)


def _write(d, x, top, text, fill=1):
    """Text whose letters sit inside a 10-pixel row starting at `top`."""
    d.text((x, top + 8), text, font=FONT, fill=fill, anchor="ls")


class Screen:
    def __init__(self):
        self.device = None
        self.last_text = None
        self.is_off = False
        self.is_dim = False
        self.brightness = "High"
        if not config.FAKE:
            from luma.core.interface.serial import i2c
            from luma.oled.device import sh1106, ssd1306
            serial = i2c(port=1, address=0x3C)
            try:
                self.device = sh1106(serial)   # 1.3" screen
            except Exception:
                self.device = ssd1306(serial)  # 0.96" screen

    # ---- low level ----

    def _show(self, image, text):
        if self.device:
            self.device.display(image)
            return
        image.save(config.DATA_DIR / "screen.png")
        if text != self.last_text:
            self.last_text = text
            print("+" + "-" * 24 + "+")
            for line in text.splitlines():
                print("|" + line[:24].ljust(24) + "|")
            print("+" + "-" * 24 + "+", flush=True)

    def _new(self):
        image = Image.new("1", (W, H))
        return image, ImageDraw.Draw(image)

    # ---- what the rest of the code uses ----

    def text(self, lines, title=None):
        """A title bar (optional) and up to 5 lines of text. A line can be (icon, text)."""
        image, d = self._new()
        y = 0
        if title:
            d.rectangle((0, 0, W - 1, ROW), fill=1)
            _write(d, 2, 1, title, fill=0)
            y = ROW + 2
        plain = []
        for line in lines:
            if isinstance(line, tuple):
                icon, line = line
                _icon(d, icon, 2, y + 1)
                _write(d, 12, y, line)
            else:
                _write(d, 2, y, line)
            plain.append(line)
            y += ROW
        self._show(image, "\n".join(([f"[{title}]"] if title else []) + plain))

    def home(self, name, status_icons, rows, hint):
        """Home screen: name on top with small status icons on the right, then icon rows."""
        image, d = self._new()
        _write(d, 2, 0, name)
        x = W - 9
        for icon in status_icons:
            _icon(d, icon, x, 1)
            x -= 10
        d.line((0, 11, W - 1, 11), fill=1)
        y = 15
        for icon, text in rows:
            _icon(d, icon, 2, y + 1)
            _write(d, 12, y, text)
            y += ROW + 1
        w = d.textlength(hint, font=FONT)
        _write(d, W - 2 - w, 54, hint)
        self._show(image, "\n".join([f"{name}  ({' '.join(status_icons)})"] + [t for _, t in rows] + [hint]))

    def menu(self, title, labels, selected):
        """A list with the selected item highlighted. Scrolls when it's longer than the screen."""
        image, d = self._new()
        d.rectangle((0, 0, W - 1, ROW), fill=1)
        _write(d, 2, 1, title, fill=0)
        visible = ROWS - 1
        first = min(max(0, selected - visible + 1), max(0, len(labels) - visible))
        text = [f"[{title}]"]
        for i, label in enumerate(labels[first:first + visible], start=first):
            y = ROW + 3 + (i - first) * ROW
            if i == selected:
                d.rectangle((0, y - 1, W - 4, y + ROW - 2), fill=1)
                _write(d, 3, y, label, fill=0)
                text.append("> " + label)
            else:
                _write(d, 3, y, label)
                text.append("  " + label)
        if len(labels) > visible:  # scroll bar
            h = max(6, 50 * visible // len(labels))
            top = ROW + 2 + (50 - h) * first // (len(labels) - visible)
            d.rectangle((W - 2, top, W - 1, top + h), fill=1)
        self._show(image, "\n".join(text))

    def big(self, big_text, top, bottom=()):
        """A big code in the middle, with small text above and below (used for pairing)."""
        image, d = self._new()
        _write(d, 2, 1, top)
        w = d.textlength(big_text, font=BIG)
        d.text(((W - w) // 2, 37), big_text, font=BIG, fill=1, anchor="ls")
        for i, line in enumerate(bottom):
            _write(d, 2, 44 + i * ROW, line)
        self._show(image, "\n".join([top, "", "   " + big_text, ""] + list(bottom)))

    async def boot_animation(self, sleep):
        """A star burst, then the Galaxy Cube wordmark."""
        stars = [(random.uniform(-1, 1), random.uniform(-1, 1)) for _ in range(40)]
        for step in range(1, 9):
            image, d = self._new()
            for sx, sy in stars:
                x, y = W / 2 + sx * step * 9, H / 2 + sy * step * 5
                d.point((x, y), fill=1)
            if self.device:
                self.device.display(image)
            await sleep(0.06)
        image, d = self._new()
        for sx, sy in stars:
            d.point((W / 2 + sx * 70, H / 2 + sy * 40), fill=1)
        d.rectangle((14, 20, 113, 44), fill=0)
        w = d.textlength("GALAXY", font=BIG)
        d.text(((W - w) // 2, 34), "GALAXY", font=BIG, fill=1, anchor="ls")
        w = d.textlength("CUBE", font=FONT)
        d.text(((W - w) // 2, 43), "CUBE", font=FONT, fill=1, anchor="ls")
        self._show(image, "\n\n    Galaxy Cube")
        await sleep(1)

    # ---- brightness and sleep (OLEDs burn in) ----

    def set_brightness(self, name):
        self.brightness = name
        if self.device and not self.is_dim:
            self.device.contrast(BRIGHTNESS.get(name, 255))

    def dim(self):
        if not self.is_dim:
            self.is_dim = True
            if self.device:
                self.device.contrast(5)

    def off(self):
        if not self.is_off:
            self.is_off = True
            log.info("Screen off")
            if self.device:
                self.device.hide()

    def on(self):
        was_off = self.is_off
        self.is_off = self.is_dim = False
        if self.device:
            if was_off:
                self.device.show()
            self.device.contrast(BRIGHTNESS.get(self.brightness, 255))
