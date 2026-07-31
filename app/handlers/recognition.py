from __future__ import annotations

import logging
import uuid
from pathlib import Path

from aiogram import F, Router
from aiogram.types import Message

from app.config import Settings
from app.database.db import Database
from app.keyboards.main import encode_track, track_keyboard
from app.services.acrcloud import ACRCloudError, ACRCloudService
from app.services.media import MediaError, extract_audio
from app.services.spotify import SpotifyError, SpotifyService
from app.services.youtube import YouTubeError, YouTubeService

router = Router(name="recognition")
logger = logging.getLogger(__name__)


async def _download_media(message: Message, settings: Settings) -> tuple[Path, bool]:
    media = message.voice or message.audio or message.video or message.video_note or message.document
    if media is None:
        raise MediaError("Media topilmadi")
    size = getattr(media, "file_size", 0) or 0
    if size > settings.max_media_mb * 1024 * 1024:
        raise MediaError(f"Fayl juda katta. Maksimum {settings.max_media_mb} MB.")
    suffix = ".bin"
    if message.voice:
        suffix = ".ogg"
    elif message.audio:
        suffix = Path(message.audio.file_name or ".mp3").suffix or ".mp3"
    elif message.video:
        suffix = Path(message.video.file_name or ".mp4").suffix or ".mp4"
    elif message.video_note:
        suffix = ".mp4"
    elif message.document:
        suffix = Path(message.document.file_name or ".bin").suffix or ".bin"
    path = settings.temp_dir / f"{uuid.uuid4().hex}{suffix}"
    await message.bot.download(media, destination=path)
    is_video = bool(message.video or message.video_note or (message.document and (message.document.mime_type or "").startswith("video/")))
    return path, is_video


@router.message(F.voice | F.audio | F.video | F.video_note | F.document)
async def recognize_media(
    message: Message,
    settings: Settings,
    db: Database,
    acr: ACRCloudService | None,
    spotify: SpotifyService | None,
    youtube: YouTubeService | None,
) -> None:
    if not acr:
        await message.answer("❌ ACRCloud sozlanmagan. .env ichidagi ACR_HOST, ACR_ACCESS_KEY va ACR_ACCESS_SECRET ni tekshiring.")
        return
    status = await message.answer("🎧 Musiqani aniqlayapman...")
    source: Path | None = None
    prepared: Path | None = None
    try:
        source, is_video = await _download_media(message, settings)
        if is_video or source.suffix.lower() in {".ogg", ".oga", ".webm", ".m4a"}:
            prepared = settings.temp_dir / f"{source.stem}.mp3"
            await extract_audio(source, prepared)
        else:
            prepared = source
        track = await acr.recognize(prepared)
        if not track:
            await status.edit_text("😕 Qo'shiq aniqlanmadi. 5–15 soniyalik, musiqasi aniqroq parcha yuboring.")
            await db.add_history(message.from_user.id, "recognize_not_found")
            return

        if spotify:
            try:
                matches = await spotify.search(track.query, 1)
                if matches:
                    match = matches[0]
                    track.image_url = match.image_url
                    track.spotify_url = track.spotify_url or match.spotify_url
                    track.preview_url = match.preview_url
                    track.album = track.album or match.album
            except SpotifyError:
                logger.exception("Spotify enrichment failed")
        if youtube and not track.youtube_url:
            try:
                track.youtube_url = await youtube.search_video(track.query)
            except YouTubeError:
                logger.exception("YouTube enrichment failed")

        await db.add_history(message.from_user.id, "recognize", track=track)
        caption = f"✅ <b>Qo'shiq topildi!</b>\n\n🎵 <b>{track.title}</b>\n👤 {track.artist}"
        if track.album:
            caption += f"\n💿 {track.album}"
        if track.release_date:
            caption += f"\n📅 {track.release_date}"
        token = encode_track(track)
        await status.delete()
        if track.image_url:
            await message.answer_photo(track.image_url, caption=caption, reply_markup=track_keyboard(track, token))
        else:
            await message.answer(caption, reply_markup=track_keyboard(track, token))
    except (MediaError, ACRCloudError) as exc:
        logger.exception("Recognition failed")
        await status.edit_text(f"❌ {str(exc)[:500]}")
    except Exception:
        logger.exception("Unexpected recognition failure")
        await status.edit_text("❌ Kutilmagan xato yuz berdi. Konsoldagi logni tekshiring.")
    finally:
        for path in {source, prepared}:
            if path and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
