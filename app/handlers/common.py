from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.database.db import Database
from app.config import Settings
from app.keyboards.main import main_menu, track_keyboard

router = Router(name="common")

WELCOME = (
    "<b>🎧 Music Finder Professional</b>\n\n"
    "🎙 Voice, audio yoki video yuboring — ichidagi musiqani aniqlayman.\n"
    "🔎 Qo'shiq yoki ijrochi nomini yozing — Spotify va YouTube'dan qidiraman.\n\n"
    "<i>Faqat o'zingizga tegishli yoki ruxsat berilgan kontentni yuklang.</i>"
)


@router.message(CommandStart())
async def start(message: Message, db: Database, settings: Settings) -> None:
    if message.from_user:
        await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer(WELCOME, reply_markup=main_menu(settings.mini_app_url))


@router.message(Command("id"))
async def user_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("menu"))
async def menu(message: Message, settings: Settings) -> None:
    await message.answer(WELCOME, reply_markup=main_menu(settings.mini_app_url))


@router.message(Command("miniapp"))
async def miniapp(message: Message, settings: Settings) -> None:
    if not settings.mini_app_url.startswith("https://"):
        await message.answer("Mini App URL hali .env faylida sozlanmagan.")
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✨ Mini Appni ochish", web_app=WebAppInfo(url=settings.mini_app_url))
    ]])
    await message.answer("🎧 Music Finder Mini App", reply_markup=markup)


@router.callback_query(F.data == "help_recognize")
async def recognize_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("🎙 5–15 soniyalik voice/audio yoki qisqa video yuboring. Musiqa aniq eshitilsin.")


@router.callback_query(F.data == "help_search")
async def search_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("🔎 Qo'shiq yoki ijrochi nomini oddiy matn qilib yuboring. Masalan: <code>Eminem Lose Yourself</code>")


@router.callback_query(F.data == "favorites")
async def favorites(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    tracks = await db.get_favorites(callback.from_user.id)
    if not tracks:
        await callback.message.answer("❤️ Sevimlilar ro'yxati hozircha bo'sh.")
        return
    await callback.message.answer(f"❤️ <b>Sevimlilar:</b> {len(tracks)} ta")
    for track in tracks[:10]:
        await callback.message.answer(f"🎵 <b>{track.title}</b>\n👤 {track.artist}", reply_markup=track_keyboard(track))


@router.callback_query(F.data == "history")
async def history(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    rows = await db.get_history(callback.from_user.id)
    if not rows:
        await callback.message.answer("🕘 Tarix hozircha bo'sh.")
        return
    lines = ["<b>🕘 Oxirgi harakatlar:</b>"]
    for row in rows[:12]:
        track = row["track"]
        value = track.query if track else (row["query"] or "—")
        lines.append(f"• {row['created_at'][:16]} — {value}")
    await callback.message.answer("\n".join(lines))
