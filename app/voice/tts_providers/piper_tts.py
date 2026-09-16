"""
Piper TTS adapter (Phase 9).

Fully offline, free. Uses Piper's ONNX voice models.
Model files are looked up under `voice.tts.piper.models_dir`.
If the model is missing, we return a clear error.

On Windows, Piper works best when invoked through its Python API.
We use a lazy import so the package only loads when needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.voice.tts_base import TTSProvider, TTSError

logger = get_logger(__name__)

try:
    from piper.voice import PiperVoice  # type: ignore
    _PIPER_AVAILABLE = True
except Exception:  # noqa: BLE001
    PiperVoice = None  # type: ignore
    _PIPER_AVAILABLE = False


class PiperTTS(TTSProvider):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config or {}
        self.voice_model = self.config.get(
            "voice_model", "en_US-lessac-medium.onnx"
        )
        models_dir = self.config.get("models_dir", "./models/piper")
        base = ConfigManager.get_project_root()
        p = Path(models_dir)
        if not p.is_absolute():
            p = base / p
        self.models_dir = p
        self.speed = float(self.config.get("speed", 1.0))
        self._voice = None

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_offline": True,
            "supports_streaming": False,
            "supports_ssml": False,
            "supports_multilingual": False,
        }

    def _model_path(self) -> Path:
        return self.models_dir / self.voice_model

    async def warm_up(self) -> bool:
        if not _PIPER_AVAILABLE:
            logger.error("piper_not_installed")
            return False
        model_path = self._model_path()
        if not model_path.exists():
            logger.error("piper_model_missing", path=str(model_path))
            return False
        if self._voice is not None:
            return True
        try:
            self._voice = PiperVoice.load(str(model_path))
            logger.info("piper_loaded", model=str(model_path))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("piper_load_failed", error=str(exc))
            return False

    async def synthesize(
        self,
        text: str,
        output_path: str,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if not _PIPER_AVAILABLE:
            raise TTSError("piper-tts is not installed.")
        if not text.strip():
            raise TTSError("Empty text.")

        if self._voice is None:
            ok = await self.warm_up()
            if not ok:
                raise TTSError(
                    "Piper model not available. Download a .onnx voice "
                    "model into models/piper/."
                )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            import wave  # noqa: WPS433
            with wave.open(str(out), "wb") as wav_file:
                self._voice.synthesize(text, wav_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("piper_synthesize_failed", error=str(exc))
            raise TTSError(f"Piper synthesis failed: {exc}") from exc

        return str(out)