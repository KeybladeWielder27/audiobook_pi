"""Bring-up test for the ST7789 TFT wired to the RP2040 Zero.
Run this from Thonny (or save as main.py to run on boot).
"""
import framebuf
from machine import Pin, SPI, PWM
import time

from st7789_mini import ST7789

WIDTH = 320
HEIGHT = 240

# Backlight on GP7, full brightness for this test
bl = PWM(Pin(7))
bl.freq(1000)
bl.duty_u16(65535)

spi = SPI(0, baudrate=32_000_000, sck=Pin(2), mosi=Pin(3))
cs = Pin(5)
dc = Pin(4)
rst = Pin(6)

display = ST7789(spi, cs, dc, rst, width=WIDTH, height=HEIGHT)

buf = bytearray(WIDTH * HEIGHT * 2)  # RGB565 = 2 bytes/pixel
fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.RGB565)

# framebuf color helper: pack RGB888 into RGB565. framebuf stores colors in
# native (little-endian) byte order internally, but the ST7789 expects each
# 16-bit color big-endian over SPI -- so we pre-swap the bytes here, which
# cancels out once framebuf stores it, landing correctly on the wire.
def rgb(r, g, b):
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((val & 0xFF) << 8) | (val >> 8)

WHITE = rgb(255, 255, 255)
BLACK = rgb(0, 0, 0)
RED = rgb(255, 0, 0)
GREEN = rgb(0, 200, 0)
BLUE = rgb(0, 100, 255)
YELLOW = rgb(255, 220, 0)

print("Drawing test pattern...")
fb.fill(BLACK)
fb.text("Hello!", 10, 10, WHITE)
fb.text("RP2040 TFT OK", 10, 30, GREEN)
fb.fill_rect(10, 60, 100, 40, RED)
fb.fill_rect(120, 60, 100, 40, BLUE)
display.blit(buf)
time.sleep(3)

print("Animating a moving box for 5 seconds...")
start = time.ticks_ms()
x = 0
while time.ticks_diff(time.ticks_ms(), start) < 5000:
    fb.fill(BLACK)
    fb.fill_rect(x, 140, 30, 30, YELLOW)
    display.blit(buf)
    x = (x + 8) % (WIDTH - 30)
    time.sleep_ms(50)

fb.fill(BLACK)
fb.text("Test complete!", 10, 120, WHITE)
display.blit(buf)

print("Done. If you saw colored shapes, text, and a moving box, it's working.")
