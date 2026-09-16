"""
Edge TTS adapter (Phase 9).

Uses Microsoft Edge's online neural TTS service via the `edge-tts`
Python package. Completely free, no API key, no signup.
Requires an internet connection.

Voices:
    en-US-AvaNeural      — female, warm (default for English)
    en-US-AriaNeural     — female, expressive
    en-US-JennyNeural    — female, friendly
    bn-BD-NabanitaNeural — female, Bangla (Bangladesh)
    bn-IN-TanishaaNeural — female, Bangla (India)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.voice.tts_base import TTSProvider, TTSError

logger = get_logger(__name__)

try:
    import edge_tts  # type: ignore
    _EDGE_AVAILABLE = True
except Exception:  # noqa: BLE001
    edge_tts = None  # type: ignore
    _EDGE_AVAILABLE = False


def _detect_language(text: str) -> str:
    """Very light heuristic: Bangla chars → 'bn', else 'en'."""
    for ch in text:
        if "\u0980" <= ch <= "\u09FF":  # Bengali Unicode block
            return "bn"
    return "en"


class EdgeTTS(TTSProvider):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config or {}
        self.en_voice = self.config.get("en_voice", "en-US-AvaNeural")
        self.bn_voice = self.config.get("bn_voice", "bn-BD-NabanitaNeural")
        self.rate = self.config.get("rate", "+0%")
        self.volume = self.config.get("volume", "+0%")
        self.pitch = self.config.get("pitch", "+0Hz")
        self.language_pref = str(
            ConfigManager.get("voice.tts.language", "auto")
        ).lower()

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_offline": False,
            "supports_streaming": True,
            "supports_ssml": False,
            "supports_multilingual": True,
        }

    async def warm_up(self) -> bool:
        if not _EDGE_AVAILABLE:
            logger.error("edge_tts_not_installed")
            return False
        try:
            voices = await edge_tts.list_voices()  # type: ignore
            logger.info("edge_tts_ready", voice_count=len(voices or []))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("edge_tts_warm_up_failed", error=str(exc))
            return False

    def _pick_voice(self, text: str, language: Optional[str]) -> str:
        lang = (language or self.language_pref or "auto").lower()
        if lang in ("bn", "bangla", "bengali"):
            return self.bn_voice
        if lang in ("en", "english"):
            return self.en_voice
        # auto
        detected = _detect_language(text)
        return self.bn_voice if detected == "bn" else self.en_voice

    async def synthesize(
        self,
        text: str,
        output_path: str,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if not _EDGE_AVAILABLE:
            raise TTSError(
                "edge-tts is not installed. Run: pip install edge-tts"
            )
        if not text.strip():
            raise TTSError("Empty text.")

        voice = self._pick_voice(text, language)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            communicate = edge_tts.Communicate(  # type: ignore
                text=text,
                voice=voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )
            await communicate.save(str(out))
        except Exception as exc:  # noqa: BLE001
            logger.error("edge_tts_synthesize_failed", voice=voice, error=str(exc))
            raise TTSError(f"Edge TTS synthesis failed: {exc}") from exc

        if not out.exists():
            raise TTSError("Edge TTS produced no output file.")

        return str(out)