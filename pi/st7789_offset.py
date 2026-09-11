"""luma.lcd's built-in st7789 driver doesn't support h_offset/v_offset
(unlike its sibling st7735/ili9341 classes), but many real-world ST7789
boards need it because the visible glass is narrower than -- and shifted
within -- the chip's full addressable GRAM range. This subclass adds that
support by overriding set_window(), which is the one place the base class
hardcodes offset-free addressing."""
from luma.lcd.device import st7789 as _st7789_base


class st7789_offset(_st7789_base):
    def __init__(self, *args, h_offset=0, v_offset=0, **kwargs):
        self._h_offset = h_offset
        self._v_offset = v_offset
        super().__init__(*args, **kwargs)

    def set_window(self, x1, y1, x2, y2):
        x1 += self._h_offset
        x2 += self._h_offset
        y1 += self._v_offset
        y2 += self._v_offset
        self.command(0x2A, x1 >> 8, x1 & 0xFF, (x2 - 1) >> 8, (x2 - 1) & 0xFF)
        self.command(0x2B, y1 >> 8, y1 & 0xFF, (y2 - 1) >> 8, (y2 - 1) & 0xFF)
        self.command(0x2C)
