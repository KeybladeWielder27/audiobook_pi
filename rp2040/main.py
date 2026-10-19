"""Main firmware for the RP2040 display co-processor. Receives screen state
over UART from the Pi and renders it to the ST7789 -- the Pi no longer
touches the display hardware directly at all.
"""
import framebuf
from machine import Pin, SPI, UART, PWM
import time

from st7789_mini import ST7789

WIDTH = 320
HEIGHT = 240

bl = PWM(Pin(7))
bl.freq(1000)
bl.duty_u16(65535)

spi = SPI(0, baudrate=32_000_000, sck=Pin(2), mosi=Pin(3))
display = ST7789(spi, Pin(5), Pin(4), Pin(6), width=WIDTH, height=HEIGHT)

buf = bytearray(WIDTH * HEIGHT * 2)
fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.RGB565)

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
ready_pin = Pin(10, Pin.IN, Pin.PULL_DOWN)

# UART1: bridge to the KCX_BT_EMITTER module (via a 3.3V<->5V level shifter).
# Baud rate should match whatever the module actually uses -- 9600 is the
# common default for this class of AT-command BT module, adjust if needed.
bt_uart = UART(1, baudrate=9600, tx=Pin(8), rx=Pin(9))


def rgb(r, g, b):
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((val & 0xFF) << 8) | (val >> 8)


WHITE = rgb(255, 255, 255)
BLACK = rgb(0, 0, 0)
ACCENT = rgb(30, 144, 255)  # dodgerblue, matches the Pi UI's accent color
DIM = rgb(136, 146, 160)

# Small scratch buffer used to render text at 1x before scaling it up --
# sized for the longest string we'll ever draw in one call.
_SCRATCH_CHARS = 40
_scratch_buf = bytearray(_SCRATCH_CHARS * 8 * 8 // 8)
_scratch_fb = framebuf.FrameBuffer(_scratch_buf, _SCRATCH_CHARS * 8, 8, framebuf.MONO_HLSB)


def text_scaled(text, x, y, color, scale=2):
    """Draws text using the built-in 8x8 font blown up by `scale`, since
    MicroPython's framebuf.text() has no size parameter of its own."""
    text = text[:_SCRATCH_CHARS]
    _scratch_fb.fill(0)
    _scratch_fb.text(text, 0, 0, 1)
    w = len(text) * 8
    for ty in range(8):
        for tx in range(w):
            if _scratch_fb.pixel(tx, ty):
                fb.fill_rect(x + tx * scale, y + ty * scale, scale, scale, color)


def text_width(text, scale=2):
    return len(text) * 8 * scale


ROW_HEIGHT = 44  # tall enough for up to 2 wrapped lines per item
TEXT_SCALE = 2
CHAR_W = 8 * TEXT_SCALE
MAX_CHARS_PER_ROW = WIDTH // CHAR_W  # ~20 at scale 2


def format_time(seconds):
    seconds = int(seconds) if seconds > 0 else 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return "{}:{:02d}:{:02d}".format(h, m, s)
    return "{}:{:02d}".format(m, s)


def draw_list(selected_index, items):
    fb.fill(BLACK)
    visible_rows = HEIGHT // ROW_HEIGHT
    top = 0
    if selected_index >= visible_rows:
        top = selected_index - visible_rows + 1
    for row, idx in enumerate(range(top, min(len(items), top + visible_rows))):
        y = row * ROW_HEIGHT
        lines = wrap_text(items[idx], MAX_CHARS_PER_ROW, max_lines=2)
        if idx == selected_index:
            fb.fill_rect(0, y, WIDTH, ROW_HEIGHT, ACCENT)
            text_color = BLACK
        else:
            text_color = WHITE
        ty = y + 6
        for line in lines:
            text_scaled(line, 6, ty, text_color, TEXT_SCALE)
            ty += 18
    display.blit(buf)


def wrap_text(text, max_chars, max_lines=2):
    """Wraps text to whole words, up to max_lines. If there's leftover text
    beyond that, the last line is truncated with an ellipsis."""
    words = text.split()
    lines = []
    current = ""
    i = 0
    while i < len(words) and len(lines) < max_lines:
        word = words[i]
        candidate = current + (" " if current else "") + word
        if len(candidate) <= max_chars:
            current = candidate
            i += 1
        elif current:
            lines.append(current)
            current = ""
        else:
            # a single word longer than the whole line width
            lines.append(word[:max_chars])
            i += 1
    if current:
        lines.append(current)
    if i < len(words) and lines:
        last = lines[-1]
        if len(last) > max_chars - 3:
            last = last[:max_chars - 3]
        lines[-1] = last + "..."
    return lines


def draw_now_playing(title, chapter_title, chapter_index, chapter_count,
                      position, duration, is_paused, volume, battery):
    fb.fill(BLACK)

    title_lines = wrap_text(title, MAX_CHARS_PER_ROW, max_lines=2)
    y = 8
    for line in title_lines:
        text_scaled(line, 8, y, WHITE, TEXT_SCALE)
        y += 18

    chapter_y = y + 10
    ch_line = "Ch {}/{}: {}".format(chapter_index + 1, max(chapter_count, 1), chapter_title)
    text_scaled(ch_line[:MAX_CHARS_PER_ROW], 8, chapter_y, DIM, TEXT_SCALE)

    bar_y = chapter_y + 34
    bar_h = 16
    bar_w = WIDTH - 16
    fb.rect(8, bar_y, bar_w, bar_h, DIM)
    if duration > 0:
        fill_w = int(bar_w * min(1.0, position / duration))
        fb.fill_rect(8, bar_y, fill_w, bar_h, ACCENT)

    time_text = "{} / {}".format(format_time(position), format_time(duration))
    text_scaled(time_text, 8, bar_y + 26, WHITE, TEXT_SCALE)

    status = "Paused" if is_paused else "Playing"
    status_color = DIM if is_paused else ACCENT
    row2_y = bar_y + 56
    text_scaled("Vol {}%".format(volume), 8, row2_y, WHITE, TEXT_SCALE)
    if battery >= 0:
        text_scaled("Batt {}%".format(battery), 8, row2_y + 28, DIM, TEXT_SCALE)
    text_scaled(status, WIDTH - text_width(status, TEXT_SCALE) - 8, row2_y, status_color, TEXT_SCALE)

    display.blit(buf)


def set_backlight(percent):
    percent = max(0, min(100, percent))
    bl.duty_u16(int(percent / 100 * 65535))


SPRITE_SIZE = 60


def load_sprite(filename):
    with open(filename, "rb") as f:
        data = bytearray(f.read())
    return framebuf.FrameBuffer(data, SPRITE_SIZE, SPRITE_SIZE, framebuf.RGB565)


sprites = [
    load_sprite("sprite_frame1.bin"),
    load_sprite("sprite_frame2.bin"),
    load_sprite("sprite_frame3.bin"),
]

_runner_x = WIDTH
_runner_frame = 0
_runner_last_step = 0


def draw_splash():
    fb.fill(WHITE)
    text_scaled("Audiobook Player", 30, 60, BLACK, TEXT_SCALE)
    text_scaled("waiting...", 30, 90, DIM, TEXT_SCALE)
    fb.blit(sprites[_runner_frame], _runner_x, 150)
    display.blit(buf)


def draw_loading(title):
    fb.fill(BLACK)
    lines = wrap_text(title, MAX_CHARS_PER_ROW, max_lines=2)
    y = 90
    for line in lines:
        text_scaled(line, 8, y, WHITE, TEXT_SCALE)
        y += 18
    text_scaled("Loading...", 8, y + 10, ACCENT, TEXT_SCALE)
    display.blit(buf)


def step_runner():
    global _runner_x, _runner_frame
    _runner_x -= 8
    _runner_frame = (_runner_frame + 1) % len(sprites)
    if _runner_x < -SPRITE_SIZE:
        _runner_x = WIDTH
    draw_splash()


print("Ready, listening for screen updates...")
draw_splash()
was_ready = False
rx_buf = b""
bt_rx_buf = b""
while True:
    is_ready = ready_pin.value() == 1
    if is_ready and not was_ready:
        print("Pi is ready")
    elif was_ready and not is_ready:
        print("Pi is no longer ready -- showing splash")
        draw_splash()
    was_ready = is_ready

    if not is_ready:
        now = time.ticks_ms()
        if time.ticks_diff(now, _runner_last_step) > 120:
            step_runner()
            _runner_last_step = now

    if uart.any():
        rx_buf += uart.read()
        while b"\n" in rx_buf:
            line, rx_buf = rx_buf.split(b"\n", 1)
            if not is_ready:
                continue  # ignore any stray/stale messages while the Pi isn't running
            try:
                text = line.decode().strip()
                if not text:
                    continue
                parts = text.split("|")
                cmd = parts[0]
                if cmd == "LIST":
                    selected_index = int(parts[1])
                    items = parts[2].split("~") if parts[2] else []
                    draw_list(selected_index, items)
                elif cmd == "NOWPLAYING":
                    (_, title, chapter_title, chapter_index, chapter_count,
                     position, duration, is_paused, volume, battery) = parts
                    draw_now_playing(
                        title, chapter_title, int(chapter_index), int(chapter_count),
                        float(position), float(duration), is_paused == "1",
                        int(volume), int(battery),
                    )
                elif cmd == "BACKLIGHT":
                    set_backlight(int(parts[1]))
                elif cmd == "LOADING":
                    draw_loading(parts[1])
                elif cmd == "BTAT":
                    # Relay an AT command from the Pi out to the BT module.
                    # parts[1] is the raw command text, e.g. "AT+GMR?"
                    print("BTAT received from Pi:", parts[1])
                    bt_uart.write((parts[1] + "\r\n").encode())
                    print("Wrote to bt_uart (UART1)")
            except Exception as e:
                print("Error handling message:", e)

    # Relay anything the BT module sends back to the Pi, tagged so
    # display.py can tell it apart from its own screen-update traffic.
    if bt_uart.any():
        bt_rx_buf += bt_uart.read()
        print("bt_uart raw buffer so far:", bt_rx_buf)
        while b"\n" in bt_rx_buf:
            resp_line, bt_rx_buf = bt_rx_buf.split(b"\n", 1)
            resp_text = resp_line.decode().strip()
            if resp_text:
                print("Relaying BT module response to Pi:", resp_text)
                uart.write(("BTRESP|" + resp_text + "\n").encode())

    time.sleep_ms(10)
