"""Bring-up test for battery voltage sensing via ADS1115 + voltage divider.
Wiring:
  Battery+ -> 10k resistor -> junction -> 20k resistor -> GND
  Junction -> ADS1115 AIN0
  ADS1115 VDD -> Pi 3.3V, GND -> common ground
  SDA -> GPIO2 (pin 3), SCL -> GPIO3 (pin 5)

The 10k/20k divider scales the battery voltage down by 1.5x, so multiply
the raw ADC reading by 1.5 to recover the real battery voltage.
"""
import time

import smbus2

ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG = 0x01

# Single-shot, AIN0 vs GND, +-4.096V range (PGA=1), 128 SPS, comparator off.
CONFIG_VALUE = 0xC383

DIVIDER_RATIO = 1.5554  # calibrated against a multimeter reading, not the ideal 1.5 --
                         # real resistor tolerance shifts this a few percent in practice
LSB_VOLTS = 4.096 / 32768  # volts per ADC count at +-4.096V range

bus = smbus2.SMBus(1)


def read_raw():
    # Write config to start a single-shot conversion.
    bus.write_i2c_block_data(ADS1115_ADDR, REG_CONFIG, [CONFIG_VALUE >> 8, CONFIG_VALUE & 0xFF])
    time.sleep(0.01)  # conversion takes ~8ms at 128SPS, pad a little
    data = bus.read_i2c_block_data(ADS1115_ADDR, REG_CONVERSION, 2)
    raw = (data[0] << 8) | data[1]
    if raw & 0x8000:
        raw -= 1 << 16
    return raw


print("Reading battery voltage for 10 seconds, 1/sec...")
for _ in range(10):
    raw = read_raw()
    adc_volts = raw * LSB_VOLTS
    battery_volts = adc_volts * DIVIDER_RATIO
    print(f"  ADC: {adc_volts:.3f} V   Battery: {battery_volts:.3f} V")
    time.sleep(1)

print("\nDone. Battery voltage should be in the 3.0-4.2V range for a 1S LiPo/Li-ion cell.")
