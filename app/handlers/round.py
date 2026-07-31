from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from app.config import Settings
from app.services.round_video import RoundVideoError, make_round_video
from app.services.task_manager import TaskManager

router = Router(name="round")
_waiting_users: set[int] = set()


def _video_media(message: Message):
    if message.video:
        return message.video, Path(message.video.file_name or "video.mp4").suffix or ".mp4"
    if message.video_note:
        return message.video_note, ".mp4"
    if message.animation:
        return message.animation, Path(message.animation.file_name or "animation.mp4").suffix or ".mp4"
    if message.document and (message.document.mime_type or "").startswith("video/"):
        return message.document, Path(message.document.file_name or "video.mp4").suffix or ".mp4"
    return None, ""


def _is_waiting_video(message: Message) -> bool:
    if not message.from_user:
        return False
    media, _ = _video_media(message)
    if media is None:
        return False
    caption = (message.caption or "").strip().lower()
    return message.from_user.id in _waiting_users or caption.startswith("/round")


async def _convert_and_send(message: Message, settings: Settings, task_manager: TaskManager) -> None:
    media, suffix = _video_media(message)
    if media is None:
        await message.answer("❌ Video topilmadi. /round ni videoga reply qilib yuboring yoki /round dan keyin video yuboring.")
        return

    size = getattr(media, "file_size", 0) or 0
    if size > settings.max_media_mb * 1024 * 1024:
        await message.answer(f"❌ Video juda katta. Maksimum: {settings.max_media_mb} MB.")
        return

    source = settings.temp_dir / f"round_src_{uuid.uuid4().hex}{suffix}"
    output = settings.temp_dir / f"round_{uuid.uuid4().hex}.mp4"
    status = await message.answer("⭕ Video krujok ko'rinishiga tayyorlanmoqda…")

    try:
        async with await task_manager.enter(f"round:{message.chat.id}:{message.message_id}"):
            await message.bot.download(media, destination=source)
            await make_round_video(source, output, max_seconds=60)

        await message.answer_video_note(
            video_note=FSInputFile(output),
            length=512,
        )
        await status.edit_text("✅ Krujok tayyor.")
    except RoundVideoError as exc:
        await status.edit_text(f"❌ {str(exc)[:700]}")
    except Exception as exc:
        await status.edit_text(f"❌ Kutilmagan xato: <code>{str(exc)[:500]}</code>")
    finally:
        await asyncio.to_thread(source.unlink, missing_ok=True)
        await asyncio.to_thread(output.unlink, missing_ok=True)


@router.message(Command("round", "raund"))
async def round_command(message: Message, settings: Settings, task_manager: TaskManager) -> None:
    if not message.from_user:
        return

    replied = message.reply_to_message
    if replied and _video_media(replied)[0] is not None:
        await _convert_and_send(replied, settings, task_manager)
        return

    _waiting_users.add(message.from_user.id)
    await message.answer(
        "⭕ <b>Round rejimi yoqildi.</b>\n\n"
        "Endi istalgan videoni yuboring — uni 60 soniyagacha kesib, dumaloq Telegram krujok qilib beraman.\n\n"
        "Yoki videoga reply qilib <code>/round</code> yozing."
    )


@router.message(F.func(_is_waiting_video))
async def round_waiting_video(message: Message, settings: Settings, task_manager: TaskManager) -> None:
    if message.from_user:
        _waiting_users.discard(message.from_user.id)
    await _convert_and_send(message, settings, task_manager)
