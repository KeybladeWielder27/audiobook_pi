"""Main entry point: menu state machine tying display, input, playback, library together."""
import faulthandler
import signal
import time
from enum import Enum, auto

import battery_monitor
import config
import device_settings
import display
import haptics
import library
from gpiozero import DigitalOutputDevice
from input import InputManager
from playback import Playback
from state import StateStore, SettingsStore

# Lets us dump a full stack trace of every thread on demand (kill -SIGUSR1 <pid>)
# without killing the process -- essential for diagnosing hangs when running
# headless under systemd, where there's no terminal to Ctrl+C.
faulthandler.enable()
faulthandler.register(signal.SIGUSR1)


class Screen(Enum):
    MAIN_MENU = auto()
    LIBRARY_LIST = auto()
    NOW_PLAYING = auto()
    CHAPTER_LIST = auto()
    BOOKMARK_LIST = auto()
    SETTINGS_LIST = auto()


class App:
    def __init__(self):
        self.input = InputManager()
        self.ready_signal = DigitalOutputDevice(config.READY_GPIO)
        self.ready_signal.on()
        self.state = StateStore()
        self.settings = SettingsStore()
        self.playback = Playback()
        self.playback.volume = self.settings.get_volume()

        self.books = library.scan_library()
        self.screen = Screen.MAIN_MENU
        self.main_menu_items = ["Audiobooks", "Settings"]
        self.main_menu_selected_index = 0
        self.selected_index = 0
        self.chapter_selected_index = 0
        self.bookmark_selected_index = 0
        self.settings_selected_index = 0
        self.settings_editing = False
        self._battery_cache = None
        self._last_battery_check = 0.0

        # Each entry backs one row on the settings screen.
        # type "toggle": get/set wire it to a real hardware action (see
        #   device_settings.py); leave both None for a setting that's
        #   stored but not yet implemented (e.g. backlight, sleep timer).
        # type "number": min/max/step/default control how Up/Down adjust
        #   the value once the row is opened for editing with Select.
        self.setting_defs = [
            {"id": "wifi", "label": "Wi-Fi", "type": "toggle",
             "get": device_settings.get_wifi_enabled, "set": device_settings.set_wifi_enabled},
            {"id": "skip_forward", "label": "Skip forward", "type": "number",
             "min": config.SKIP_MIN, "max": config.SKIP_MAX, "step": config.SKIP_STEP,
             "default": config.SKIP_FORWARD_SECONDS, "unit": "s", "get": None, "set": None},
            {"id": "skip_back", "label": "Skip back", "type": "number",
             "min": config.SKIP_MIN, "max": config.SKIP_MAX, "step": config.SKIP_STEP,
             "default": config.SKIP_BACK_SECONDS, "unit": "s", "get": None, "set": None},
            {"id": "backlight", "label": "Backlight", "type": "number",
             "min": config.BACKLIGHT_MIN, "max": 100, "step": 10,
             "default": 100, "unit": "%", "get": None, "set": device_settings.set_backlight_brightness},
            {"id": "sleep_timer", "label": "Sleep timer", "type": "toggle", "get": None, "set": None},
            {"id": "auto_off", "label": "Auto power off", "type": "toggle", "get": None, "set": None},
            {"id": "battery", "label": "Battery", "type": "info", "read": self._read_battery_display},
        ]
        # Sync stored preferences with real hardware state at startup, in
        # case something changed the radio outside the app since last run.
        for sd in self.setting_defs:
            if sd.get("get") is not None:
                self.settings.set_setting(sd["id"], sd["get"]())

        # Backlight has no external state to sync from (unlike Wi-Fi), so
        # instead we push the last saved brightness out to the hardware.
        device_settings.set_backlight_brightness(self.settings.get_setting("backlight", 100))
        self.current_book = None
        self._last_autosave = time.monotonic()
        self._last_render = 0.0

    def _read_battery_display(self):
        return battery_monitor.format_battery(self._battery_cache)

    # --- screen transitions ---

    def _open_book(self, book):
        self.current_book = book
        book_state = self.state.get(book.path)
        if book.kind == "multi":
            # Each file is a chapter, so the saved chapter index selects
            # which file to start on, then we seek within that file.
            self.playback.load_playlist(
                book.files, start_index=book_state.chapter, start_position=book_state.position
            )
        else:
            # Seeking to the saved absolute position is enough here -- mpv
            # derives the correct embedded chapter from playback position
            # automatically. Do NOT also call jump_to_chapter(): setting
            # mpv's chapter property triggers its own seek to that chapter's
            # start, which would silently overwrite the position seek above.
            self.playback.load_single(book.path, start_position=book_state.position)
        self.screen = Screen.NOW_PLAYING

    def _close_book_to_library(self):
        if self.current_book:
            self.state.update_progress(
                self.current_book.path, self.playback.position, self.playback.chapter_index
            )
            self.state.save()
        self.playback.stop()
        self.current_book = None
        self.screen = Screen.LIBRARY_LIST

    # --- input handling ---

    def handle_event(self, name, kind):
        if self.screen == Screen.MAIN_MENU:
            self._handle_main_menu_input(name, kind)
        elif self.screen == Screen.LIBRARY_LIST:
            self._handle_library_input(name, kind)
        elif self.screen == Screen.NOW_PLAYING:
            self._handle_now_playing_input(name, kind)
        elif self.screen == Screen.CHAPTER_LIST:
            self._handle_chapter_list_input(name, kind)
        elif self.screen == Screen.BOOKMARK_LIST:
            self._handle_bookmark_list_input(name, kind)
        elif self.screen == Screen.SETTINGS_LIST:
            self._handle_settings_input(name, kind)

    def _handle_main_menu_input(self, name, kind):
        items = self.main_menu_items
        if name == "up":
            self.main_menu_selected_index = (self.main_menu_selected_index - 1) % len(items)
        elif name == "down":
            self.main_menu_selected_index = (self.main_menu_selected_index + 1) % len(items)
        elif name == "select":
            choice = items[self.main_menu_selected_index]
            if choice == "Audiobooks":
                self.selected_index = 0
                self.screen = Screen.LIBRARY_LIST
            elif choice == "Settings":
                self.settings_selected_index = 0
                self.screen = Screen.SETTINGS_LIST

    def _handle_library_input(self, name, kind):
        if name == "menu":
            self.screen = Screen.MAIN_MENU
            return
        if not self.books:
            return
        if name == "up":
            self.selected_index = (self.selected_index - 1) % len(self.books)
        elif name == "down":
            self.selected_index = (self.selected_index + 1) % len(self.books)
        elif name == "select":
            self._open_book(self.books[self.selected_index])

    def _handle_now_playing_input(self, name, kind):
        if name == "play_pause":
            self.playback.toggle_pause()
        elif name == "next_chapter":
            self.playback.next_chapter()
        elif name == "prev_chapter":
            self.playback.prev_chapter()
        elif name == "up":
            step = self.settings.get_setting("skip_forward", config.SKIP_FORWARD_SECONDS)
            self.playback.seek_relative(step)
        elif name == "down":
            step = self.settings.get_setting("skip_back", config.SKIP_BACK_SECONDS)
            self.playback.seek_relative(-step)
        elif name == "volume_up":
            self.playback.volume += config.VOLUME_STEP
            self.settings.set_volume(self.playback.volume)
        elif name == "volume_down":
            self.playback.volume -= config.VOLUME_STEP
            self.settings.set_volume(self.playback.volume)
        elif name == "menu" and kind == "short":
            self._close_book_to_library()
        elif name == "menu" and kind == "long":
            self.bookmark_selected_index = 0
            self.screen = Screen.BOOKMARK_LIST
        elif name == "select" and kind == "long":
            self.state.add_bookmark(self.current_book.path, self.playback.position)
        elif name == "select" and kind == "short":
            self.chapter_selected_index = self.playback.chapter_index
            self.screen = Screen.CHAPTER_LIST

    def _handle_chapter_list_input(self, name, kind):
        chapters = self.current_book.chapters
        if not chapters:
            if name == "menu":
                self.screen = Screen.NOW_PLAYING
            return
        if name == "up":
            self.chapter_selected_index = (self.chapter_selected_index - 1) % len(chapters)
        elif name == "down":
            self.chapter_selected_index = (self.chapter_selected_index + 1) % len(chapters)
        elif name == "select":
            self.playback.jump_to_chapter(self.chapter_selected_index)
            self.screen = Screen.NOW_PLAYING
        elif name == "menu":
            self.screen = Screen.NOW_PLAYING

    def _handle_settings_input(self, name, kind):
        defs = self.setting_defs
        current = defs[self.settings_selected_index]

        if self.settings_editing:
            # Up/Down adjust the value instead of moving the selection while
            # editing a numeric row; Select or Menu commits and exits.
            if name == "up":
                self._adjust_number_setting(current, +1)
            elif name == "down":
                self._adjust_number_setting(current, -1)
            elif name in ("select", "menu"):
                self.settings_editing = False
            return

        if name == "up":
            self.settings_selected_index = (self.settings_selected_index - 1) % len(defs)
        elif name == "down":
            self.settings_selected_index = (self.settings_selected_index + 1) % len(defs)
        elif name == "select":
            if current["type"] == "toggle":
                new_value = not self.settings.get_setting(current["id"], False)
                self.settings.set_setting(current["id"], new_value)
                if current.get("set") is not None:
                    current["set"](new_value)
            elif current["type"] == "number":
                self.settings_editing = True
        elif name == "menu":
            self.screen = Screen.MAIN_MENU

    def _adjust_number_setting(self, sd, direction):
        value = self.settings.get_setting(sd["id"], sd["default"])
        value = max(sd["min"], min(sd["max"], value + direction * sd["step"]))
        self.settings.set_setting(sd["id"], value)
        if sd.get("set") is not None:
            sd["set"](value)

    def _handle_bookmark_list_input(self, name, kind):
        bookmarks = self.state.get(self.current_book.path).bookmarks
        if not bookmarks:
            if name == "menu":
                self.screen = Screen.NOW_PLAYING
            return
        if name == "up":
            self.bookmark_selected_index = (self.bookmark_selected_index - 1) % len(bookmarks)
        elif name == "down":
            self.bookmark_selected_index = (self.bookmark_selected_index + 1) % len(bookmarks)
        elif name == "select" and kind == "short":
            self.playback.seek_to(bookmarks[self.bookmark_selected_index].position)
            self.screen = Screen.NOW_PLAYING
        elif name == "select" and kind == "long":
            self.state.remove_bookmark(self.current_book.path, self.bookmark_selected_index)
            bookmarks = self.state.get(self.current_book.path).bookmarks
            if self.bookmark_selected_index >= len(bookmarks):
                self.bookmark_selected_index = max(0, len(bookmarks) - 1)
        elif name == "menu":
            self.screen = Screen.NOW_PLAYING

    # --- rendering ---

    def render(self):
        if self.screen == Screen.MAIN_MENU:
            display.draw_main_menu(self.main_menu_items, self.main_menu_selected_index)
        elif self.screen == Screen.LIBRARY_LIST:
            display.draw_library_list(self.books, self.selected_index)
        elif self.screen == Screen.NOW_PLAYING and self.current_book:
            chapters = self.current_book.chapters
            idx = self.playback.chapter_index
            chapter_title = chapters[idx].title if idx < len(chapters) else "-"
            battery_percent = self._battery_cache[1] if self._battery_cache else None
            display.draw_now_playing(
                self.current_book, self.playback.position, self.playback.duration,
                chapter_title, idx, len(chapters), self.playback.is_paused, self.playback.volume,
                battery_percent=battery_percent,
            )
        elif self.screen == Screen.CHAPTER_LIST and self.current_book:
            display.draw_chapter_list(self.current_book.chapters, self.chapter_selected_index)
        elif self.screen == Screen.BOOKMARK_LIST and self.current_book:
            bookmarks = self.state.get(self.current_book.path).bookmarks
            display.draw_bookmark_list(bookmarks, self.bookmark_selected_index)
        elif self.screen == Screen.SETTINGS_LIST:
            rows = []
            for sd in self.setting_defs:
                if sd["type"] == "toggle":
                    value = self.settings.get_setting(sd["id"], False)
                    rows.append((sd["label"], "ON" if value else "OFF", value))
                elif sd["type"] == "number":
                    value = self.settings.get_setting(sd["id"], sd["default"])
                    rows.append((sd["label"], f"{value}{sd.get('unit', '')}", True))
                elif sd["type"] == "info":
                    rows.append((sd["label"], sd["read"](), True))
            display.draw_settings_list(rows, self.settings_selected_index, editing=self.settings_editing)

    # --- main loop ---

    def run(self):
        try:
            while True:
                event = self.input.poll(timeout=0.1)
                if event:
                    haptics.pulse()
                    self.handle_event(*event)

                now = time.monotonic()
                if now - self._last_battery_check > config.BATTERY_POLL_INTERVAL_SECONDS:
                    self._battery_cache = battery_monitor.read_battery()
                    self._last_battery_check = now

                if self.screen == Screen.NOW_PLAYING and self.current_book:
                    now = time.monotonic()
                    if now - self._last_autosave > config.AUTOSAVE_INTERVAL_SECONDS:
                        self.state.update_progress(
                            self.current_book.path, self.playback.position, self.playback.chapter_index
                        )
                        self.state.save()
                        self._last_autosave = now

                now = time.monotonic()
                if event or now - self._last_render > config.RENDER_INTERVAL_SECONDS:
                    self.render()
                    self._last_render = now
        except KeyboardInterrupt:
            import traceback
            traceback.print_exc()
        finally:
            if self.current_book:
                self.state.update_progress(
                    self.current_book.path, self.playback.position, self.playback.chapter_index
                )
            self.state.save()
            self.playback.shutdown()
            self.ready_signal.off()


if __name__ == "__main__":
    App().run()
