"""Persistence for resume positions and bookmarks, backed by a JSON file."""
import json
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List

import config


@dataclass
class Bookmark:
    label: str
    position: float


@dataclass
class BookState:
    position: float = 0.0
    chapter: int = 0
    finished: bool = False
    bookmarks: List[Bookmark] = field(default_factory=list)


class StateStore:
    """Thread-safe JSON-backed state for all books, keyed by file path."""

    def __init__(self, path=config.STATE_FILE):
        self._path = path
        self._lock = threading.Lock()
        self._data: Dict[str, BookState] = {}
        self._load()

    def _load(self):
        if not self._path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            raw = {}
        self._data = {}
        for key, val in raw.items():
            bookmarks = [Bookmark(**b) for b in val.get("bookmarks", [])]
            self._data[key] = BookState(
                position=val.get("position", 0.0),
                chapter=val.get("chapter", 0),
                finished=val.get("finished", False),
                bookmarks=bookmarks,
            )

    def save(self):
        with self._lock:
            serializable = {
                key: {
                    "position": bs.position,
                    "chapter": bs.chapter,
                    "finished": bs.finished,
                    "bookmarks": [asdict(b) for b in bs.bookmarks],
                }
                for key, bs in self._data.items()
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(serializable, indent=2))
            tmp.replace(self._path)

    def get(self, book_path: str) -> BookState:
        with self._lock:
            return self._data.setdefault(book_path, BookState())

    def update_progress(self, book_path: str, position: float, chapter: int):
        with self._lock:
            bs = self._data.setdefault(book_path, BookState())
            bs.position = position
            bs.chapter = chapter

    def add_bookmark(self, book_path: str, position: float, label: str = None):
        with self._lock:
            bs = self._data.setdefault(book_path, BookState())
            label = label or f"Bookmark {len(bs.bookmarks) + 1}"
            bs.bookmarks.append(Bookmark(label=label, position=position))
        self.save()

    def remove_bookmark(self, book_path: str, index: int):
        with self._lock:
            bs = self._data.setdefault(book_path, BookState())
            if 0 <= index < len(bs.bookmarks):
                bs.bookmarks.pop(index)
        self.save()

    def mark_finished(self, book_path: str, finished: bool = True):
        with self._lock:
            bs = self._data.setdefault(book_path, BookState())
            bs.finished = finished


class SettingsStore:
    """Tiny JSON-backed store for global settings: volume, Wi-Fi, and any
    future toggles (backlight, sleep timer, auto power off, ...)."""

    def __init__(self, path=config.SETTINGS_FILE):
        self._path = path
        self._lock = threading.Lock()
        self._data = {"volume": config.DEFAULT_VOLUME}
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            if isinstance(data, dict):
                self._data.update(data)
        except (json.JSONDecodeError, OSError):
            pass

    def get_volume(self) -> int:
        return int(self._data.get("volume", config.DEFAULT_VOLUME))

    def set_volume(self, volume: int):
        with self._lock:
            self._data["volume"] = max(0, min(config.MAX_VOLUME, volume))
            self._path.write_text(json.dumps(self._data))

    def get_setting(self, key: str, default=False):
        return self._data.get(key, default)

    def set_setting(self, key: str, value):
        with self._lock:
            self._data[key] = value
            self._path.write_text(json.dumps(self._data))
