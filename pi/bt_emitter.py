"""Talks to a KCX_BT_EMITTER V1.7 Bluetooth audio module. The Pi has no
free hardware UART of its own (its only one is already used for the
RP2040 display link, and USB was intentionally avoided to keep everything
on the GPIO header for a fully embedded device) -- so the RP2040 acts as
a bridge, relaying AT commands out over its own second UART (UART1) to
the module, and relaying responses back.

NOTE: exact AT command syntax/responses should be verified against your
specific module -- this is a starting template, not a confirmed-working
command set. Test send_command("AT+GMR?") first to confirm the link
itself works before relying on any of the higher-level helpers below.
"""
import time

import display


def send_command(command: str, wait_for_response: bool = True, timeout: float = 1.0):
    """Sends an AT command, optionally waiting briefly for a reply.
    Returns the response text (without the module's own line terminators),
    or None if no response arrived within timeout."""
    display.send_bt_at(command)
    if not wait_for_response:
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = display.poll_bt_response()
        if response is not None:
            return response
        time.sleep(0.05)
    return None


def get_firmware_version():
    return send_command("AT+GMR?")


def get_volume():
    return send_command("AT+VOL?")


def set_volume(level: int):
    return send_command(f"AT+VOL={level}")


def get_bt_mode():
    return send_command("AT+BT_MODE?")
