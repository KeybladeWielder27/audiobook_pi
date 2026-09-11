"""Scans the audiobooks directory for books. Two layouts are supported:

  audiobooks/My Book.m4b          -- single file, embedded chapters (m4b)
  audiobooks/My Short Story.mp3   -- single file, no/rare embedded chapters
  audiobooks/My Long Book/        -- folder = one book, each .mp3 inside is
      01 - Chapter One.mp3           treated as one chapter, played as a
      02 - Chapter Two.mp3           gapless mpv playlist
      ...
"""
import json
import re
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List

from mutagen import File as MutagenFile

import config


@dataclass
class Chapter:
    title: str
    start: float = 0.0  # only meaningful for single-file embedded chapters


@dataclass
class Book:
    path: str          # unique id: file path for single-file, folder path for multi-file
    title: str
    author: str
    duration: float
    kind: str = "single"          # "single" or "multi"
    chapters: List[Chapter] = field(default_factory=list)
    files: List[str] = field(default_factory=list)  # chapter file paths, multi-file only

    @property
    def filename(self):
        return Path(self.path).name


def _natural_sort_key(path: Path):
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", path.name)]


def _read_tags(path: Path):
    """Generic tag reader that works across m4b (MP4 atoms) and mp3 (ID3),
    via mutagen's format-agnostic 'easy' interface."""
    title, author, duration = path.stem, "Unknown", 0.0
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None:
            if audio.tags:
                t = audio.tags.get("title")
                a = audio.tags.get("artist") or audio.tags.get("albumartist")
                if t:
                    title = str(t[0])
                if a:
                    author = str(a[0])
            if audio.info:
                duration = float(audio.info.length)
    except Exception:
        pass
    return title, author, duration


def _read_chapters(path: Path) -> List[Chapter]:
    """Uses ffprobe to pull an embedded chapter table (m4b always has one;
    mp3 rarely does, in which case this just returns an empty list)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_chapters", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        chapters = []
        for ch in data.get("chapters", []):
            title = ch.get("tags", {}).get("title", f"Chapter {len(chapters) + 1}")
            start = float(ch.get("start_time", 0.0))
            chapters.append(Chapter(title=title, start=start))
        return chapters
    except Exception:
        return []


def _build_single_book(path: Path, cache: dict) -> Book:
    key = str(path)
    mtime = path.stat().st_mtime
    cached = cache.get(key)
    if cached and cached.get("mtime") == mtime and cached.get("book", {}).get("kind") == "single":
        b = cached["book"]
        return Book(
            path=b["path"], title=b["title"], author=b["author"], duration=b["duration"],
            kind="single", chapters=[Chapter(**c) for c in b["chapters"]],
        )
    title, author, duration = _read_tags(path)
    chapters = _read_chapters(path)
    return Book(path=key, title=title, author=author, duration=duration, kind="single", chapters=chapters)


def _build_multi_book(folder: Path, mp3_files: List[Path], cache: dict) -> Book:
    key = str(folder)
    mtime = folder.stat().st_mtime
    cached = cache.get(key)
    if cached and cached.get("mtime") == mtime and cached.get("book", {}).get("kind") == "multi":
        b = cached["book"]
        return Book(
            path=b["path"], title=b["title"], author=b["author"], duration=b["duration"],
            kind="multi", chapters=[Chapter(**c) for c in b["chapters"]], files=b["files"],
        )

    chapters = []
    total_duration = 0.0
    author = "Unknown"
    for f in mp3_files:
        ch_title, ch_author, ch_duration = _read_tags(f)
        chapters.append(Chapter(title=ch_title))
        total_duration += ch_duration
        if author == "Unknown" and ch_author != "Unknown":
            author = ch_author

    title = folder.name
    return Book(
        path=key, title=title, author=author, duration=total_duration, kind="multi",
        chapters=chapters, files=[str(f) for f in mp3_files],
    )


def scan_library(directory: Path = config.LIBRARY_DIR, use_cache: bool = True) -> List[Book]:
    directory.mkdir(parents=True, exist_ok=True)
    cache = {}
    if use_cache and config.LIBRARY_CACHE_FILE.exists():
        try:
            cache = json.loads(config.LIBRARY_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            cache = {}

    books = []
    fresh_cache = {}

    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix.lower() in (".m4b", ".mp3"):
            book = _build_single_book(entry, cache)
        elif entry.is_dir():
            mp3_files = sorted(entry.glob("*.mp3"), key=_natural_sort_key)
            if not mp3_files:
                continue
            book = _build_multi_book(entry, mp3_files, cache)
        else:
            continue

        books.append(book)
        fresh_cache[book.path] = {
            "mtime": entry.stat().st_mtime,
            "book": {
                "path": book.path, "title": book.title, "author": book.author,
                "duration": book.duration, "kind": book.kind,
                "chapters": [asdict(c) for c in book.chapters],
                "files": book.files,
            },
        }

    config.LIBRARY_CACHE_FILE.write_text(json.dumps(fresh_cache, indent=2))
    return books
