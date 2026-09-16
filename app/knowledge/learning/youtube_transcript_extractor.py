"""
YouTube transcript extractor (Phase 14).

Fetches auto-generated or manual captions without downloading video.
Falls back to None if no captions are available.
"""
from __future__ import annotations

import re
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


_YT_URL_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)(?P<vid>[A-Za-z0-9_-]{11})"
)


class TranscriptError(Exception):
    """Raised when transcript extraction fails."""


class YouTubeTranscriptExtractor:
    """Fetch captions from a YouTube URL."""

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        m = _YT_URL_RE.search(url)
        return m.group("vid") if m else None

    def extract(self, url: str, languages: Optional[list] = None) -> Optional[str]:
        vid = self.extract_video_id(url)
        if not vid:
            logger.warning("youtube_invalid_url", url=url)
            return None

        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.warning("youtube_transcript_api_not_installed", error=str(exc))
            return None

        langs = languages or ["en", "bn", "hi"]

        try:
            entries = YouTubeTranscriptApi.get_transcript(vid, languages=langs)
        except Exception as exc:  # noqa: BLE001
            logger.info("youtube_transcript_unavailable", vid=vid, error=str(exc))
            return None

        text = " ".join(e.get("text", "").strip() for e in entries if e.get("text"))
        logger.info("youtube_transcript_ok", vid=vid, length=len(text))
        return text