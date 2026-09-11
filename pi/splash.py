"""Draws a simple splash screen on the display at boot, before the main
player starts. The display holds the last frame drawn until something else
writes to it, so this script just draws once and exits immediately -- it
doesn't need to keep running, and has no dependency on audio/network being
ready."""
import time

from luma.core.interface.serial import spi
from luma.core.render import canvas
from PIL import ImageFont

from st7789_offset import st7789_offset
import config


def _font(size):
    for path in config.FONT_PATH_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


print("Initializing display...")
serial = spi(port=config.DISPLAY_SPI_PORT, device=config.DISPLAY_SPI_DEVICE,
             gpio_DC=config.DISPLAY_GPIO_DC, gpio_RST=config.DISPLAY_GPIO_RST)
device = st7789_offset(serial, width=config.DISPLAY_WIDTH, height=config.DISPLAY_HEIGHT,
                        rotate=0, h_offset=config.DISPLAY_H_OFFSET, v_offset=config.DISPLAY_V_OFFSET)

title_font = _font(28)
sub_font = _font(16)

print("Drawing splash frame...")
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="black", fill="black")

    title = "Audiobook Player"
    title_w = draw.textlength(title, font=title_font)
    draw.text(((config.DISPLAY_WIDTH - title_w) / 2, 90), title, font=title_font, fill="white")

    subtitle = "starting..."
    sub_w = draw.textlength(subtitle, font=sub_font)
    draw.text(((config.DISPLAY_WIDTH - sub_w) / 2, 135), subtitle, font=sub_font, fill="dodgerblue")

print("Frame sent. Holding briefly...")
time.sleep(2)
print("Done.")
