"""Sends screen state to the RP2040 display co-processor over UART, instead
of drawing locally -- the Pi no longer touches the TFT hardware at all.
Function names/shapes intentionally mirror the old local-drawing display.py
so player.py's calls stay recognizable, just without a `draw` parameter."""
import serial

import config

_ser = None


def _get_serial():
    global _ser
    if _ser is None:
        _ser = serial.Serial(config.DISPLAY_UART_PORT, baudrate=config.DISPLAY_UART_BAUD, timeout=0.1)
    return _ser


def _send(line: str):
    try:
        _get_serial().write((line + "\n").encode())
    except Exception:
        pass  # display link issues shouldn't crash playback


def _sanitize(text: str) -> str:
    return text.replace("|", " ").replace("~", " ").replace("\n", " ")


def _send_list(selected_index, items):
    safe_items = [_sanitize(item) for item in items]
    _send(f"LIST|{selected_index}|{'~'.join(safe_items)}")


def _format_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def draw_main_menu(items, selected_index):
    _send_list(selected_index, items)


def draw_library_list(books, selected_index):
    titles = [b.title for b in books] or ["No audiobooks found"]
    _send_list(selected_index, titles)


def draw_chapter_list(chapters, selected_index):
    titles = [c.title for c in chapters] or ["No chapter data"]
    _send_list(selected_index, titles)


def draw_bookmark_list(bookmarks, selected_index):
    items = [f"{b.label} ({_format_time(b.position)})" for b in bookmarks] or ["No bookmarks yet"]
    _send_list(selected_index, items)


def draw_settings_list(rows, selected_index, editing=False):
    # rows: list of (label, value_str, is_on). Pre-pad here so values still
    # line up on the RP2040's fixed-width font, since we're sending plain
    # text rather than structured layout data. (Editing highlight color and
    # on/off color-coding are dropped in this first version -- everything
    # renders as a plain list for now.)
    items = []
    for idx, (label, value, _is_on) in enumerate(rows):
        display_value = f"< {value} >" if editing and idx == selected_index else value
        pad = max(1, 19 - len(label) - len(display_value))
        items.append(f"{label}{' ' * pad}{display_value}")
    _send_list(selected_index, items)


def draw_now_playing(book, position, duration, chapter_title, chapter_index,
                      chapter_count, is_paused, volume, battery_percent=None):
    battery = battery_percent if battery_percent is not None else -1
    _send(
        f"NOWPLAYING|{_sanitize(book.title)}|{_sanitize(chapter_title)}|"
        f"{chapter_index}|{chapter_count}|{position:.1f}|{duration:.1f}|"
        f"{1 if is_paused else 0}|{volume}|{battery}"
    )


def set_backlight(percent: int):
    _send(f"BACKLIGHT|{percent}")


def draw_loading(title: str):
    _send(f"LOADING|{_sanitize(title)}")


_rx_buffer = b""


def send_bt_at(command: str):
    """Sends an AT command to be relayed to the BT module by the RP2040
    (the Pi has no free hardware UART of its own for this)."""
    _send(f"BTAT|{_sanitize(command)}")


def poll_bt_response():
    """Non-blocking: returns the next BT module response line if one has
    arrived over the shared UART link, or None. The RP2040 tags these
    'BTRESP|...' so they're never confused with its own (nonexistent)
    outgoing screen traffic -- we only ever send to it, never receive,
    except for this one case."""
    global _rx_buffer
    try:
        ser = _get_serial()
        if ser.in_waiting:
            _rx_buffer += ser.read(ser.in_waiting)
    except Exception:
        return None
    while b"\n" in _rx_buffer:
        line, _rx_buffer = _rx_buffer.split(b"\n", 1)
        text = line.decode(errors="ignore").strip()
        if text.startswith("BTRESP|"):
            return text[len("BTRESP|"):]
    return None
