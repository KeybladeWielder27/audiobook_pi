"""Battery monitoring via ADS1115 reading a voltage divider on AIN0.
Returns (voltage, percent), or None if the sensor can't be read (not wired,
I2C disabled, etc.) so callers can gracefully hide battery UI.

Wiring:
  Battery+ -> 10k resistor -> junction -> 20k resistor -> GND
  Junction -> ADS1115 AIN0
  ADS1115 VDD -> Pi 3.3V, GND -> common ground
"""
import smbus2
import time

ADS1115_ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG = 0x01

# Single-shot, AIN0 vs GND, +-4.096V range (PGA=1), 128 SPS, comparator off.
CONFIG_VALUE = 0xC383
LSB_VOLTS = 4.096 / 32768

# Calibrated against a multimeter reading (see test_battery.py) rather than
# the divider's ideal 1.5x -- real resistor tolerance shifts this a few
# percent in practice. Recalibrate here if you swap resistors.
DIVIDER_RATIO = 1.5554

# Rough discharge curve for a 1S LiPo/Li-ion cell. Not perfectly linear --
# real cells sag fast near empty/full and stay fairly flat in the middle.
_VOLTAGE_CURVE = [
    (3.00, 0), (3.30, 5), (3.50, 10), (3.60, 20), (3.65, 30),
    (3.70, 40), (3.73, 50), (3.76, 60), (3.80, 70), (3.85, 80),
    (3.95, 90), (4.05, 95), (4.20, 100),
]

_bus = None
_ema_voltage = None
EMA_ALPHA = 0.25  # smoothing across polls: lower = smoother but slower to react


def _get_bus():
    global _bus
    if _bus is None:
        _bus = smbus2.SMBus(1)
    return _bus


def _read_raw():
    bus = _get_bus()
    bus.write_i2c_block_data(ADS1115_ADDR, REG_CONFIG, [CONFIG_VALUE >> 8, CONFIG_VALUE & 0xFF])
    time.sleep(0.01)
    data = bus.read_i2c_block_data(ADS1115_ADDR, REG_CONVERSION, 2)
    raw = (data[0] << 8) | data[1]
    if raw & 0x8000:
        raw -= 1 << 16
    return raw


def voltage_to_percent(voltage: float) -> int:
    if voltage <= _VOLTAGE_CURVE[0][0]:
        return 0
    if voltage >= _VOLTAGE_CURVE[-1][0]:
        return 100
    for (v_lo, p_lo), (v_hi, p_hi) in zip(_VOLTAGE_CURVE, _VOLTAGE_CURVE[1:]):
        if v_lo <= voltage <= v_hi:
            frac = (voltage - v_lo) / (v_hi - v_lo)
            return round(p_lo + frac * (p_hi - p_lo))
    return 0


def read_battery(samples: int = 8):
    """Averages several quick samples to cut ADC noise within one reading,
    then applies an exponential moving average across calls so the displayed
    value glides toward new readings instead of jumping every poll."""
    global _ema_voltage
    try:
        readings = [_read_raw() * LSB_VOLTS for _ in range(samples)]
        adc_volts = sum(readings) / len(readings)
        battery_volts = adc_volts * DIVIDER_RATIO

        if _ema_voltage is None:
            _ema_voltage = battery_volts
        else:
            _ema_voltage = EMA_ALPHA * battery_volts + (1 - EMA_ALPHA) * _ema_voltage

        percent = voltage_to_percent(_ema_voltage)
        return _ema_voltage, percent
    except Exception:
        return None


def format_battery(cached_reading):
    if cached_reading is None:
        return "N/A"
    voltage, percent = cached_reading
    return f"{percent}% ({voltage:.2f}V)"
