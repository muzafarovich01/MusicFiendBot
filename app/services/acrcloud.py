from __future__ import annotations

import base64
import hashlib
import hmac
import time
from pathlib import Path

import aiohttp

from app.models import Track


class ACRCloudError(RuntimeError):
    pass


class ACRCloudService:
    def __init__(self, host: str, access_key: str, access_secret: str) -> None:
        self.host = host
        self.access_key = access_key
        self.access_secret = access_secret

    async def recognize(self, file_path: Path) -> Track | None:
        endpoint = "/v1/identify"
        timestamp = str(int(time.time()))
        string_to_sign = "\n".join(["POST", endpoint, self.access_key, "audio", "1", timestamp])
        signature = base64.b64encode(
            hmac.new(self.access_secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()
        data = aiohttp.FormData()
        data.add_field("access_key", self.access_key)
        data.add_field("sample_bytes", str(file_path.stat().st_size))
        data.add_field("timestamp", timestamp)
        data.add_field("signature", signature)
        data.add_field("data_type", "audio")
        data.add_field("signature_version", "1")
        data.add_field("sample", file_path.open("rb"), filename=file_path.name, content_type="application/octet-stream")

        timeout = aiohttp.ClientTimeout(total=35)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"https://{self.host}{endpoint}", data=data) as response:
                    payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            raise ACRCloudError(f"ACRCloud bilan ulanish xatosi: {exc}") from exc

        status = payload.get("status", {})
        code = int(status.get("code", -1))
        if code == 1001:
            return None
        if code != 0:
            raise ACRCloudError(f"ACRCloud xatosi {code}: {status.get('msg', 'Unknown error')}")

        music = payload.get("metadata", {}).get("music", [])
        if not music:
            return None
        item = music[0]
        artists = ", ".join(a.get("name", "") for a in item.get("artists", []) if a.get("name")) or "Noma'lum ijrochi"
        external = item.get("external_metadata", {})
        spotify = external.get("spotify", {})
        youtube = external.get("youtube", {})
        return Track(
            title=item.get("title") or "Noma'lum qo'shiq",
            artist=artists,
            album=(item.get("album") or {}).get("name"),
            release_date=item.get("release_date"),
            spotify_url=(f"https://open.spotify.com/track/{spotify.get('track', {}).get('id')}" if spotify.get("track", {}).get("id") else None),
            youtube_url=(f"https://www.youtube.com/watch?v={youtube.get('vid')}" if youtube.get("vid") else None),
            isrc=(item.get("external_ids") or {}).get("isrc"),
            source="acrcloud",
        )
