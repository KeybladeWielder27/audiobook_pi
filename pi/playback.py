"""Wraps python-mpv for playback in two modes:

  single-file: m4b or standalone mp3, using mpv's native embedded chapters
  multi-file:  a folder of mp3s loaded as an mpv playlist, where each
               playlist entry IS a chapter

Position/duration/pause always refer to the currently active file in either
mode, which keeps the Now Playing screen's progress bar meaningful in both
cases (progress within the current chapter's audio)."""
from typing import List

import mpv

import config


class Playback:
    def __init__(self):
        self._mpv = mpv.MPV(
            vid=False,
            ytdl=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
        )
        self._is_multi = False

    def load_single(self, path: str, start_position: float = 0.0):
        self._is_multi = False
        self._mpv.playlist_clear()
        self._mpv.play(path)
        self._mpv.wait_until_playing()
        if start_position > 0:
            self._mpv.seek(start_position, reference="absolute")

    def load_playlist(self, paths: List[str], start_index: int = 0, start_position: float = 0.0):
        self._is_multi = True
        self._mpv.playlist_clear()
        for p in paths:
            self._mpv.playlist_append(p)
        start_index = max(0, min(start_index, len(paths) - 1))
        self._mpv.playlist_play_index(start_index)
        self._mpv.wait_until_playing()
        if start_position > 0:
            self._mpv.seek(start_position, reference="absolute")

    def toggle_pause(self):
        self._mpv.pause = not self._mpv.pause

    @property
    def is_paused(self) -> bool:
        return bool(self._mpv.pause)

    @property
    def position(self) -> float:
        return self._mpv.time_pos or 0.0

    @property
    def duration(self) -> float:
        return self._mpv.duration or 0.0

    @property
    def chapter_index(self) -> int:
        if self._is_multi:
            return self._mpv.playlist_pos or 0
        return self._mpv.chapter or 0

    @property
    def chapter_count(self) -> int:
        if self._is_multi:
            return len(self._mpv.playlist or [])
        return len(self._mpv.chapter_list or [])

    def next_chapter(self):
        try:
            if self._is_multi:
                self._mpv.command("playlist-next", "weak")
            else:
                self._mpv.chapter = self.chapter_index + 1
        except Exception:
            pass

    def prev_chapter(self):
        try:
            if self._is_multi:
                self._mpv.command("playlist-prev", "weak")
            else:
                self._mpv.chapter = max(0, self.chapter_index - 1)
        except Exception:
            pass

    def jump_to_chapter(self, index: int):
        try:
            if self._is_multi:
                self._mpv.playlist_play_index(index)
            else:
                self._mpv.chapter = index
        except Exception:
            pass

    @property
    def volume(self) -> int:
        return int(self._mpv.volume or 0)

    @volume.setter
    def volume(self, value: int):
        self._mpv.volume = max(0, min(config.MAX_VOLUME, value))

    def seek_to(self, seconds: float):
        self._mpv.seek(seconds, reference="absolute")

    def seek_relative(self, delta_seconds: float):
        # mpv clamps at the start/end of the current file automatically, so
        # skipping past either edge is safe -- no bounds-checking needed here.
        self._mpv.seek(delta_seconds, reference="relative")

    def stop(self):
        # If paused, ALSA's drain-on-stop can hang indefinitely waiting for a
        # buffer that will never empty while the stream is paused. Resume
        # playback briefly so the stop/drain sequence can actually complete.
        if self._mpv.pause:
            self._mpv.pause = False
        self._mpv.stop()
        self._mpv.playlist_clear()
        self._is_multi = False

    def shutdown(self):
        self._mpv.terminate()
