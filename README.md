# Raspberry Pi Audiobook Player

A dedicated audiobook player built on a Raspberry Pi (Zero W or Zero 2 W),
with an RP2040 co-processor driving a color TFT display over UART.

## Architecture
- **`pi/`** — Python app running on the Raspberry Pi: library scanning,
  playback (via mpv), button input, haptics, battery monitoring, audio
  (I2S DAC). Never touches the display directly.
- **`rp2040/`** — MicroPython firmware for the RP2040 Zero: owns the TFT
  display and backlight entirely, renders every screen, shows an animated
  "waiting" splash whenever the Pi isn't running.
- **`REBUILD_GUIDE.md`** — full setup guide, split into a Pi-only part
  (for hardware swaps) and an RP2040 part (rarely needed again once set up).

## Branches
- `main` — the working, stable build
- `remix` — for variants/experiments without touching `main`
