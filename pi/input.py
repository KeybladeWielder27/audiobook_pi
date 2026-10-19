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

    def is_held(self, name):
        """True while the button is currently pressed down."""
        return self._buttons[name].is_active

    def held_duration(self, name):
        """Seconds the button has been held so far, or 0.0 if not currently
        pressed. Lets the main loop implement hold-to-repeat actions
        (e.g. super fast-forward) without waiting for a release event."""
        if self._buttons[name].is_active and name in self._press_times:
            return time.monotonic() - self._press_times[name]
        return 0.0
