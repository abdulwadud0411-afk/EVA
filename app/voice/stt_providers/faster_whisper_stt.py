"""
Faster-Whisper STT provider (Phase 8).

Runs Whisper models locally on CPU. No internet, no API key, no cost.
Default model: "small". First call downloads the model (~500 MB).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.voice.base import STTProvider, STTError
from app.voice.interface import TranscriptionResult

logger = get_logger(__name__)

try:
    from faster_whisper import WhisperModel  # type: ignore
    _WHISPER_AVAILABLE = True
except Exception:  # noqa: BLE001
    WhisperModel = None  # type: ignore
    _WHISPER_AVAILABLE = False


class FasterWhisperSTT(STTProvider):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config or {}
        self.model_name = self.config.get("model", "small")
        self.device = self.config.get("device", "cpu")
        self.compute_type = self.config.get("compute_type", "int8")
        self.beam_size = int(self.config.get("beam_size", 5))
        self.vad_filter = bool(self.config.get("vad_filter", True))
        self.initial_prompt = self.config.get(
            "initial_prompt",
            "Hey EVA, open Chrome, Notepad, volume up, take screenshot.",
        )
        self._model = None

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_streaming": False,
            "supports_language_detect": True,
            "supports_timestamps": True,
            "supports_offline": True,
        }

    async def warm_up(self) -> bool:
        """Load the model into memory. Downloads on first call."""
        if not _WHISPER_AVAILABLE:
            logger.error("faster_whisper_not_installed")
            return False
        if self._model is not None:
            return True
        try:
            logger.info(
                "faster_whisper_loading",
                model=self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster_whisper_loaded", model=self.model_name)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("faster_whisper_load_failed", error=str(exc))
            return False

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> TranscriptionResult:
        if not _WHISPER_AVAILABLE:
            raise STTError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            )
        p = Path(audio_path)
        if not p.exists():
            raise STTError(f"Audio file not found: {audio_path}")

        if self._model is None:
            ok = await self.warm_up()
            if not ok:
                raise STTError("Failed to load Whisper model.")

        # Resolve language — prefer config over "auto"
        lang = language
        if not lang or lang == "auto":
            cfg_lang = ConfigManager.get("voice.stt.language", "en")
            lang = None if cfg_lang == "auto" else cfg_lang

        try:
            segments, info = self._model.transcribe(
                str(p),
                language=lang,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                initial_prompt=self.initial_prompt,
            )
            parts = []
            for seg in segments:
                parts.append(seg.text)
            text = "".join(parts).strip()
            detected = getattr(info, "language", "unknown")
            prob = float(getattr(info, "language_probability", 0.0) or 0.0)
            duration = float(getattr(info, "duration", 0.0) or 0.0)
        except Exception as exc:  # noqa: BLE001
            logger.error("faster_whisper_transcribe_failed", error=str(exc))
            raise STTError(f"Transcription failed: {exc}") from exc

        return TranscriptionResult(
            text=text,
            language=detected,
            confidence=prob,
            duration_seconds=duration,
        )