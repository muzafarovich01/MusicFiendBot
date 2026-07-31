from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


class MediaError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


async def extract_audio(source: Path, destination: Path, seconds: int = 15) -> Path:
    if not ffmpeg_available():
        raise MediaError("Video/voice qayta ishlash uchun FFmpeg o'rnatilmagan. README dagi ko'rsatmani bajaring.")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(source), "-t", str(seconds), "-vn", "-ac", "1", "-ar", "44100", "-b:a", "128k", str(destination),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0 or not destination.exists():
        detail = stderr.decode(errors="ignore")[-500:]
        raise MediaError(f"FFmpeg audio ajrata olmadi. {detail}")
    return destination
