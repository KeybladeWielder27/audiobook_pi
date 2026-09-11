"""
Bring-up test for the AITRIP 2.0" ST7789V TFT (240x320, SPI).
Wiring (same SPI/DC/RST as the old OLED):
  DIN/MOSI -> GPIO10 (SPI0 MOSI)
  CLK/SCK  -> GPIO11 (SPI0 SCLK)
  CS       -> GPIO8  (SPI0 CE0)
  DC       -> GPIO24
  RST      -> GPIO25
  BL       -> 3.3V (always on)
"""

import time

import RPi.GPIO as GPIO
from luma.core.interface.serial import spi
from luma.core.render import canvas

from st7789_offset import st7789_offset

# Backlight now lives on GPIO12 with software control (used to be hardwired
# to 3.3V) -- turn it fully on for this standalone test, since nothing else
# will drive that pin outside the main app.
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(12, GPIO.OUT)
GPIO.output(12, GPIO.HIGH)

# Native panel resolution, no rotation for this first test.
# NOTE: many "2.0 inch ST7789" boards are actually 172x320 with the visible
# glass shifted within the chip's 240-column addressable range -- h_offset
# tells the driver where the real pixels start.
serial = spi(port=0, device=0, gpio_DC=24, gpio_RST=25, bus_speed_hz=32000000)
device = st7789_offset(serial, width=320, height=240, rotate=0, h_offset=0, v_offset=0)

print(f"Display initialized: {device.width}x{device.height}")
print("Drawing color test pattern...")

with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    draw.text((10, 10), "Hello!", fill="white")
    draw.text((10, 40), "TFT Display OK", fill="green")
    draw.rectangle((10, 70, 110, 110), outline="red", fill="red")
    draw.rectangle((120, 70, 220, 110), outline="blue", fill="blue")

time.sleep(4)

print("Animating a moving box for 5 seconds...")
x = 0
start = time.time()
while time.time() - start < 5:
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.rectangle((x, 150, x + 30, 190), outline="yellow", fill="yellow")
    x = (x + 8) % (device.width - 30)
    time.sleep(0.05)

with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    draw.text((10, 140), "Test complete!", fill="white")

print("Done. If you saw colored shapes, text, and a moving box, it's working.")
