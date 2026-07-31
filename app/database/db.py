from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import aiosqlite

from app.models import Track


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    query TEXT,
                    track_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    track_key TEXT NOT NULL,
                    track_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, track_key)
                );
                CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, id DESC);
                CREATE TABLE IF NOT EXISTS music_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT,
                    duration_ms INTEGER,
                    telegram_file_id TEXT,
                    local_path TEXT,
                    source_name TEXT,
                    source_url TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_music_title ON music_library(title);
                CREATE INDEX IF NOT EXISTS idx_music_artist ON music_library(artist);
                CREATE INDEX IF NOT EXISTS idx_music_source_url ON music_library(source_url);
                """
            )
            try:
                await db.execute("ALTER TABLE music_library ADD COLUMN source_url TEXT")
            except Exception:
                pass
            await db.execute("CREATE INDEX IF NOT EXISTS idx_music_source_url ON music_library(source_url)")
            await db.commit()

    async def upsert_user(self, user_id: int, username: str | None, full_name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users(user_id, username, full_name) VALUES(?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    last_seen=CURRENT_TIMESTAMP
                """,
                (user_id, username, full_name),
            )
            await db.commit()

    async def add_history(self, user_id: int, action: str, query: str | None = None, track: Track | None = None) -> None:
        payload = json.dumps(asdict(track), ensure_ascii=False) if track else None
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO history(user_id, action, query, track_json) VALUES(?, ?, ?, ?)",
                (user_id, action, query, payload),
            )
            await db.commit()

    async def toggle_favorite(self, user_id: int, track: Track) -> bool:
        payload = json.dumps(asdict(track), ensure_ascii=False)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id FROM favorites WHERE user_id=? AND track_key=?",
                (user_id, track.key),
            )
            row = await cur.fetchone()
            if row:
                await db.execute("DELETE FROM favorites WHERE id=?", (row[0],))
                await db.commit()
                return False
            await db.execute(
                "INSERT INTO favorites(user_id, track_key, track_json) VALUES(?, ?, ?)",
                (user_id, track.key, payload),
            )
            await db.commit()
            return True

    async def get_favorites(self, user_id: int, limit: int = 20) -> list[Track]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT track_json FROM favorites WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cur.fetchall()
        return [Track(**json.loads(row[0])) for row in rows]

    async def get_history(self, user_id: int, limit: int = 15) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT action, query, track_json, created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cur.fetchall()
        result = []
        for action, query, track_json, created_at in rows:
            result.append({
                "action": action,
                "query": query,
                "track": Track(**json.loads(track_json)) if track_json else None,
                "created_at": created_at,
            })
        return result

    async def stats(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            values: dict[str, int] = {}
            for key, sql in {
                "users": "SELECT COUNT(*) FROM users",
                "history": "SELECT COUNT(*) FROM history",
                "favorites": "SELECT COUNT(*) FROM favorites",
                "today": "SELECT COUNT(*) FROM history WHERE date(created_at)=date('now')",
            }.items():
                cur = await db.execute(sql)
                values[key] = int((await cur.fetchone())[0])
            return values


    async def add_music(self, track: Track, source_name: str | None = None) -> int:
        async with aiosqlite.connect(self.path) as db:
            # Bir xil lokal fayl qayta-qayta bazaga tushmasin.
            if track.local_path:
                cur = await db.execute(
                    "SELECT id FROM music_library WHERE local_path=? LIMIT 1",
                    (track.local_path,),
                )
                row = await cur.fetchone()
                if row:
                    await db.execute(
                        """UPDATE music_library SET title=?, artist=?, album=?, duration_ms=?,
                           telegram_file_id=COALESCE(?, telegram_file_id), source_name=? WHERE id=?""",
                        (track.title, track.artist, track.album, track.duration_ms,
                         track.telegram_file_id, source_name, row[0]),
                    )
                    await db.commit()
                    return int(row[0])

            cur = await db.execute(
                """INSERT INTO music_library(title, artist, album, duration_ms, telegram_file_id, local_path, source_name, source_url)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                (track.title, track.artist, track.album, track.duration_ms, track.telegram_file_id, track.local_path, source_name, track.youtube_url or track.spotify_url),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def search_music(self, query: str, limit: int = 10) -> list[Track]:
        pattern = f"%{query.strip()}%"
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """SELECT title, artist, album, duration_ms, telegram_file_id, local_path
                FROM music_library
                WHERE title LIKE ? COLLATE NOCASE OR artist LIKE ? COLLATE NOCASE
                   OR (artist || ' - ' || title) LIKE ? COLLATE NOCASE
                ORDER BY id DESC LIMIT ?""",
                (pattern, pattern, pattern, limit),
            )
            rows = await cur.fetchall()
        return [Track(title=r[0], artist=r[1], album=r[2], duration_ms=r[3], telegram_file_id=r[4], local_path=r[5], source="library") for r in rows]

    async def get_cached_track(self, track: Track) -> Track | None:
        async with aiosqlite.connect(self.path) as db:
            if track.youtube_url:
                cur = await db.execute(
                    "SELECT title, artist, album, duration_ms, telegram_file_id, local_path, source_url FROM music_library WHERE source_url=? AND telegram_file_id IS NOT NULL ORDER BY id DESC LIMIT 1",
                    (track.youtube_url,),
                )
                row = await cur.fetchone()
                if row:
                    return Track(title=row[0], artist=row[1], album=row[2], duration_ms=row[3], telegram_file_id=row[4], local_path=row[5], youtube_url=row[6], source="cache")
            cur = await db.execute(
                "SELECT title, artist, album, duration_ms, telegram_file_id, local_path, source_url FROM music_library WHERE lower(title)=lower(?) AND lower(artist)=lower(?) AND telegram_file_id IS NOT NULL ORDER BY id DESC LIMIT 1",
                (track.title, track.artist),
            )
            row = await cur.fetchone()
            if row:
                return Track(title=row[0], artist=row[1], album=row[2], duration_ms=row[3], telegram_file_id=row[4], local_path=row[5], youtube_url=row[6], source="cache")
        return None

    async def music_count(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM music_library")
            return int((await cur.fetchone())[0])

    async def miniapp_profile(self, user_id: int) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            searches = int((await (await db.execute(
                "SELECT COUNT(*) FROM history WHERE user_id=? AND action IN ('search', 'miniapp_search')",
                (user_id,),
            )).fetchone())[0])
            favorites = int((await (await db.execute(
                "SELECT COUNT(*) FROM favorites WHERE user_id=?",
                (user_id,),
            )).fetchone())[0])
            library = int((await (await db.execute(
                "SELECT COUNT(*) FROM music_library"
            )).fetchone())[0])
        return {"searches": searches, "favorites": favorites, "library": library}

    async def all_user_ids(self) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT user_id FROM users")
            return [int(row[0]) for row in await cur.fetchall()]
