"""Bring-up test for the haptic vibration motor.
Wiring:
  GPIO13 -> 1k resistor -> transistor base
  Transistor emitter -> GND
  Transistor collector -> motor '-' lead
  Motor '+' lead -> 3.3V
  Flyback diode across motor leads (cathode to +, anode to -)
"""
import time

from gpiozero import DigitalOutputDevice

motor = DigitalOutputDevice(13)

print("Pulsing 3 times, 0.3s on / 0.3s off...")
for i in range(3):
    print(f"  pulse {i + 1}")
    motor.on()
    time.sleep(0.3)
    motor.off()
    time.sleep(0.3)

print("Now a quick double-buzz like a real button click (0.08s pulses)...")
for i in range(2):
    motor.on()
    time.sleep(0.08)
    motor.off()
    time.sleep(0.15)

print("Done. Did you feel the motor buzz each time?")
