# Audiobook Player Rebuild Guide

Complete setup from blank SD card / fresh RP2040 to a fully working device.
This is a **two-board system**:

- **Raspberry Pi** — runs the actual player app (library, playback, buttons,
  audio, battery). Currently a Pi Zero W (original), but everything here
  applies identically to a Zero 2 W — same GPIO header, same pin numbers,
  no wiring changes needed either way.
- **RP2040 Zero** — a display co-processor. It owns the TFT screen and
  backlight entirely and renders everything itself; the Pi never touches
  the display directly. They talk over a simple UART link.

If you're moving to new Pi hardware (e.g. Zero W → Zero 2 W), you only need
**Part A**. The RP2040 side is untouched — it doesn't know or care which Pi
is talking to it.

---

## Part A — Raspberry Pi Setup

### A1 — Flash the OS

1. Download **Raspberry Pi Imager**.
2. In Imager:
   - **Device**: your board (Zero W or Zero 2 W)
   - **OS**: Raspberry Pi OS Lite. **If using the original Zero W, you must
     pick the 32-bit build** — it cannot boot 64-bit at all (older ARMv6
     CPU). A Zero 2 W can use either; 64-bit is fine there.
   - **Storage**: your SD card
3. Before writing, set hostname, SSH (password or key), Wi-Fi, locale via
   the gear icon.
4. Write and boot.

### A2 — Base system setup

```bash
ssh <username>@audiobookpi.local
sudo apt update && sudo apt full-upgrade -y
sudo raspi-config
```

In `raspi-config` → **Interface Options**, enable:
- **I2C** (for the battery monitor)
- **Serial Port** → "login shell over serial?" **No**, "serial hardware
  enabled?" **Yes** (this frees GPIO14/15 for the RP2040 UART link instead
  of a login console)

Note: **SPI does not need to be enabled** — the Pi no longer drives any
display hardware directly.

Reboot, then install dependencies:

```bash
sudo apt install -y python3-pip python3-venv python3-dev \
  libjpeg-dev zlib1g-dev libfreetype6-dev \
  mpv libmpv-dev git ffmpeg alsa-utils \
  pipewire pipewire-audio wireplumber \
  swig liblgpio-dev i2c-tools
```

Enable persistent logging and linger (needed for headless PipeWire/audio):

```bash
sudo mkdir -p /var/log/journal
sudo systemctl restart systemd-journald
sudo loginctl enable-linger $USER
```

Set up the Python environment. Note the dependency list is shorter than
you might expect — since the Pi no longer drives a display, it needs no
display libraries (`luma`, `spidev`, `RPi.GPIO`) at all, just:

```bash
mkdir -p ~/audiobook-player && cd ~/audiobook-player
python3 -m venv venv
source venv/bin/activate
pip install gpiozero python-mpv mutagen Pillow lgpio smbus2 pyserial
```

If `lgpio` fails to build:
```bash
sudo apt install -y python3-lgpio
```

### A3 — Wi-Fi toggle permission

```bash
which rfkill
sudo visudo -f /etc/sudoers.d/audiobook-wifi
```
Add (adjusting the path if different):
```
pi ALL=(ALL) NOPASSWD: /usr/sbin/rfkill
```

### A4 — Wiring (Pi side only)

The Pi's job is now just: buttons, haptics, battery sensing, audio DAC,
and the UART link to the RP2040.

**Buttons** (each wired to GND, internal pull-ups):
| Button | GPIO | Physical pin |
|---|---|---|
| Menu/Back | GPIO5 | 29 |
| Up | GPIO6 | 31 |
| Down | GPIO27 | 13 |
| Select | GPIO17 | 11 |
| Play/Pause | GPIO26 | 37 |
| Next Chapter | GPIO16 | 36 |
| Prev Chapter | GPIO20 | 38 |
| Volume Up | GPIO22 | 15 |
| Volume Down | GPIO23 | 16 |

**Haptic motor** (GPIO13, physical pin 33) → 1kΩ resistor → transistor base;
transistor emitter → GND; transistor collector → motor −; motor + → 3.3V;
flyback diode across motor terminals (cathode to +, anode to −).

**Battery monitor (INA226 at I2C address 0x40)** — wired in-line with the
battery's power path (like a real ammeter), not tapped off a divider:
| Pin | Connects to |
|---|---|
| VIN+ | Battery+ |
| VIN- | Load (Pi/boost converter power input) |
| VCC | 3.3V |
| GND | GND |
| SDA | GPIO2 (pin 3) |
| SCL | GPIO3 (pin 5) |

No voltage divider needed — the INA226 senses bus voltage directly up to
36V, independent of its own 3.3V supply.

**Audio (PCM5102A I2S DAC):**
| PCM5102A Pin | Connects to |
|---|---|
| VCC | 3.3V |
| GND | GND |
| BCK | GPIO18 (physical pin 12) |
| LCK | GPIO19 (physical pin 35) |
| DIN | GPIO21 (physical pin 40) |
| SCK | GND |

Add to `/boot/firmware/config.txt`:
```
dtparam=audio=off
dtoverlay=hifiberry-dac
```
**Also uncomment `#dtparam=i2s=on`** near the top of the file (remove the
`#`). Easy to miss, and the failure mode is silent: without it, the codec
overlay has no I2S hardware to attach to, and `dmesg` shows nothing at all.

Reboot, then verify with `aplay -l` (should show `sndrpihifiberry`) and
`wpctl status` (should appear as a sink).

**UART link to RP2040:**
| Pi Pin | RP2040 Pin |
|---|---|
| GPIO14 / TXD (physical pin 8) | GP1 (RX) |
| GPIO15 / RXD (physical pin 10) | GP0 (TX) |
| GND | GND |

**Ready signal to RP2040** (tells the RP2040 whether `player.py` is
actually running, vs. mid-boot or crashed):
| Pi Pin | RP2040 Pin |
|---|---|
| GPIO24 (physical pin 18) | GP10 |

**Optional: KCX_BT_EMITTER bridge** — the Pi has no free hardware UART of
its own, so the RP2040 relays AT commands to this module over its own
second UART (UART1), rather than adding a USB adapter. See Part B3 below
for the RP2040-side wiring; nothing changes on the Pi side beyond the
`bt_emitter.py` module talking over the existing UART0 link.

### A5 — Deploy the code

Clone from your GitHub repo (preferred, since it's now version-controlled):
```bash
git clone <your-repo-url> ~/audiobook-player-src
cp -r ~/audiobook-player-src/pi/* ~/audiobook-player/
```

**Whichever method you use, verify it actually landed** before trusting
it — we hit repeated cases during development where a copy silently
didn't take (wrong path, stale terminal state, etc.), producing very
confusing "the fix doesn't work" symptoms that were really "the fix never
arrived." A quick sanity check after any deploy:
```bash
grep SCREEN_SLEEP_TIMEOUT_SECONDS ~/audiobook-player/config.py
```
If that prints nothing, the copy didn't work — recheck paths before
debugging anything else.

```bash
cd ~/audiobook-player
source venv/bin/activate
python -c "import gpiozero, mpv, mutagen, PIL, lgpio, smbus2, serial; print('all imports OK')"
```

### A6 — Isolated hardware tests

```bash
python test_uart.py          # sends PING, expect PONG back from the RP2040
python test_buttons.py       # press each button, confirm correct name prints
python test_haptics.py       # should feel 3 buzzes then a quick double-click
python test_battery.py       # should show voltage close to a multimeter reading
```

(Display is no longer tested from the Pi at all — that happens on the
RP2040 side, see Part B.)

### A7 — Set up audiobooks and confirm playback

```bash
mkdir -p ~/audiobook-player/audiobooks
```
Copy in at least one `.m4b`/`.mp3`, then:
```bash
python player.py
```
Watch the RP2040's screen (not the Pi) — you should see the Main Menu.
Confirm library browsing, playback, and audio through the DAC.

### A8 — Autostart service

No boot-splash service is needed anymore — the RP2040 shows its own
"waiting..." splash automatically whenever the ready signal is low,
including during the entire Pi boot process before `player.py` starts.

```bash
sudo nano /etc/systemd/system/audiobook-player.service
```
```ini
[Unit]
Description=Audiobook Player
After=multi-user.target user@1000.service sound.target
Wants=user@1000.service sound.target

[Service]
Type=simple
User=pi
Environment=XDG_RUNTIME_DIR=/run/user/1000
WorkingDirectory=/home/pi/audiobook-player
ExecStart=/home/pi/audiobook-player/venv/bin/python /home/pi/audiobook-player/player.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```
(Adjust `User=`/paths if your username isn't `pi`.)

```bash
sudo systemctl daemon-reload
sudo systemctl enable audiobook-player.service
sudo reboot
```

### A9 — Boot time optimization (optional but recommended)

Two safe, permanent fixes that took total boot time from ~2:47 to ~2:10 on
a Zero W (should help proportionally on any Pi):

```bash
sudo apt purge cloud-init -y
sudo rm -rf /etc/cloud /var/lib/cloud
sudo systemctl mask rpi-resize-swap-file.service
sudo reboot
```

---

## Part B — RP2040 Display Co-Processor Setup

Only needed once — this board doesn't change when you swap Pi hardware.
Skip this whole part if the RP2040 is already flashed and working.

### B1 — Flash MicroPython

1. Download the RP2040/Pico MicroPython `.uf2` from micropython.org.
2. Hold BOOTSEL, plug in via USB, release — it appears as a drive `RPI-RP2`.
3. Drag the `.uf2` onto it. It reboots automatically.
4. Install **Thonny** (thonny.org), connect to the board (MicroPython
   Raspberry Pi Pico interpreter), confirm the REPL responds.

### B2 — Wiring (RP2040 side)

**TFT display:**
| TFT Pin | RP2040 Pin |
|---|---|
| VCC | 3.3V |
| GND | GND |
| DIN (MOSI) | GP3 |
| CLK (SCLK) | GP2 |
| CS | GP5 |
| DC | GP4 |
| RST | GP6 |
| BL (backlight) | GP7 |

**UART link to Pi:** see Part A4 above (GP0/GP1). **Ready signal:** GP10 (not GP8 — that pin was reassigned to the BT bridge's UART1 if you build that; see B4).

### B3 — Upload firmware

Via Thonny, upload these files to the RP2040's root filesystem:
- `main.py` (runs automatically on boot)
- `st7789_mini.py`
- `sprite_frame1.bin`, `sprite_frame2.bin`, `sprite_frame3.bin`

Power cycle. You should see the animated splash screen immediately, even
with no Pi connected — that's the RP2040 operating independently while it
waits for a ready signal.

### B4 — Optional: KCX_BT_EMITTER bridge

The KCX_BT_EMITTER's UART pins run at 5V TTL logic, while the RP2040 is
3.3V — a level shifter is required between them, not a direct wire.

| KCX_BT_EMITTER Pin | Connects to |
|---|---|
| RX | RP2040 GP8 (via level shifter, low side to RP2040, high side to module) |
| TX | RP2040 GP9 (via level shifter) |
| GND | Common ground |

This uses the RP2040's second hardware UART (UART1), completely
independent of the UART0 link to the Pi — no conflict between display
traffic and BT commands. On the Pi side, `bt_emitter.py` sends AT commands
and reads responses over the *existing* Pi↔RP2040 link; the RP2040 firmware
relays them to/from the module transparently.

Verify the default baud rate in `main.py`'s `bt_uart = UART(1, ...)` line
matches your specific module (9600 is the documented default for the
KCX_BT_EMITTER; other modules in this family may differ — e.g. a
KCX_BT_RTX variant we tested used 115200).

**Level shifter warning, learned the hard way**: make sure you're using a
genuine bidirectional TTL-to-TTL logic level converter (e.g. HW-221 or a
generic BSS138-based board with separate HV/LV power pins) — **not** an
RS232-to-TTL converter (e.g. a MAX3232-based "HW-027" board). They look
similarly generic but do fundamentally different jobs; using the wrong
one produces exactly this failure signature: the RP2040 successfully
writes data out, but absolutely nothing comes back, not even garbage.

---

## Final Checklist

**Before you get here**: avoid opening the Settings screen while still
debugging buttons/wiring — a stray button press can toggle Wi-Fi off, and
that block persists across reboots via the OS itself, potentially locking
you out of SSH with no easy recovery except physical access.

- [ ] RP2040 shows the animated splash screen on its own at power-up
- [ ] Main Menu appears within a few seconds of `player.py` starting
- [ ] Audiobooks play, chapters navigate, resume works
- [ ] A book title too long to fit wraps to 2 lines instead of running off
      (Now Playing and Library both)
- [ ] "Loading..." screen appears briefly when opening a book
- [ ] Volume, skip forward/back adjustable in Settings
- [ ] Holding Up on Now Playing accelerates into continuous fast-forward
      after ~0.6s, instead of just doing one skip
- [ ] Next/Prev Chapter on a book with no chapter data (e.g. a plain mp3)
      jumps ±30 minutes instead of doing nothing
- [ ] Backlight brightness adjustable in Settings
- [ ] Screen goes dark after 10s idle, and any button wakes it without
      also performing that button's normal action
- [ ] Battery percentage shows on Now Playing and in Settings
- [ ] Haptic buzz on every button press
- [ ] Wi-Fi toggle in Settings actually disables/enables the radio
- [ ] Splash reappears if you stop `player.py` (Ctrl+C or service stop)
