from __future__ import annotations

import re
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message

from app.config import Settings
from app.database.db import Database
from app.models import Track

router = Router(name="library")


def _admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_ids)


def _parse_name(text: str | None, filename: str | None = None) -> tuple[str, str]:
    raw = (text or "").strip()
    raw = re.sub(r"^/addmusic(?:@\w+)?\s*", "", raw, flags=re.I).strip()
    if not raw and filename:
        raw = Path(filename).stem.replace("_", " ")
    if " - " in raw:
        artist, title = raw.split(" - ", 1)
        return artist.strip() or "Noma'lum ijrochi", title.strip() or "Noma'lum qo'shiq"
    return "Noma'lum ijrochi", raw or "Noma'lum qo'shiq"


@router.message(Command("addmusic"))
async def add_music(message: Message, command: CommandObject, settings: Settings, db: Database) -> None:
    if not _admin(message, settings):
        await message.answer("⛔ Bu buyruq faqat admin uchun.")
        return
    media = message.reply_to_message
    if not media:
        await message.answer("Audio/MP3 xabarga reply qilib yozing:\n<code>/addmusic Ijrochi - Qo'shiq</code>")
        return

    file_id = None
    filename = None
    duration_ms = None
    title = artist = album = None
    if media.audio:
        file_id = media.audio.file_id
        filename = media.audio.file_name
        duration_ms = (media.audio.duration or 0) * 1000 or None
        title = media.audio.title
        artist = media.audio.performer
    elif media.document and (media.document.mime_type or "").startswith("audio/"):
        file_id = media.document.file_id
        filename = media.document.file_name
    else:
        await message.answer("❌ Reply qilingan xabar audio yoki MP3 hujjat bo'lishi kerak.")
        return

    parsed_artist, parsed_title = _parse_name(command.args, filename)
    track = Track(
        title=title or parsed_title,
        artist=artist or parsed_artist,
        album=album,
        duration_ms=duration_ms,
        telegram_file_id=file_id,
        source="library",
    )
    row_id = await db.add_music(track, filename)
    await message.answer(f"✅ Kutubxonaga qo'shildi #{row_id}\n🎵 <b>{track.title}</b>\n👤 {track.artist}")


@router.message(Command("musiccount"))
async def music_count(message: Message, settings: Settings, db: Database) -> None:
    if not _admin(message, settings):
        return
    await message.answer(f"🎵 Kutubxonadagi qo'shiqlar: <b>{await db.music_count()}</b>")


@router.message(Command("importmusic"))
async def import_music(message: Message, settings: Settings, db: Database) -> None:
    if not _admin(message, settings):
        return
    files = [p for p in settings.music_dir.rglob("*") if p.suffix.lower() in {".mp3", ".m4a", ".ogg", ".flac"}]
    if not files:
        await message.answer(f"📁 <code>{settings.music_dir}</code> papkasida audio topilmadi.")
        return
    status = await message.answer(f"⏳ {len(files)} ta fayl import qilinmoqda...")
    ok = bad = 0
    for path in files:
        try:
            artist, title = _parse_name(None, path.name)
            sent = await message.bot.send_audio(
                chat_id=message.chat.id,
                audio=FSInputFile(path),
                title=title,
                performer=artist,
                disable_notification=True,
            )
            if not sent.audio:
                raise RuntimeError("Telegram audio file_id qaytarmadi")
            await db.add_music(Track(title=title, artist=artist, duration_ms=(sent.audio.duration or 0)*1000 or None, telegram_file_id=sent.audio.file_id, local_path=str(path), source="library"), path.name)
            ok += 1
        except Exception:
            bad += 1
    await status.edit_text(f"✅ Import: {ok}\n❌ Xato: {bad}\n🎵 Jami: {await db.music_count()}")
