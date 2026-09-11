"""Hardware-level actions for the settings screen. Each function here backs
one toggle/slider in player.py's settings registry. Add new functions here as
new settings (sleep timer, auto power off, ...) get implemented."""
import subprocess

import config
import display  # backlight now lives on the RP2040, controlled over the same UART link


def get_wifi_enabled() -> bool:
    try:
        result = subprocess.run(
            ["rfkill", "list", "wifi"], capture_output=True, text=True, timeout=3
        )
        return "Soft blocked: yes" not in result.stdout
    except Exception:
        return True  # assume on if we can't tell, safer default than silently off


def set_wifi_enabled(enabled: bool):
    try:
        subprocess.run(
            ["sudo", "rfkill", "unblock" if enabled else "block", "wifi"], timeout=5
        )
    except Exception:
        pass


_backlight_last_value = 100


def set_backlight_brightness(percent: int):
    global _backlight_last_value
    percent = max(config.BACKLIGHT_MIN, min(100, percent))
    display.set_backlight(percent)
    _backlight_last_value = percent


def get_backlight_brightness() -> int:
    # Backlight brightness is purely software state on the RP2040 side
    # (nothing to query back from it), so this just reports what we last set.
    return _backlight_last_value


def cleanup_backlight():
    global _backlight_pwm
    if _backlight_pwm is not None:
        _backlight_pwm.stop()
        _backlight_pwm = None
