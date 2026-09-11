"""Button handling: converts GPIO edges into queued named events."""
import queue
import time

from gpiozero import Button

import config


class InputManager:
    def __init__(self):
        self.events = queue.Queue()
        self._buttons = {}
        self._press_times = {}

        for name, pin in config.BUTTON_PINS.items():
            btn = Button(pin, pull_up=True, bounce_time=0.05)
            btn.when_pressed = self._make_press_handler(name)
            btn.when_released = self._make_release_handler(name)
            self._buttons[name] = btn

    def _make_press_handler(self, name):
        def handler():
            self._press_times[name] = time.monotonic()
        return handler

    def _make_release_handler(self, name):
        def handler():
            started = self._press_times.pop(name, time.monotonic())
            held = time.monotonic() - started
            kind = "long" if held >= config.LONG_PRESS_SECONDS else "short"
            self.events.put((name, kind))
        return handler

    def poll(self, timeout=0.1):
        """Returns (button_name, 'short'|'long') or None if nothing happened."""
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None
