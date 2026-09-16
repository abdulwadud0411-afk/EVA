"""
openWakeWord provider (Phase 10).

Wraps the openWakeWord library. Uses a built-in model as a fast gate.
If the model detects a plausible wake-word frame, the detector hands
off to STT for verification (in hybrid mode).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.voice.wakeword_base import (
    WakeWordDetection,
    WakeWordError,
    WakeWordProvider,
)

logger = get_logger(__name__)

try:
    from openwakeword.model import Model as OWWModel  # type: ignore
    _OWW_AVAILABLE = True
except Exception:  # noqa: BLE001
    OWWModel = None  # type: ignore
    _OWW_AVAILABLE = False


_SAMPLE_RATE = 16000


class OpenWakeWordProvider(WakeWordProvider):
    """
    Lightweight neural wake-word gate.

    Because openWakeWord does not ship a "Hey EVA" model out of the box,
    we use a close placeholder (e.g. `hey_jarvis`) and rely on the STT
    layer to verify the exact phrase.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.model_name = str(self.config.get("model", "hey_jarvis"))
        self.sensitivity = float(self.config.get("sensitivity", 0.5))
        self.chunk_seconds = float(self.config.get("chunk_seconds", 1.5))
        self._model = None
        self._chunk_samples = int(_SAMPLE_RATE * self.chunk_seconds)
        self._buffer = np.zeros(0, dtype=np.int16)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    async def warm_up(self) -> bool:
        if not _OWW_AVAILABLE:
            logger.error("openwakeword_not_installed")
            return False
        if self._model is not None:
            return True
        try:
            # Load the requested model, downloading if necessary.
            self._model = OWWModel(
                wakeword_models=[self.model_name],
                inference_framework="onnx",
            )
            logger.info(
                "openwakeword_loaded",
                model=self.model_name,
                sensitivity=self.sensitivity,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("openwakeword_load_failed", error=str(exc))
            return False

    def reset(self) -> None:
        self._buffer = np.zeros(0, dtype=np.int16)
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:  # noqa: BLE001
                pass

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_multiple_phrases": False,
            "supports_custom_models": True,
            "supports_streaming": True,
        }

    async def process_chunk(self, audio_chunk: Any) -> WakeWordDetection:
        if self._model is None:
            raise WakeWordError("openWakeWord model not loaded.")

        if not isinstance(audio_chunk, np.ndarray):
            audio_chunk = np.frombuffer(audio_chunk, dtype=np.int16)

        # Accumulate into the buffer until we have a full chunk
        self._buffer = np.concatenate([self._buffer, audio_chunk])
        if len(self._buffer) < self._chunk_samples:
            return WakeWordDetection(triggered=False, phrase="")

        chunk = self._buffer[: self._chunk_samples]
        self._buffer = self._buffer[self._chunk_samples :]

        try:
            scores = self._model.predict(chunk)
        except Exception as exc:  # noqa: BLE001
            logger.warning("openwakeword_predict_failed", error=str(exc))
            return WakeWordDetection(triggered=False, phrase="")

        # scores is a dict {model_name: score}
        best_phrase = ""
        best_score = 0.0
        for name, score in scores.items():
            try:
                score_f = float(score)
            except Exception:  # noqa: BLE001
                continue
            if score_f > best_score:
                best_score = score_f
                best_phrase = name

        triggered = best_score >= self.sensitivity
        return WakeWordDetection(
            triggered=triggered,
            phrase=best_phrase,
            confidence=best_score,
            metadata={"source": "openwakeword"},
        )