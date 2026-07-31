from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True, frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    acr_host: str
    acr_access_key: str
    acr_access_secret: str
    spotify_client_id: str
    spotify_client_secret: str
    youtube_api_key: str
    database_path: Path
    temp_dir: Path
    search_limit: int
    max_media_mb: int
    music_dir: Path
    download_max_mb: int
    cookies_file: Path | None
    max_parallel_downloads: int
    request_cooldown: float
    mini_app_url: str
    web_host: str
    web_port: int

    @property
    def acr_enabled(self) -> bool:
        return bool(self.acr_host and self.acr_access_key and self.acr_access_secret)

    @property
    def spotify_enabled(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)

    @property
    def youtube_enabled(self) -> bool:
        return bool(self.youtube_api_key)


def _parse_admin_ids(raw: str) -> frozenset[int]:
    result: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError as exc:
            raise RuntimeError(f"ADMIN_IDS ichida noto'g'ri ID bor: {part}") from exc
    return frozenset(result)


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN .env faylida yo'q. .env.example nusxasini .env deb nomlang.")

    db_path = Path(os.getenv("DATABASE_PATH", "data/music_finder.db")).expanduser()
    temp_dir = Path(os.getenv("TEMP_DIR", "temp")).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    music_dir = Path(os.getenv("MUSIC_DIR", "music")).expanduser()
    music_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        acr_host=os.getenv("ACR_HOST", "").strip().replace("https://", "").replace("http://", "").rstrip("/"),
        acr_access_key=os.getenv("ACR_ACCESS_KEY", "").strip(),
        acr_access_secret=os.getenv("ACR_ACCESS_SECRET", "").strip(),
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", "").strip(),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "").strip(),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
        database_path=db_path,
        temp_dir=temp_dir,
        search_limit=max(1, min(int(os.getenv("SEARCH_LIMIT", "5")), 10)),
        max_media_mb=max(1, min(int(os.getenv("MAX_MEDIA_MB", "20")), 50)),
        music_dir=music_dir,
        download_max_mb=max(5, min(int(os.getenv("DOWNLOAD_MAX_MB", "45")), 1900)),
        max_parallel_downloads=max(1, min(5, int(os.getenv("MAX_PARALLEL_DOWNLOADS", "2")))),
        request_cooldown=max(0.3, float(os.getenv("REQUEST_COOLDOWN", "1.2"))),
        mini_app_url=os.getenv("MINI_APP_URL", "").strip().rstrip("/"),
        web_host=os.getenv("WEB_HOST", "0.0.0.0").strip() or "0.0.0.0",
        web_port=max(1, min(65535, int(os.getenv("PORT", os.getenv("WEB_PORT", "8080"))))),
        cookies_file=(Path(os.getenv("COOKIES_FILE", "cookies.txt")).expanduser() if os.getenv("COOKIES_FILE", "").strip() else None),
    )
