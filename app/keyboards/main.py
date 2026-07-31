from __future__ import annotations

import secrets
from collections import OrderedDict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Track

_TRACK_CACHE: OrderedDict[str, Track] = OrderedDict()
_SEARCH_CACHE: OrderedDict[str, list[Track]] = OrderedDict()
_CACHE_LIMIT = 2000


def main_menu(mini_app_url: str = "") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎙 Qo'shiqni aniqlash", callback_data="help_recognize")],
        [InlineKeyboardButton(text="🔎 Qidirish", callback_data="help_search")],
        [InlineKeyboardButton(text="❤️ Sevimlilar", callback_data="favorites"), InlineKeyboardButton(text="🕘 Tarix", callback_data="history")],
    ]
    if mini_app_url.startswith("https://"):
        rows.insert(0, [InlineKeyboardButton(text="✨ Music Mini App", web_app=WebAppInfo(url=mini_app_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def encode_track(track: Track) -> str:
    token = secrets.token_urlsafe(8)
    _TRACK_CACHE[token] = track
    _TRACK_CACHE.move_to_end(token)
    while len(_TRACK_CACHE) > _CACHE_LIMIT:
        _TRACK_CACHE.popitem(last=False)
    return token


def decode_track(value: str) -> Track:
    track = _TRACK_CACHE.get(value)
    if track is None:
        raise ValueError("Track callback expired")
    return track


def encode_search(tracks: list[Track]) -> str:
    token = secrets.token_urlsafe(7)
    _SEARCH_CACHE[token] = tracks
    _SEARCH_CACHE.move_to_end(token)
    while len(_SEARCH_CACHE) > 500:
        _SEARCH_CACHE.popitem(last=False)
    return token


def decode_search(token: str, index: int) -> Track:
    tracks = _SEARCH_CACHE.get(token)
    if tracks is None or not 0 <= index < len(tracks):
        raise ValueError("Search callback expired")
    return tracks[index]


def search_results_keyboard(token: str, count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(0, min(count, 10), 5):
        rows.append([
            InlineKeyboardButton(text=str(i + 1), callback_data=f"pick:{token}:{i}")
            for i in range(start, min(start + 5, count, 10))
        ])
    rows.append([
        InlineKeyboardButton(text="⬅️", callback_data="search_back"),
        InlineKeyboardButton(text="❌", callback_data="search_close"),
        InlineKeyboardButton(text="➡️", callback_data="search_next"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def track_keyboard(track: Track, favorite_token: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if track.spotify_url:
        builder.button(text="🟢 Spotify", url=track.spotify_url)
    if track.youtube_url:
        builder.button(text="🔴 YouTube", url=track.youtube_url)
    if favorite_token:
        builder.button(text="❤️ Saqlash/olib tashlash", callback_data=f"fav:{favorite_token}")
    builder.adjust(2, 1)
    return builder.as_markup()
