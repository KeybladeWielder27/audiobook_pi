# Audiobook Player Rebuild Guide — Pi Zero W

Complete setup from a blank SD card to a fully working device. This
consolidates every fix and lesson learned during the original build on a
Pi Zero 2 W — no need to repeat any of that troubleshooting here.

## Before you start: the one critical difference

**The original Pi Zero W cannot run 64-bit Raspberry Pi OS.** It uses the
older ARM11 (ARMv6) processor; only the Zero 2 W's quad-core Cortex-A53
supports 64-bit. If you have your old SD card from the Zero 2 W, it will
**not boot** on this board — you need a fresh 32-bit image regardless of
whether the card itself still works.

The GPIO header and pin numbering are identical between the two boards, so
none of your wiring needs to change. Just expect things to feel slower
overall — boot time, menu responsiveness, everything — since this is a
single-core ARM11 @ 1GHz instead of a quad-core Cortex-A53 @ 1GHz. That's
expected, not a bug to chase.

---

## Phase 1 — Flash the OS

1. Download **Raspberry Pi Imager** on your computer.
2. Insert a microSD card (16GB+, Class 10/A1 or better).
3. In Imager:
   - **Device**: Raspberry Pi Zero W
   - **OS**: Raspberry Pi OS Lite **(32-bit)** — this is the critical
     choice; 64-bit will not boot on this board
   - **Storage**: your SD card
4. Click the gear icon before writing and set:
   - Hostname (e.g. `audiobookpi`)
   - Enable SSH with password auth (or your public key)
   - Wi-Fi SSID/password
   - Locale/timezone/keyboard layout
5. Write the image and boot the Pi.

## Phase 2 — Base system setup

SSH in once it's up (give it a minute or two longer than the Zero 2 W took):

```bash
ssh <username>@audiobookpi.local
sudo apt update && sudo apt full-upgrade -y
sudo raspi-config
```

In `raspi-config` → **Interface Options**, enable both:
- **SPI** (for the display)
- **I2C** (for the battery monitor)

Reboot, then SSH back in and install everything needed:

```bash
sudo apt install -y python3-pip python3-venv python3-dev \
  libjpeg-dev zlib1g-dev libfreetype6-dev fonts-dejavu-core \
  mpv libmpv-dev git ffmpeg alsa-utils \
  pipewire pipewire-audio wireplumber \
  swig liblgpio-dev i2c-tools
```

Enable persistent logging (worth having if anything ever needs debugging):

```bash
sudo mkdir -p /var/log/journal
sudo systemctl restart systemd-journald
```

Enable linger so PipeWire/audio come up on boot without needing a login session:

```bash
sudo loginctl enable-linger $USER
```

Set up the Python environment:

```bash
mkdir -p ~/audiobook-player && cd ~/audiobook-player
python3 -m venv venv
source venv/bin/activate
pip install luma.lcd gpiozero python-mpv mutagen Pillow spidev RPi.GPIO lgpio smbus2
```

If `lgpio` fails to build, this fixes it:
```bash
sudo apt install -y python3-lgpio
```

## Phase 3 — Wi-Fi toggle permission

The Settings screen's Wi-Fi toggle needs passwordless `sudo` for just the
`rfkill` command:

```bash
which rfkill   # note the path, usually /usr/sbin/rfkill
sudo visudo -f /etc/sudoers.d/audiobook-wifi
```

Add this line (adjust the path if `which rfkill` gave something different):
```
pi ALL=(ALL) NOPASSWD: /usr/sbin/rfkill
```

## Phase 4 — Wiring

Move all your existing wiring over unchanged — same GPIO numbers, same
physical pins. Reference table:

**TFT Display (SPI0):**
| Function | GPIO | Physical pin |
|---|---|---|
| MOSI | GPIO10 | 19 |
| SCLK | GPIO11 | 23 |
| CS (CE0) | GPIO8 | 24 |
| DC | GPIO24 | 18 |
| RST | GPIO25 | 22 |
| Backlight (PWM) | GPIO12 | 32 |

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

**Battery monitor (ADS1115 at I2C address 0x48):**
| Pin | Connects to |
|---|---|
| VDD | 3.3V |
| GND | GND |
| SDA | GPIO2 (pin 3) |
| SCL | GPIO3 (pin 5) |

Voltage divider: Battery+ → 10kΩ → junction → 20kΩ → GND, junction → ADS1115 AIN0.

**Audio (PCM5102A I2S DAC)** — the Pi's I2S hardware is fixed to these
exact pins, which is why Select/Down were moved off them above:
| PCM5102A Pin | Connects to |
|---|---|
| VCC | 3.3V |
| GND | GND |
| BCK | GPIO18 (physical pin 12) |
| LCK | GPIO19 (physical pin 35) |
| DIN | GPIO21 (physical pin 40) |
| SCK | GND (ties the chip to its internal PLL clock) |

Add to `/boot/firmware/config.txt`:
```
dtparam=audio=off
dtoverlay=hifiberry-dac
```

**Also uncomment the existing `#dtparam=i2s=on` line near the top of the
file** (remove the `#`). This is easy to miss and causes a specific,
confusing failure: the `hifiberry-dac` overlay tells the system *which
codec* to use, but `dtparam=i2s=on` is what enables the I2S hardware
interface itself. Without it, the codec driver never even gets a chance to
probe, and `dmesg` will show zero related messages at all — the overlay
sits there in the config file doing nothing.

Reboot after saving. Verify with `aplay -l` (should show `sndrpihifiberry`)
and `wpctl status` (should appear as a sink and become default).

## Phase 5 — Deploy the code

Download and unzip the attached `audiobook-player.zip`, then copy the whole
folder to the Pi:

```bash
scp -r audiobook-player <username>@audiobookpi.local:~/
```

Re-activate the venv and confirm imports work:

```bash
cd ~/audiobook-player
source venv/bin/activate
python -c "import luma.lcd, gpiozero, mpv, mutagen, PIL, RPi.GPIO, lgpio, smbus2; print('all imports OK')"
```

## Phase 6 — Isolated hardware tests

Test each piece before trusting the full app, same as the original build:

```bash
python test_display_tft.py   # should show colored shapes, text, moving box
python test_buttons.py       # press each button, confirm correct name prints
python test_haptics.py       # should feel 3 buzzes then a quick double-click
python test_battery.py       # should show voltage close to a multimeter reading
```

Fix anything that doesn't check out here before moving on — much easier to
debug one piece at a time than inside the full app.

## Phase 7 — Set up audiobooks and confirm playback

```bash
mkdir -p ~/audiobook-player/audiobooks
```

Copy at least one `.m4b` or `.mp3` file in (via `scp`), then:

```bash
python player.py
```

Confirm you see the Main Menu, can open the library, play a book, and hear
audio through the PCM5102A DAC.

## Phase 8 — Boot splash service

```bash
sudo nano /etc/systemd/system/audiobook-splash.service
```

```ini
[Unit]
Description=Audiobook Player Boot Splash
DefaultDependencies=no
After=local-fs.target
Before=audiobook-player.service

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 2
ExecStart=/home/pi/audiobook-player/venv/bin/python /home/pi/audiobook-player/splash.py
RemainAfterExit=no

[Install]
WantedBy=sysinit.target
```

## Phase 9 — Main player autostart service

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

(If your username isn't `pi`, update `User=` and every `/home/pi/...` path
in both service files above.)

Enable both and do a full cold-boot test:

```bash
sudo systemctl daemon-reload
sudo systemctl enable audiobook-splash.service
sudo systemctl enable audiobook-player.service
sudo reboot
```

Watch the display through the whole boot: splash screen should appear
within a couple seconds, hold through the slower audio/network startup,
then the Main Menu should take over automatically with no login needed.

## Phase 10 — Final checklist

**Before you get here**: avoid opening the Settings screen while you're
still debugging buttons or wiring. A stray/erratic button press during
unrelated hardware debugging can accidentally toggle Wi-Fi off — and unlike
most app state, that block is saved by the OS itself and persists across
reboots, potentially locking you out of SSH access with no easy way back in
except a monitor and keyboard plugged in directly. Confirm buttons behave
correctly first, then it's safe to explore Settings.

- [ ] Main Menu appears on boot with no manual steps
- [ ] Audiobooks play, chapters navigate, resume works
- [ ] Volume, skip forward/back work and are adjustable in Settings
- [ ] Backlight brightness adjustable in Settings
- [ ] Battery percentage shows on Now Playing and in Settings
- [ ] Haptic buzz on every button press
- [ ] Wi-Fi toggle in Settings actually disables/enables the radio

If everything on that list checks out, you're fully back up and running.
