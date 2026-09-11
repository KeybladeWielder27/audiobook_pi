"""Central configuration: GPIO pins, paths, constants."""
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = BASE_DIR / "audiobooks"
STATE_FILE = BASE_DIR / "state.json"
LIBRARY_CACHE_FILE = BASE_DIR / "library_cache.json"

# --- Display (RP2040 co-processor over UART -- Pi no longer drives the TFT directly) ---
DISPLAY_UART_PORT = "/dev/serial0"
DISPLAY_UART_BAUD = 115200

# --- Ready signal (tells the RP2040 whether player.py is actually running) ---
READY_GPIO = 24

# --- Buttons (BCM numbering) ---
BUTTON_PINS = {
    "menu": 5,
    "up": 6,
    "down": 27,
    "select": 17,
    "play_pause": 26,
    "next_chapter": 16,
    "prev_chapter": 20,
    "volume_up": 22,
    "volume_down": 23,
}

LONG_PRESS_SECONDS = 0.8

# --- Playback ---
AUTOSAVE_INTERVAL_SECONDS = 10  # how often to persist playback position while playing
RENDER_INTERVAL_SECONDS = 0.5  # throttle idle redraws; button presses still redraw immediately
DEFAULT_VOLUME = 70
VOLUME_STEP = 5
MAX_VOLUME = 130
SETTINGS_FILE = BASE_DIR / "settings.json"
SKIP_FORWARD_SECONDS = 30
SKIP_BACK_SECONDS = 15
SKIP_STEP = 5
SKIP_MIN = 5
SKIP_MAX = 120

# --- Backlight (PWM on GPIO12, freed up from the old PWM audio circuit) ---
BACKLIGHT_GPIO = 12
BACKLIGHT_PWM_FREQ = 1000
BACKLIGHT_MIN = 10  # floor so the screen can never go fully unreadable-dark

# --- Haptic feedback motor (GPIO13, also freed from the old audio circuit) ---
HAPTIC_GPIO = 13
HAPTIC_PULSE_SECONDS = 0.12

# --- Battery monitoring (ADS1115 ADC + voltage divider on AIN0) ---
BATTERY_POLL_INTERVAL_SECONDS = 5

# --- Display ---
FONT_PATH_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
