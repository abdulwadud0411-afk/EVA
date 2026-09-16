"""
YouTube downloader (Phase 14).

Uses yt-dlp to download video/audio when captions are unavailable or
when a demo video needs frame analysis.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class DownloadError(Exception):
    """Raised when download fails."""


class YouTubeDownloader:
    def __init__(self) -> None:
        base = ConfigManager.get_data_dir()
        raw = ConfigManager.get("learning.video.download_dir", "./data/knowledge/videos")
        p = Path(raw)
        if not p.is_absolute():
            p = ConfigManager.get_project_root() / raw
        self.download_dir = p
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_minutes = int(ConfigManager.get("learning.video.max_duration_minutes", 90))

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def download_audio(self, url: str) -> Optional[Path]:
        """Download only the audio track (mp3). Smallest download."""
        return self._download(url, audio_only=True)

    def download_video(self, url: str) -> Optional[Path]:
        """Download video at configured max quality."""
        return self._download(url, audio_only=False)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _download(self, url: str, audio_only: bool) -> Optional[Path]:
        try:
            import yt_dlp  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise DownloadError(
                "yt-dlp not installed. Run: pip install yt-dlp"
            ) from exc

        outtmpl = str(self.download_dir / "%(id)s.%(ext)s")
        quality = str(ConfigManager.get("learning.youtube.max_quality", "720p"))

        if audio_only:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }],
                "quiet": True,
                "no_warnings": True,
                "match_filter": self._duration_filter,
            }
        else:
            # quality like "720p" -> format selector
            height = "".join(ch for ch in quality if ch.isdigit()) or "720"
            ydl_opts = {
                "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
                "merge_output_format": "mp4",
                "match_filter": self._duration_filter,
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Post-processor may change extension
                p = Path(filename)
                if audio_only and p.suffix != ".mp3":
                    p = p.with_suffix(".mp3")
                if not audio_only and p.suffix not in (".mp4", ".mkv", ".webm"):
                    p = p.with_suffix(".mp4")
        except Exception as exc:  # noqa: BLE001
            logger.error("youtube_download_failed", url=url, error=str(exc))
            raise DownloadError(f"Download failed: {exc}") from exc

        if not p.exists():
            raise DownloadError(f"File not found after download: {p}")

        logger.info("youtube_download_ok", path=str(p), size_mb=p.stat().st_size / 1_048_576)
        return p

    def _duration_filter(self, info_dict, *, incomplete=False):
        """Reject videos longer than max_duration_minutes."""
        dur = info_dict.get("duration")
        if dur is None:
            return None
        if dur > self.max_minutes * 60:
            return f"Video too long: {dur / 60:.1f} min (limit {self.max_minutes} min)"
        return None