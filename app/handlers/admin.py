from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
<<<<<<< HEAD
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
=======
from aiogram.types import Message
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd

from app.config import Settings
from app.database.db import Database
from app.services.task_manager import TaskManager

router = Router(name="admin")


def is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_ids)


@router.message(Command("stats"))
async def stats(message: Message, settings: Settings, db: Database) -> None:
    if not is_admin(message, settings):
        return
    data = await db.stats()
    await message.answer(
        "<b>📊 Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{data['users']}</b>\n"
        f"🔎 Jami harakatlar: <b>{data['history']}</b>\n"
        f"📅 Bugun: <b>{data['today']}</b>\n"
        f"❤️ Sevimlilar: <b>{data['favorites']}</b>"
    )


@router.message(Command("broadcast"))
async def broadcast(message: Message, command: CommandObject, settings: Settings, db: Database) -> None:
    if not is_admin(message, settings):
        return
    text = (command.args or "").strip()
    if not text and message.reply_to_message:
        text = message.reply_to_message.html_text or message.reply_to_message.text or ""
    if not text:
        await message.answer("Foydalanish: <code>/broadcast xabar matni</code>")
        return
    sent = failed = 0
    progress = await message.answer("📨 Tarqatish boshlandi...")
    for user_id in await db.all_user_ids():
        try:
            await message.bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)
    await progress.edit_text(f"✅ Yuborildi: {sent}\n❌ Xato: {failed}")


@router.message(Command("status"))
async def status(message: Message, settings: Settings, task_manager: TaskManager) -> None:
    if not is_admin(message, settings):
        return
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(".").percent
        system = f"CPU: <b>{cpu}%</b>\nRAM: <b>{ram}%</b>\nDisk: <b>{disk}%</b>"
    except Exception:
        system = "Tizim statistikasi mavjud emas"
    await message.answer(
        "<b>⚡ Bot holati</b>\n\n"
        f"Faol yuklamalar: <b>{task_manager.active}</b>\n"
        f"Navbatda: <b>{task_manager.waiting}</b>\n"
        f"Parallel limit: <b>{settings.max_parallel_downloads}</b>\n\n" + system
    )
<<<<<<< HEAD


@router.message(Command("adminapp"))
async def adminapp(message: Message, settings: Settings) -> None:
    if not is_admin(message, settings):
        return
    if not settings.mini_app_url.startswith("https://"):
        await message.answer("Mini App URL hali .env faylida sozlanmagan.")
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="👑 Admin panelni ochish",
            web_app=WebAppInfo(url=settings.mini_app_url),
        )
    ]])
    await message.answer(
        "<b>👑 Music Finder Admin</b>\n\nFoydalanuvchilar va statistikani ko‘rish:",
        reply_markup=markup,
    )
=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
