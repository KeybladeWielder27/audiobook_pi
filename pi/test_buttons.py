"""
Bring-up test for all navigation/volume buttons. Reads pin assignments
directly from config.py so this can never fall out of sync with the app.
Each button is wired between its GPIO and GND (internal pull-up used,
so a press pulls the pin LOW).
"""
from signal import pause

from gpiozero import Button

import config


def make_handler(name):
    def handler():
        print(f"[PRESS]   {name}")
    return handler


def make_release_handler(name):
    def handler():
        print(f"[release] {name}")
    return handler


buttons = {}
for name, pin in config.BUTTON_PINS.items():
    btn = Button(pin, pull_up=True, bounce_time=0.05)
    btn.when_pressed = make_handler(name)
    btn.when_released = make_release_handler(name)
    buttons[name] = btn
    print(f"Registered '{name}' on GPIO{pin}")

print("\nAll buttons registered. Press each one -- Ctrl+C to quit.\n")

try:
    pause()
except KeyboardInterrupt:
    print("\nExiting.")
