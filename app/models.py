from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Track:
    title: str
    artist: str
    album: str | None = None
    release_date: str | None = None
    duration_ms: int | None = None
    image_url: str | None = None
    spotify_url: str | None = None
    youtube_url: str | None = None
    preview_url: str | None = None
    isrc: str | None = None
    source: str = "unknown"
    telegram_file_id: str | None = None
    local_path: str | None = None

    @property
    def query(self) -> str:
        return f"{self.artist} - {self.title}".strip(" -")

    @property
    def key(self) -> str:
        return f"{self.artist.lower().strip()}::{self.title.lower().strip()}"
