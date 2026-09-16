"""
Abstract STT provider interface (Phase 8).

Every STT engine (Faster-Whisper, OpenAI Whisper API, Google, ...)
implements this ABC. The agent depends only on this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.voice.interface import TranscriptionResult


class STTError(Exception):
    """Raised when speech-to-text fails."""


class STTProvider(ABC):
    """Provider-agnostic speech-to-text interface."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe the given WAV file to text."""
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """
        Feature flags:
            supports_streaming, supports_language_detect,
            supports_timestamps, supports_offline
        """
        raise NotImplementedError

    @abstractmethod
    async def warm_up(self) -> bool:
        """Load any heavy resources (model) up-front. Return True on success."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__