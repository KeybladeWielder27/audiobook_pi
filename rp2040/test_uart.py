"""UART bring-up test, RP2040 side. Listens for lines, replies PONG when it
sees PING. Run from Thonny while test_uart.py runs on the Pi.
"""
from machine import UART, Pin
import time

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

print("Listening for UART messages...")
buf = b""
while True:
    if uart.any():
        buf += uart.read()
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode().strip()
            print(f"Received: {text}")
            if text == "PING":
                uart.write(b"PONG\n")
                print("Sent: PONG")
    time.sleep_ms(10)
