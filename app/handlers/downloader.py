from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Settings
from app.services.downloader import MediaDownloader, is_supported_url, platform_name
from app.services.task_manager import TaskManager

router = Router(name="downloader")
_pending: dict[tuple[int, int], str] = {}


def _confirm_keyboard(user_id: int, message_id: int) -> InlineKeyboardMarkup:
    key = f"{user_id}:{message_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📹 Video", callback_data=f"dl:video:{key}"),
            InlineKeyboardButton(text="🎧 Audio", callback_data=f"dl:audio:{key}"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"dl:cancel:{key}")],
    ])


@router.message(F.text.func(lambda text: bool(text and is_supported_url(text))))
async def capture_link(message: Message) -> None:
    if not message.from_user or not message.text:
        return
    url = message.text.strip()
    _pending[(message.from_user.id, message.message_id)] = url
    platform = platform_name(url)
    await message.answer(
        f"<b>📥 {platform} havolasi topildi</b>\n\n"
        "Faqat o'zingizga tegishli yoki yuklab olish/tarqatishga ruxsatingiz bor kontent uchun foydalaning.\n"
        "Qaysi format kerak?",
        reply_markup=_confirm_keyboard(message.from_user.id, message.message_id),
    )


@router.callback_query(F.data.startswith("dl:"))
async def process_download(callback: CallbackQuery, downloader: MediaDownloader, settings: Settings, task_manager: TaskManager) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return
    _, mode, owner_raw, msg_raw = parts
    try:
        owner_id, msg_id = int(owner_raw), int(msg_raw)
    except ValueError:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return
    if callback.from_user.id != owner_id:
        await callback.answer("Bu tugma boshqa foydalanuvchiga tegishli", show_alert=True)
        return
    url = _pending.pop((owner_id, msg_id), None)
    if mode == "cancel":
        await callback.answer("Bekor qilindi")
        if callback.message:
            await callback.message.edit_text("❌ Yuklash bekor qilindi.")
        return
    if not url:
        await callback.answer("Havola eskirgan. Qayta yuboring.", show_alert=True)
        return

    position = await task_manager.position()
    await callback.answer("Navbatga qo‘shildi")
    if callback.message:
        await callback.message.edit_text(f"⏳ Navbatdagi o‘rningiz: <b>{position}</b>\nMedia tayyorlanmoqda…")
    result = None
    try:
        async with await task_manager.enter(f"{mode}:{url}"):
            if callback.message:
                await callback.message.edit_text("⬇️ Media yuklanmoqda…")
            result = await downloader.download(
                url=url,
                job_id=f"{owner_id}_{msg_id}",
                audio_only=(mode == "audio"),
            )
        caption = f"<b>{result.title}</b>"
        if result.uploader:
            caption += f"\n👤 {result.uploader}"
        caption += "\n\n✅ Tayyor"
        file = FSInputFile(result.path)
        if result.media_type == "audio":
            await callback.message.answer_audio(file, caption=caption, title=result.title, performer=result.uploader)
        else:
            await callback.message.answer_video(file, caption=caption, supports_streaming=True)
        await callback.message.edit_text("✅ Yuklab berildi.")
    except Exception as exc:
        text = str(exc).strip() or exc.__class__.__name__
        if callback.message:
            await callback.message.edit_text(
                "❌ Yuklab bo'lmadi. Havola yopiq, login talab qilishi, platforma o'zgargan yoki fayl limitdan katta bo'lishi mumkin.\n\n"
                f"<code>{text[:500]}</code>"
            )
    finally:
        await downloader.cleanup(result)
