"""Haptic feedback: a short vibration pulse on every button press. Uses
gpiozero's background blink so the pulse never blocks the main render loop,
even briefly."""
from gpiozero import DigitalOutputDevice

import config

_motor = DigitalOutputDevice(config.HAPTIC_GPIO)


def pulse():
    _motor.blink(on_time=config.HAPTIC_PULSE_SECONDS, off_time=0, n=1, background=True)
