"""
Transcript analyzer (Phase 14).

Runs STT on extracted audio (or uses YouTube captions directly)
and provides a clean transcript string.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


class TranscriptAnalyzer:
    async def transcribe_audio(self, audio_path: Path) -> str:
        """Run local STT on a WAV file."""
        try:
            from app.voice.stt_registry import STTRegistry
        except Exception as exc:  # noqa: BLE001
            logger.error("stt_registry_unavailable", error=str(exc))
            return ""

        try:
            stt = STTRegistry.get_active_provider()
            await stt.warm_up()
            result = await stt.transcribe(str(audio_path))
            return result.text or ""
        except Exception as exc:  # noqa: BLE001
            logger.error("stt_transcribe_failed", error=str(exc))
            return ""

    def clean(self, raw: str, max_chars: int = 20_000) -> str:
        """Trim very long transcripts before sending to the AI provider."""
        text = (raw or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars]