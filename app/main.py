from __future__ import annotations

import asyncio
import logging
import sys
import re
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import load_settings
from app.database.db import Database
from app.handlers import admin, common, downloader as downloader_handler, library, recognition, round as round_handler, search
from app.services.acrcloud import ACRCloudService
from app.services.spotify import SpotifyService
from app.services.youtube import YouTubeService
from app.services.downloader import MediaDownloader
from app.services.task_manager import TaskManager
from app.models import Track
from app.webapp import create_web_app
import uvicorn


def _track_from_filename(path: Path) -> Track:
    raw = path.stem.replace("_", " ").strip()
    raw = re.sub(r"\s+", " ", raw)
    if " - " in raw:
        artist, title = raw.split(" - ", 1)
    else:
        artist, title = "Noma'lum ijrochi", raw
    return Track(
        title=title.strip() or "Noma'lum qo'shiq",
        artist=artist.strip() or "Noma'lum ijrochi",
        local_path=str(path.resolve()),
        source="library",
    )


async def auto_index_music(settings, db: Database) -> tuple[int, int]:
    settings.music_dir.mkdir(parents=True, exist_ok=True)
    extensions = {".mp3", ".m4a", ".ogg", ".flac", ".wav"}
    files = [p for p in settings.music_dir.rglob("*") if p.is_file() and p.suffix.lower() in extensions]
    ok = bad = 0
    for path in files:
        try:
            await db.add_music(_track_from_filename(path), path.name)
            ok += 1
        except Exception:
            logging.getLogger(__name__).exception("Could not index %s", path)
            bad += 1
    return ok, bad


async def cleanup_temp(temp_dir: Path, max_age_hours: int = 6) -> int:
    import time
    removed = 0
    cutoff = time.time() - max_age_hours * 3600
    for path in temp_dir.glob("*"):
        try:
            if path.is_file() and path.name != ".gitkeep" and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            logging.getLogger(__name__).exception("Temp cleanup failed for %s", path)
    return removed


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("bot.log", encoding="utf-8")],
    )
    db = Database(settings.database_path)
    await db.init()
    indexed, index_errors = await auto_index_music(settings, db)
    removed_temp = await cleanup_temp(settings.temp_dir)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(common.router, admin.router, downloader_handler.router, library.router, round_handler.router, recognition.router, search.router)

    acr = ACRCloudService(settings.acr_host, settings.acr_access_key, settings.acr_access_secret) if settings.acr_enabled else None
    spotify = SpotifyService(settings.spotify_client_id, settings.spotify_client_secret) if settings.spotify_enabled else None
    youtube = YouTubeService(settings.youtube_api_key) if settings.youtube_enabled else None
    downloader = MediaDownloader(settings.temp_dir, settings.download_max_mb, settings.cookies_file)
    task_manager = TaskManager(settings.max_parallel_downloads)

    logging.getLogger(__name__).info(
        "Bot starting | ACR=%s Spotify=%s YouTube=%s Admins=%s",
        bool(acr), bool(spotify), bool(youtube), len(settings.admin_ids),
    )
    logging.getLogger(__name__).info("Auto music index: %s files, %s errors | temp removed=%s", indexed, index_errors, removed_temp)

    web_app = create_web_app(settings, db, spotify, youtube)
    web_config = uvicorn.Config(web_app, host=settings.web_host, port=settings.web_port, log_level="info")
    web_server = uvicorn.Server(web_config)
    web_task = asyncio.create_task(web_server.serve(), name="miniapp-web-server")
    logging.getLogger(__name__).info("Mini App web server: http://%s:%s", settings.web_host, settings.web_port)

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(
            bot,
            settings=settings,
            db=db,
            acr=acr,
            spotify=spotify,
            youtube=youtube,
            downloader=downloader,
            task_manager=task_manager,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        web_server.should_exit = True
        await web_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
