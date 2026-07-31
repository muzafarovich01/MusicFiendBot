from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


SUPPORTED_HOSTS = (
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com",
    "facebook.com", "www.facebook.com", "fb.watch",
    "twitter.com", "x.com", "www.x.com",
)


@dataclass(slots=True)
class DownloadResult:
    path: Path
    title: str
    uploader: str | None
    duration: int | None
    webpage_url: str
    media_type: str
    work_dir: Path


def is_supported_url(text: str) -> bool:
    try:
        parsed = urlparse(text.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in SUPPORTED_HOSTS


def platform_name(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "instagram" in host:
        return "Instagram"
    if "tiktok" in host:
        return "TikTok"
    if "youtu" in host:
        return "YouTube"
    if "facebook" in host or "fb.watch" in host:
        return "Facebook"
    if host in {"twitter.com", "x.com", "www.x.com"}:
        return "X"
    return "Platforma"


class MediaDownloader:
    def __init__(self, temp_dir: Path, max_mb: int = 45, cookies_file: Path | None = None) -> None:
        self.temp_dir = temp_dir.resolve()
        self.max_bytes = max_mb * 1024 * 1024
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        candidates = [cookies_file, Path.cwd() / "cookies.txt", Path("cookies.txt")]
        self.cookies_file: Path | None = next(
            (p.resolve() for p in candidates if p and p.exists() and p.is_file()),
            None,
        )

    async def download(self, url: str, job_id: str, audio_only: bool = False) -> DownloadResult:
        return await asyncio.to_thread(self._download_sync, url, job_id, audio_only)

    async def cleanup(self, result: DownloadResult | None) -> None:
        if result is None:
            return
        await asyncio.to_thread(shutil.rmtree, result.work_dir, True)

    def _new_work_dir(self, job_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "", job_id)[:35] or "job"
        # Har bir urinish uchun alohida papka: Windows WinError 5 va fayl to'qnashuvini yo'qotadi.
        return Path(tempfile.mkdtemp(prefix=f"{safe}_{uuid.uuid4().hex[:10]}_", dir=self.temp_dir))

    def _base_options(self, outtmpl: str, audio_only: bool) -> dict:
        options: dict = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "socket_timeout": 35,
            "retries": 5,
            "fragment_retries": 5,
            "extractor_retries": 3,
            "file_access_retries": 5,
            "continuedl": True,
            "overwrites": False,
            "nopart": True,
            "concurrent_fragment_downloads": 1,
            "max_filesize": self.max_bytes,
            "prefer_ffmpeg": True,
            "merge_output_format": "mp4",
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        if self.cookies_file:
            options["cookiefile"] = str(self.cookies_file)

        if audio_only:
            options["format"] = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]
        else:
            options["format"] = (
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                "best[height<=720][ext=mp4]/best[height<=720]/best"
            )
        return options

    def _download_sync(self, url: str, job_id: str, audio_only: bool) -> DownloadResult:
        work_dir = self._new_work_dir(job_id)
        outtmpl = str(work_dir / "media_%(id)s.%(ext)s")
        options = self._base_options(outtmpl, audio_only)

        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise RuntimeError("Media ma'lumoti olinmadi")
                path = self._find_downloaded_file(ydl, info, work_dir, audio_only)

                if path.stat().st_size > self.max_bytes:
                    raise RuntimeError(
                        f"Fayl juda katta. Limit: {self.max_bytes // (1024 * 1024)} MB"
                    )

                ext = path.suffix.lower()
                media_type = "audio" if ext in {".mp3", ".m4a", ".ogg", ".opus", ".wav"} else "video"
                return DownloadResult(
                    path=path,
                    title=str(info.get("title") or "Media")[:200],
                    uploader=(str(info.get("uploader"))[:100] if info.get("uploader") else None),
                    duration=int(info["duration"]) if info.get("duration") else None,
                    webpage_url=str(info.get("webpage_url") or url),
                    media_type=media_type,
                    work_dir=work_dir,
                )
        except DownloadError as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            text = str(exc)
            lowered = text.lower()
            if "drm protected" in lowered or "this video is drm" in lowered:
                raise RuntimeError("Bu natija DRM bilan himoyalangan. Boshqa raqamni tanlang.") from exc
            if "sign in to confirm" in lowered or "not a bot" in lowered:
                raise RuntimeError(
                    "YouTube cookie qabul qilinmadi yoki eskirgan. Yangi cookies.txt eksport qilib almashtiring."
                ) from exc
            if "access is denied" in lowered or "winerror 5" in lowered or "отказано в доступе" in lowered:
                raise RuntimeError(
                    "Windows faylga kirishni blokladi. Botni yopib qayta oching; temp papkani antivirusdan istisno qiling."
                ) from exc
            raise RuntimeError(f"Media yuklab bo'lmadi: {text}") from exc
        except Exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise

    @staticmethod
    def _find_downloaded_file(ydl: YoutubeDL, info: dict, work_dir: Path, audio_only: bool) -> Path:
        possible: list[Path] = []
        for requested in info.get("requested_downloads") or []:
            filepath = requested.get("filepath")
            if filepath:
                possible.append(Path(filepath))

        prepared = Path(ydl.prepare_filename(info))
        possible.append(prepared)
        if audio_only:
            possible.extend([
                prepared.with_suffix(".mp3"),
                prepared.with_suffix(".m4a"),
                prepared.with_suffix(".opus"),
            ])

        for path in possible:
            if path.exists() and path.is_file():
                return path

        candidates = sorted(
            (p for p in work_dir.rglob("*") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if audio_only:
            for candidate in candidates:
                if candidate.suffix.lower() == ".mp3":
                    return candidate
        if candidates:
            return candidates[0]
        raise RuntimeError("Yuklangan fayl topilmadi")
