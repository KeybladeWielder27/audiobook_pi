"""Minimal ST7789 driver for MicroPython on RP2040.
Mirrors the exact orientation/addressing that was confirmed working on the
Pi side: 320x240 landscape, no offset, MADCTL=0x70.
"""
from machine import Pin, SPI
import time

class ST7789:
    def __init__(self, spi, cs, dc, rst, width=320, height=240):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.width = width
        self.height = height
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=1)
        self._init_display()

    def _cmd(self, cmd, data=None):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytearray([cmd]))
        if data is not None:
            self.dc.value(1)
            self.spi.write(data)
        self.cs.value(1)

    def _init_display(self):
        self.rst.value(0)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(50)

        self._cmd(0x01)          # software reset
        time.sleep_ms(150)
        self._cmd(0x11)          # sleep out
        time.sleep_ms(150)
        self._cmd(0x3A, b'\x55') # 16-bit color (RGB565)
        self._cmd(0x36, b'\x70') # MADCTL -- matches the known-working Pi-side orientation
        self._cmd(0x21)          # display inversion on (common requirement for this panel)
        self._cmd(0x13)          # normal display mode
        time.sleep_ms(10)
        self._cmd(0x29)          # display on
        time.sleep_ms(50)

    def set_window(self, x0, y0, x1, y1):
        self._cmd(0x2A, bytearray([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._cmd(0x2B, bytearray([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._cmd(0x2C)

    def blit(self, framebuf_bytes, x0=0, y0=0, x1=None, y1=None):
        x1 = self.width - 1 if x1 is None else x1
        y1 = self.height - 1 if y1 is None else y1
        self.set_window(x0, y0, x1, y1)
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(framebuf_bytes)
        self.cs.value(1)
