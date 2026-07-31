from __future__ import annotations

import html
import re
import time
from collections import OrderedDict

import aiohttp

from app.models import Track


class YouTubeError(RuntimeError):
    pass


def _duration_to_ms(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return (hours * 3600 + minutes * 60 + seconds) * 1000


_BAD_WORDS = (
    "reaction", "live reaction", "trailer", "teaser", "shorts", "interview",
    "karaoke", "slowed", "reverb", "nightcore", "8d audio", "remix compilation",
)


class YouTubeService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._cache: OrderedDict[str, tuple[float, list[Track]]] = OrderedDict()
        self._cache_ttl = 600.0

    async def _request(self, endpoint: str, params: dict[str, str]) -> dict:
        params = {**params, "key": self.api_key}
        timeout = aiohttp.ClientTimeout(total=18, connect=8)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"https://www.googleapis.com/youtube/v3/{endpoint}", params=params) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        message = payload.get("error", {}).get("message", f"HTTP {response.status}")
                        raise YouTubeError(message)
                    return payload
        except aiohttp.ClientError as exc:
            raise YouTubeError(f"YouTube bilan ulanish xatosi: {exc}") from exc

    def _cache_get(self, key: str) -> list[Track] | None:
        item = self._cache.get(key)
        if not item:
            return None
        created, tracks = item
        if time.monotonic() - created > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return [Track(**track.__dict__) if hasattr(track, "__dict__") else Track(
            title=track.title, artist=track.artist, album=track.album, release_date=track.release_date,
            duration_ms=track.duration_ms, image_url=track.image_url, spotify_url=track.spotify_url,
            youtube_url=track.youtube_url, preview_url=track.preview_url, isrc=track.isrc,
            source=track.source, telegram_file_id=track.telegram_file_id, local_path=track.local_path
        ) for track in tracks]

    def _cache_put(self, key: str, tracks: list[Track]) -> None:
        self._cache[key] = (time.monotonic(), tracks)
        self._cache.move_to_end(key)
        while len(self._cache) > 250:
            self._cache.popitem(last=False)

    @staticmethod
    def _score(track: Track, query: str) -> tuple[int, int]:
        title = track.title.lower()
        score = 0
        if any(word in title for word in _BAD_WORDS):
            score -= 30
        if "official audio" in title or "official music video" in title or "topic" in track.artist.lower():
            score += 20
        if all(token in title for token in query.lower().split() if len(token) > 2):
            score += 10
        duration = (track.duration_ms or 0) // 1000
        if 60 <= duration <= 600:
            score += 8
        elif duration > 1200:
            score -= 20
        return score, -duration

    async def search_tracks(self, query: str, limit: int = 10) -> list[Track]:
        limit = max(1, min(limit, 10))
        normalized = " ".join(query.lower().split())
        cached = self._cache_get(f"{normalized}:{limit}")
        if cached is not None:
            return cached

        search_payload = await self._request(
            "search",
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": str(min(25, max(limit * 2, 10))),
                "videoCategoryId": "10",
                "safeSearch": "none",
            },
        )
        items = search_payload.get("items", [])
        video_ids = [item.get("id", {}).get("videoId") for item in items]
        video_ids = [video_id for video_id in video_ids if video_id]
        if not video_ids:
            return []

        details_payload = await self._request(
            "videos",
            {"part": "contentDetails,snippet", "id": ",".join(video_ids)},
        )
        details = {item.get("id"): item for item in details_payload.get("items", [])}

        tracks: list[Track] = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            detail = details.get(video_id, {})
            detail_snippet = detail.get("snippet", {}) or snippet
            thumbs = detail_snippet.get("thumbnails", {})
            image_url = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            duration_ms = _duration_to_ms(detail.get("contentDetails", {}).get("duration"))
            if duration_ms and duration_ms > 30 * 60 * 1000:
                continue
            tracks.append(Track(
                title=html.unescape(detail_snippet.get("title") or snippet.get("title") or "Noma'lum"),
                artist=html.unescape(detail_snippet.get("channelTitle") or snippet.get("channelTitle") or "YouTube"),
                duration_ms=duration_ms,
                image_url=image_url,
                youtube_url=f"https://www.youtube.com/watch?v={video_id}",
                source="youtube",
            ))
        tracks.sort(key=lambda t: self._score(t, query), reverse=True)
        result = tracks[:limit]
        self._cache_put(f"{normalized}:{limit}", result)
        return result

    async def search_video(self, query: str) -> str | None:
        tracks = await self.search_tracks(query, 1)
        return tracks[0].youtube_url if tracks else None
