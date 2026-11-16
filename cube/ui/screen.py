"""Drawing on the 128x64 OLED (spec §9). Fake mode saves screen.png and prints the text instead."""
import random

from PIL import Image, ImageDraw, ImageFont

from .. import config

log = config.log
W, H = 128, 64
ROW = 10          # pixels per text line
ROWS = H // ROW   # 6 lines
BRIGHTNESS = {"Low": 30, "Medium": 120, "High": 255}


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, OSError):
        return ImageFont.load_default()


FONT = _font(10)
BIG = _font(22)


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
        """A title bar (optional) and up to 5-6 lines of text."""
        image, d = self._new()
        y = 0
        if title:
            d.rectangle((0, 0, W, ROW), fill=1)
            d.text((2, 0), title, font=FONT, fill=0)
            y = ROW + 2
        for line in lines:
            d.text((2, y), line, font=FONT, fill=1)
            y += ROW
        self._show(image, "\n".join(([f"[{title}]"] if title else []) + list(lines)))

    def menu(self, title, labels, selected):
        """A list with the selected item highlighted. Scrolls when it's longer than the screen."""
        image, d = self._new()
        d.rectangle((0, 0, W, ROW), fill=1)
        d.text((2, 0), title, font=FONT, fill=0)
        visible = ROWS - 1
        first = min(max(0, selected - visible + 1), max(0, len(labels) - visible))
        text = [f"[{title}]"]
        for i, label in enumerate(labels[first:first + visible], start=first):
            y = ROW + 2 + (i - first) * ROW
            if i == selected:
                d.rectangle((0, y, W, y + ROW - 1), fill=1)
                d.text((3, y - 1), label, font=FONT, fill=0)
                text.append("> " + label)
            else:
                d.text((3, y - 1), label, font=FONT, fill=1)
                text.append("  " + label)
        self._show(image, "\n".join(text))

    def big(self, big_text, top, bottom=()):
        """A big code in the middle, with small text above and below (used for pairing)."""
        image, d = self._new()
        d.text((2, 0), top, font=FONT, fill=1)
        w = d.textlength(big_text, font=BIG)
        d.text(((W - w) / 2, 14), big_text, font=BIG, fill=1)
        for i, line in enumerate(bottom):
            d.text((2, 42 + i * ROW), line, font=FONT, fill=1)
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
        w = d.textlength("Galaxy Cube", font=_font(16))
        d.text(((W - w) / 2, 22), "Galaxy Cube", font=_font(16), fill=1)
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
