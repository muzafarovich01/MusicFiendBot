from __future__ import annotations

import asyncio
import base64
import time

import aiohttp

from app.models import Track


class SpotifyError(RuntimeError):
    pass


class SpotifyService:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at - 30:
            return self._token
        async with self._lock:
            if self._token and time.monotonic() < self._expires_at - 30:
                return self._token
            basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers = {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}
            timeout = aiohttp.ClientTimeout(total=20)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        "https://accounts.spotify.com/api/token",
                        headers=headers,
                        data={"grant_type": "client_credentials"},
                    ) as response:
                        payload = await response.json(content_type=None)
                        if response.status != 200:
                            raise SpotifyError(payload.get("error_description") or payload.get("error") or f"HTTP {response.status}")
            except aiohttp.ClientError as exc:
                raise SpotifyError(f"Spotify bilan ulanish xatosi: {exc}") from exc
            self._token = payload["access_token"]
            self._expires_at = time.monotonic() + int(payload.get("expires_in", 3600))
            return self._token

    async def search(self, query: str, limit: int = 5) -> list[Track]:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {"q": query, "type": "track", "limit": str(limit), "market": "US"}
        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://api.spotify.com/v1/search", headers=headers, params=params) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        raise SpotifyError(payload.get("error", {}).get("message", f"HTTP {response.status}"))
        except aiohttp.ClientError as exc:
            raise SpotifyError(f"Spotify qidiruv xatosi: {exc}") from exc

        tracks: list[Track] = []
        for item in payload.get("tracks", {}).get("items", []):
            artists = ", ".join(a.get("name", "") for a in item.get("artists", []) if a.get("name"))
            album = item.get("album", {})
            images = album.get("images", [])
            tracks.append(Track(
                title=item.get("name", "Noma'lum"),
                artist=artists or "Noma'lum ijrochi",
                album=album.get("name"),
                release_date=album.get("release_date"),
                duration_ms=item.get("duration_ms"),
                image_url=images[0].get("url") if images else None,
                spotify_url=item.get("external_urls", {}).get("spotify"),
                preview_url=item.get("preview_url"),
                isrc=item.get("external_ids", {}).get("isrc"),
                source="spotify",
            ))
        return tracks
