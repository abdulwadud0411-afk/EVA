"""
Abstract wake-word provider interface (Phase 10).

Every wake-word engine (openWakeWord, Porcupine, custom) implements this
ABC. The WakeWordDetector (hybrid layer) depends only on this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class WakeWordError(Exception):
    """Raised when a wake-word provider fails."""


@dataclass
class WakeWordDetection:
    """A single detection event from a wake-word provider."""
    triggered: bool = False
    phrase: str = ""
    confidence: float = 0.0
    raw: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WakeWordProvider(ABC):
    """Provider-agnostic wake-word interface."""

    @abstractmethod
    async def warm_up(self) -> bool:
        """Load models into memory. Return True on success."""
        raise NotImplementedError

    @abstractmethod
    async def process_chunk(self, audio_chunk: Any) -> WakeWordDetection:
        """
        Process one audio chunk.

        Args:
            audio_chunk: numpy array of int16 samples (typically 1.5 sec).

        Returns:
            WakeWordDetection (triggered=True if the phrase was detected)
        """
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Clear internal state (e.g. after cooldown or manual reset)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """Feature flags: supports_multiple_phrases, supports_custom_models, ..."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__