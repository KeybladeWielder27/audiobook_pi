"""UART bring-up test, Pi side. Sends PING every second, prints whatever
comes back. Run test_uart.py on the RP2040 (via Thonny) at the same time.
"""
import time

import serial

# /dev/serial0 is a symlink that always points to whichever hardware UART
# is mapped to GPIO14/15, regardless of mini-UART vs PL011 assignment.
ser = serial.Serial("/dev/serial0", baudrate=115200, timeout=1)

print("Sending PING every second. Ctrl+C to stop.")
try:
    while True:
        ser.write(b"PING\n")
        print("Sent: PING")
        line = ser.readline()
        if line:
            print(f"Received: {line.decode(errors='replace').strip()}")
        else:
            print("(no reply)")
        time.sleep(1)
except KeyboardInterrupt:
    pass
