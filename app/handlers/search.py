from __future__ import annotations

import html
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, FSInputFile

from app.config import Settings
from app.database.db import Database
from app.keyboards.main import (
    decode_search,
    decode_track,
    encode_search,
    encode_track,
    search_results_keyboard,
    track_keyboard,
)
from app.models import Track
from app.services.spotify import SpotifyError, SpotifyService
from app.services.youtube import YouTubeError, YouTubeService
from app.services.downloader import MediaDownloader
from app.services.task_manager import TaskManager

router = Router(name="search")
logger = logging.getLogger(__name__)


def format_duration(duration_ms: int | None) -> str:
    if not duration_ms:
        return ""
    total = duration_ms // 1000
    return f"{total // 60}:{total % 60:02d}"


def track_text(track: Track, index: int | None = None) -> str:
    prefix = f"<b>{index}.</b> " if index else ""
    lines = [f"{prefix}🎵 <b>{html.escape(track.title)}</b>", f"👤 {html.escape(track.artist)}"]
    if track.album:
        lines.append(f"💿 {html.escape(track.album)}")
    if track.release_date:
        lines.append(f"📅 {html.escape(track.release_date)}")
    if track.duration_ms:
        lines.append(f"⏱ {format_duration(track.duration_ms)}")
    return "\n".join(lines)


def result_list_text(query: str, tracks: list[Track]) -> str:
    lines = [f"🔍 <b>{html.escape(query)}</b>", ""]
    for index, track in enumerate(tracks[:10], 1):
        duration = format_duration(track.duration_ms)
        suffix = f" <b>{duration}</b>" if duration else ""
        lines.append(f"<b>{index}.</b> {html.escape(track.title)}{suffix}")
    lines.append("\nPastdagi raqamdan bittasini tanlang.")
    return "\n".join(lines)


async def enrich_spotify(track: Track, spotify: SpotifyService | None) -> Track:
    if not spotify:
        return track
    try:
        matches = await spotify.search(track.title, 1)
        if matches:
            match = matches[0]
            track.spotify_url = match.spotify_url
            track.album = match.album
            track.release_date = match.release_date
            if not track.image_url:
                track.image_url = match.image_url
    except Exception:
        # Spotify javob bermasa ham YouTube natijasini foydalanuvchiga chiqaramiz.
        logger.exception("Spotify enrichment failed")
    return track


@router.message(F.text & ~F.text.startswith("/"))
async def search_text(
    message: Message,
    settings: Settings,
    db: Database,
    spotify: SpotifyService | None,
    youtube: YouTubeService | None,
    task_manager: TaskManager,
) -> None:
    allowed, remaining = await task_manager.allow_user(message.from_user.id, settings.request_cooldown)
    if not allowed:
        await message.answer(f"⏱ Juda tez yuboryapsiz. {remaining:.1f} soniya kuting.")
        return
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Kamida 2 ta belgi yozing.")
        return
    wait = await message.answer("🔎 Qidiryapman...")

    # Avval admin qo'shgan qonuniy audio kutubxona, keyin YouTube.
    tracks: list[Track] = await db.search_music(query, 10)
    if youtube and len(tracks) < 10:
        try:
            online = await youtube.search_tracks(query, 10 - len(tracks))
            existing = {t.key for t in tracks}
            tracks.extend(t for t in online if t.key not in existing)
        except YouTubeError as exc:
            logger.exception("YouTube search failed")
            await wait.edit_text(f"❌ YouTube API xatosi: <code>{html.escape(str(exc)[:300])}</code>")
            return

    # Kutubxona va YouTube natija bermasa, Spotify fallback.
    if not tracks and spotify:
        try:
            tracks = await spotify.search(query, 10)
        except SpotifyError as exc:
            logger.exception("Spotify search failed")
            await wait.edit_text(f"❌ Spotify API xatosi: <code>{html.escape(str(exc)[:300])}</code>")
            return

    await db.add_history(message.from_user.id, "search", query=query, track=tracks[0] if tracks else None)
    if not tracks:
        await wait.edit_text("😕 Hech narsa topilmadi. YouTube API kalitini tekshiring yoki boshqa nom yozing.")
        return

    token = encode_search(tracks)
    await wait.edit_text(result_list_text(query, tracks), reply_markup=search_results_keyboard(token, len(tracks)))


@router.callback_query(F.data.startswith("pick:"))
async def pick_result(
    callback: CallbackQuery,
    db: Database,
    spotify: SpotifyService | None,
    downloader: MediaDownloader,
    task_manager: TaskManager,
) -> None:
    try:
        _, token, raw_index = callback.data.split(":", 2)
        selected_index = int(raw_index)
        track = decode_search(token, selected_index)
    except Exception:
        await callback.answer("Qidiruv eskirgan. Qaytadan qidiring.", show_alert=True)
        return

    await callback.answer("Tanlandi")

    try:
        if track.source != "spotify" and spotify:
            import asyncio
            await asyncio.wait_for(enrich_spotify(track, spotify), timeout=8)
    except Exception:
        logger.exception("Selected track enrichment skipped")

    try:
        await db.add_history(callback.from_user.id, "selected", query=track.query, track=track)
    except Exception:
        logger.exception("Could not save selected track history")

    favorite_token = encode_track(track)
    markup = track_keyboard(track, favorite_token)
    text = track_text(track)

    try:
        if track.telegram_file_id:
            await callback.message.answer_audio(
                audio=track.telegram_file_id,
                title=track.title,
                performer=track.artist,
                caption=f"🎵 <b>{html.escape(track.title)}</b>\n👤 {html.escape(track.artist)}",
                reply_markup=markup,
            )
            return

        if track.local_path and Path(track.local_path).is_file():
            sent = await callback.message.answer_audio(
                audio=FSInputFile(track.local_path),
                title=track.title,
                performer=track.artist,
                caption=f"🎵 <b>{html.escape(track.title)}</b>\n👤 {html.escape(track.artist)}",
                reply_markup=markup,
            )
            if sent.audio:
                track.telegram_file_id = sent.audio.file_id
                await db.add_music(track, Path(track.local_path).name)
            return

        # Tanlangan natija ishlamasa, shu qidiruvdagi boshqa YouTube natijalarini
        # avtomatik sinab ko‘ramiz. Avval tanlangan, keyin qolganlari.
        candidates: list[Track] = [track]
        for index in range(10):
            if index == selected_index:
                continue
            try:
                candidate = decode_search(token, index)
            except Exception:
                continue
            if candidate.youtube_url and all(
                candidate.youtube_url != item.youtube_url for item in candidates
            ):
                candidates.append(candidate)

        candidates = [item for item in candidates if item.youtube_url][:6]

        if candidates:
            position = await task_manager.position()
            progress = await callback.message.answer(
                f"⏳ Navbatdagi o‘rningiz: <b>{position}</b>\n🎧 Qo‘shiq tayyorlanmoqda…"
            )

            last_error: Exception | None = None

            for attempt_number, candidate in enumerate(candidates, start=1):
                result = None
                active_markup = track_keyboard(candidate, encode_track(candidate))

                try:
                    cached = await db.get_cached_track(candidate)
                    if cached and cached.telegram_file_id:
                        await callback.message.answer_audio(
                            audio=cached.telegram_file_id,
                            title=candidate.title,
                            performer=candidate.artist,
                            caption=(
                                f"⚡ <b>{html.escape(candidate.title)}</b>\n"
                                f"👤 {html.escape(candidate.artist)}\n\n"
                                "Keshdan tez yuborildi."
                            ),
                            reply_markup=active_markup,
                        )
                        await progress.delete()
                        return

                    await progress.edit_text(
                        f"⬇️ Yuklanmoqda…\n"
                        f"Urinish: <b>{attempt_number}/{len(candidates)}</b>\n"
                        "████░░░░░░ 40%"
                    )

                    async with await task_manager.enter(candidate.youtube_url):
                        cached = await db.get_cached_track(candidate)
                        if cached and cached.telegram_file_id:
                            await callback.message.answer_audio(
                                audio=cached.telegram_file_id,
                                title=candidate.title,
                                performer=candidate.artist,
                                caption=(
                                    f"⚡ <b>{html.escape(candidate.title)}</b>\n"
                                    f"👤 {html.escape(candidate.artist)}"
                                ),
                                reply_markup=active_markup,
                            )
                            await progress.delete()
                            return

                        result = await downloader.download(
                            candidate.youtube_url,
                            f"track_{callback.from_user.id}_{callback.id}_{attempt_number}",
                            audio_only=True,
                        )

                        await progress.edit_text(
                            "📤 Telegram’ga yuborilmoqda…\n████████░░ 80%"
                        )

                        sent = await callback.message.answer_audio(
                            audio=FSInputFile(result.path),
                            title=candidate.title or result.title,
                            performer=candidate.artist or result.uploader or "Noma’lum ijrochi",
                            duration=result.duration,
                            caption=(
                                f"🎵 <b>{html.escape(candidate.title or result.title)}</b>\n"
                                f"👤 {html.escape(candidate.artist or result.uploader or 'Noma’lum ijrochi')}\n\n"
                                "❤️ Sevimlilarga saqlashingiz mumkin."
                            ),
                            reply_markup=active_markup,
                        )

                        if sent.audio:
                            candidate.telegram_file_id = sent.audio.file_id
                            await db.add_music(
                                candidate,
                                f"youtube_{sent.audio.file_unique_id}.mp3",
                            )

                        await progress.delete()
                        return

                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "YouTube fallback failed: attempt=%s url=%s error=%s",
                        attempt_number,
                        candidate.youtube_url,
                        exc,
                    )
                    try:
                        await progress.edit_text(
                            f"⚠️ {attempt_number}-natija ishlamadi. "
                            "Keyingisi tekshirilmoqda…"
                        )
                    except Exception:
                        pass
                finally:
                    try:
                        await downloader.cleanup(result)
                    except Exception:
                        logger.exception("Could not remove temporary audio work directory")

            try:
                await progress.delete()
            except Exception:
                pass

            error_text = str(last_error or "Mos audio format topilmadi")
            await callback.message.answer(
                "❌ Tanlangan natijalar ichidan yuklab bo‘ladigan audio topilmadi.\n"
                "Boshqa nom bilan qayta qidiring yoki boshqa natijani tanlang.\n\n"
                f"<code>{html.escape(error_text[:220])}</code>"
            )
            return

        await callback.message.answer(text, reply_markup=markup)

    except Exception as exc:
        logger.exception("Could not send selected track")
        await callback.message.answer(
            "❌ Natijani chiqarishda xato bo‘ldi. Qaytadan qidirib ko‘ring.\n"
            f"<code>{html.escape(str(exc)[:250])}</code>"
        )


@router.callback_query(F.data == "search_close")
async def close_search(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.in_({"search_back", "search_next"}))
async def search_page_placeholder(callback: CallbackQuery) -> None:
    await callback.answer("Hozir 10 ta eng yaxshi natija ko'rsatilgan.", show_alert=False)


@router.callback_query(F.data.startswith("fav:"))
async def toggle_favorite(callback: CallbackQuery, db: Database) -> None:
    try:
        track = decode_track(callback.data.split(":", 1)[1])
        added = await db.toggle_favorite(callback.from_user.id, track)
    except Exception:
        logger.exception("Favorite callback decode failed")
        await callback.answer("Bu tugma eskirgan yoki ma'lumot juda uzun.", show_alert=True)
        return
    await callback.answer("❤️ Sevimlilarga qo'shildi" if added else "💔 Sevimlilardan olib tashlandi", show_alert=True)
