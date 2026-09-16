"""
Abstract TTS provider interface (Phase 9).

Every TTS engine (Piper, Edge-TTS, OpenAI TTS, ElevenLabs, ...)
implements this ABC.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TTSError(Exception):
    """Raised when text-to-speech fails."""


class TTSProvider(ABC):
    """Provider-agnostic text-to-speech interface."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_path: str,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Render text to an audio file. Return the file path."""
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """
        Feature flags:
            supports_offline, supports_streaming,
            supports_ssml, supports_multilingual
        """
        raise NotImplementedError

    @abstractmethod
    async def warm_up(self) -> bool:
        """Prepare any heavy resources. Return True on success."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__