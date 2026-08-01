from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import Settings
from app.database.db import Database
from app.models import Track
from app.services.spotify import SpotifyService
from app.services.youtube import YouTubeService


class FavoritePayload(BaseModel):
    title: str
    artist: str
    album: str | None = None
    release_date: str | None = None
    duration_ms: int | None = None
    image_url: str | None = None
    spotify_url: str | None = None
    youtube_url: str | None = None
    preview_url: str | None = None
    isrc: str | None = None
    source: str = "miniapp"
    telegram_file_id: str | None = None
    local_path: str | None = None


def _validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict:
    if not init_data:
        raise HTTPException(status_code=401, detail="Telegram initData topilmadi")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData hash mavjud emas")

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Telegram imzosi noto‘g‘ri")

    auth_date = int(values.get("auth_date", "0") or 0)
    if auth_date and time.time() - auth_date > max_age:
        raise HTTPException(status_code=401, detail="Telegram sessiyasi eskirgan")

    try:
        user = json.loads(values.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=401, detail="Telegram user ma’lumoti noto‘g‘ri") from exc
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Telegram user topilmadi")
    return user


def _track_dict(track: Track) -> dict:
    return asdict(track)


def create_web_app(
    settings: Settings,
    db: Database,
    spotify: SpotifyService | None,
    youtube: YouTubeService | None,
) -> FastAPI:
    app = FastAPI(title="Music Finder Mini App", docs_url=None, redoc_url=None)
    static_dir = Path(__file__).resolve().parent.parent / "miniapp"
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

    def auth(x_telegram_init_data: str | None) -> dict:
        return _validate_init_data(x_telegram_init_data or "", settings.bot_token)

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "service": "music-finder-miniapp"}

    @app.get("/api/me")
    async def me(x_telegram_init_data: str | None = Header(default=None)) -> dict:
        user = auth(x_telegram_init_data)
        user_id = int(user["id"])
        await db.upsert_user(
            user_id,
            user.get("username"),
            " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part).strip() or "Telegram user",
        )
        profile = await db.miniapp_profile(user_id)
        favorites = await db.get_favorites(user_id, 30)
        history = await db.get_history(user_id, 30)
        return {
            "user": user,
            "profile": profile,
            "favorites": [_track_dict(track) for track in favorites],
            "is_admin": user_id in settings.admin_ids,
            "history": [
                {
                    "action": row["action"],
                    "query": row["query"],
                    "created_at": row["created_at"],
                    "track": _track_dict(row["track"]) if row["track"] else None,
                }
                for row in history
            ],
        }

    @app.get("/api/search")
    async def search(
        q: str = Query(min_length=2, max_length=120),
        x_telegram_init_data: str | None = Header(default=None),
    ) -> dict:
        user = auth(x_telegram_init_data)
        tracks = await db.search_music(q, 10)
        existing = {track.key for track in tracks}

        if youtube and len(tracks) < 10:
            try:
                for track in await youtube.search_tracks(q, 10 - len(tracks)):
                    if track.key not in existing:
                        tracks.append(track)
                        existing.add(track.key)
            except Exception:
                pass

        if spotify and len(tracks) < 10:
            try:
                for track in await spotify.search(q, 10 - len(tracks)):
                    if track.key not in existing:
                        tracks.append(track)
                        existing.add(track.key)
            except Exception:
                pass

        await db.add_history(int(user["id"]), "miniapp_search", query=q, track=tracks[0] if tracks else None)
        return {"query": q, "tracks": [_track_dict(track) for track in tracks[:10]]}

    @app.post("/api/favorite")
    async def favorite(
        payload: FavoritePayload,
        x_telegram_init_data: str | None = Header(default=None),
    ) -> dict:
        user = auth(x_telegram_init_data)
        added = await db.toggle_favorite(int(user["id"]), Track(**payload.model_dump()))
        return {"added": added}


    @app.get("/api/admin/dashboard")
    async def admin_dashboard(x_telegram_init_data: str | None = Header(default=None)) -> dict:
        user = auth(x_telegram_init_data)
        user_id = int(user["id"])
        if user_id not in settings.admin_ids:
            raise HTTPException(status_code=403, detail="Admin ruxsati yo‘q")
        return await db.admin_dashboard()

    @app.get("/api/admin/users/{user_id}")
    async def admin_user(
        user_id: int,
        x_telegram_init_data: str | None = Header(default=None),
    ) -> dict:
        user = auth(x_telegram_init_data)
        if int(user["id"]) not in settings.admin_ids:
            raise HTTPException(status_code=403, detail="Admin ruxsati yo‘q")
        result = await db.admin_user_detail(user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
        return result

    return app
