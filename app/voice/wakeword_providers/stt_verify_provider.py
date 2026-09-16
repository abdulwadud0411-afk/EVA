"""
STT-based wake-word verification provider (Phase 10).

Runs Faster-Whisper over short audio chunks and matches against a list
of trigger phrases ("hey eva", "hello eva", ...). Slower than openWakeWord
but 100% accurate for the exact phrases the user cares about.
"""
from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.voice.wakeword_base import (
    WakeWordDetection,
    WakeWordError,
    WakeWordProvider,
)

logger = get_logger(__name__)


_SAMPLE_RATE = 16000


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    out = []
    for ch in text.lower():
        if ch.isalnum() or ch.isspace():
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


class STTVerifyProvider(WakeWordProvider):
    """
    Whisper-based wake-word verifier.

    Uses the EVA STT registry to keep provider selection consistent.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.phrases: List[str] = [
            _normalize(p)
            for p in (ConfigManager.get("voice.wake_word.phrases", []) or [])
        ]
        self.min_confidence = float(
            self.config.get("min_confidence",
                            ConfigManager.get("voice.wake_word.min_confidence", 0.5))
        )
        self._stt = None

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    async def warm_up(self) -> bool:
        try:
            from app.voice.stt_registry import STTRegistry
            self._stt = STTRegistry.get_active_provider()
            return await self._stt.warm_up()
        except Exception as exc:  # noqa: BLE001
            logger.error("stt_verify_warm_up_failed", error=str(exc))
            return False

    def reset(self) -> None:
        # No internal state to reset
        pass

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_multiple_phrases": True,
            "supports_custom_models": False,
            "supports_streaming": False,
        }

    async def process_chunk(self, audio_chunk: Any) -> WakeWordDetection:
        if self._stt is None:
            raise WakeWordError("STT not warmed up.")

        if not isinstance(audio_chunk, np.ndarray):
            audio_chunk = np.frombuffer(audio_chunk, dtype=np.int16)

        # Skip near-silent chunks (fast path)
        rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)) / 32768.0)
        if rms < 0.005:
            return WakeWordDetection(triggered=False, phrase="")

        # Write chunk to a temp WAV for Whisper
        tmp_path: Optional[Path] = None
        try:
            import soundfile as sf  # type: ignore
            fd, name = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            tmp_path = Path(name)
            sf.write(str(tmp_path), audio_chunk, _SAMPLE_RATE, subtype="PCM_16")

            result = await self._stt.transcribe(str(tmp_path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("stt_verify_transcribe_failed", error=str(exc))
            return WakeWordDetection(triggered=False, phrase="")
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        text = _normalize(result.text)
        if not text:
            return WakeWordDetection(triggered=False, phrase="")

        for phrase in self.phrases:
            if phrase and phrase in text:
                return WakeWordDetection(
                    triggered=True,
                    phrase=phrase,
                    confidence=float(result.confidence or 1.0),
                    metadata={
                        "source": "stt_verify",
                        "transcript": result.text,
                        "language": result.language,
                    },
                )

        return WakeWordDetection(
            triggered=False, phrase="",
            metadata={"transcript": result.text},
        )