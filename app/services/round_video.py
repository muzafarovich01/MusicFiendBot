from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


class RoundVideoError(RuntimeError):
    pass


def get_ffmpeg_executable() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


async def make_round_video(source: Path, destination: Path, max_seconds: int = 60) -> Path:
    ffmpeg = get_ffmpeg_executable()
    if not ffmpeg:
        raise RoundVideoError("FFmpeg topilmadi. UPDATE_AND_RUN.bat ni ishga tushiring.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Markazdan kvadrat crop, 512x512 — Telegram video-note uchun yengil va barqaror.
    vf = "crop=min(iw\\,ih):min(iw\\,ih),scale=512:512:flags=lanczos,setsar=1,fps=30"
    process = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-t", str(min(max_seconds, 60)),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
        "-pix_fmt", "yuv420p", "-profile:v", "main",
        "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1",
        "-movflags", "+faststart",
        str(destination),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0 or not destination.exists() or destination.stat().st_size == 0:
        detail = stderr.decode(errors="ignore")[-1200:]
        destination.unlink(missing_ok=True)
        raise RoundVideoError(f"Videoni krujokka aylantirib bo'lmadi. {detail}")
    return destination
