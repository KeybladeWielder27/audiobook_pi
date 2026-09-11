# Raspberry Pi Audiobook Player

A dedicated audiobook player built on a Raspberry Pi (Zero 2 W or Zero W),
with an RP2040 co-processor driving the display over UART.

## Structure
- `pi/` -- Python app that runs on the Raspberry Pi
- `rp2040/` -- MicroPython firmware for the RP2040 display co-processor
- `REBUILD_GUIDE.md` -- full setup guide from bare OS to running device

## Branches
- `main` -- the working, stable build
- (create new branches here for variants/remixes without touching `main`)
