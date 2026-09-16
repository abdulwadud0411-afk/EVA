"""
Voice interface data models (Phase 8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TranscriptionResult:
    """Result of a speech-to-text transcription."""
    text: str = ""
    language: str = "unknown"
    confidence: float = 0.0
    duration_seconds: float = 0.0
    raw: Optional[Any] = None

    @property
    def is_empty(self) -> bool:
        return not self.text or not self.text.strip()


@dataclass
class RecordingResult:
    """Result of a microphone recording session."""
    audio_path: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 16000
    channels: int = 1
    detected_silence: bool = False
    raw: Optional[Any] = None