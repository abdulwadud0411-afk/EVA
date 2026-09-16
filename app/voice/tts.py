"""
TTS controller (Phase 9).

`SpeakController` wraps the active TTS provider, synthesizes speech,
and plays it through the default speaker — no external media player
window, no perceptible delay.

Playback strategy:
    1. Synthesize to MP3 (Edge TTS) or WAV (Piper).
    2. If MP3, transcode to a temporary WAV using `av`.
    3. Play the WAV directly with sounddevice.
    4. Only fall back to the OS handler if sounddevice is unavailable.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.voice.tts_base import TTSProvider, TTSError
from app.voice.tts_registry import TTSRegistry

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Paths
# ---------------------------------------------------------------------- #
def _cache_dir() -> Path:
    base = ConfigManager.get_data_dir()
    d = base / "cache" / "tts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamped_path(suffix: str = "mp3") -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]
    return _cache_dir() / f"speak_{ts}.{suffix}"


# ---------------------------------------------------------------------- #
# MP3 → WAV transcoder
# ---------------------------------------------------------------------- #
def _transcode_mp3_to_wav(mp3_path: Path) -> Optional[Path]:
    """
    Transcode an MP3 file to a temp WAV using PyAV (bundled with
    faster-whisper). Returns the WAV path, or None on failure.
    """
    try:
        import av  # type: ignore
    except Exception:  # noqa: BLE001
        logger.warning("av_not_available")
        return None

    wav_path = mp3_path.with_suffix(".wav")
    try:
        container = av.open(str(mp3_path))
        stream = container.streams.audio[0]

        out = av.open(str(wav_path), mode="w", format="wav")
        out_stream = out.add_stream("pcm_s16le", rate=stream.rate)

        for frame in container.decode(stream):
            for packet in out_stream.encode(frame):
                out.mux(packet)

        # Flush
        for packet in out_stream.encode():
            out.mux(packet)

        out.close()
        container.close()
        return wav_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("mp3_to_wav_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Audio playback
# ---------------------------------------------------------------------- #
def _play_audio(path: str) -> None:
    """
    Play an audio file through the default output device — instant,
    no external media player window.
    """
    p = Path(path)
    if not p.exists():
        raise TTSError(f"Audio file missing: {path}")

    audio_path: Optional[Path] = p

    # If it's MP3, transcode to WAV first
    if p.suffix.lower() == ".mp3":
        wav = _transcode_mp3_to_wav(p)
        if wav is not None and wav.exists():
            audio_path = wav
        else:
            audio_path = None

    # Try sounddevice playback (works best for WAV)
    if audio_path is not None:
        try:
            import sounddevice as sd  # type: ignore
            import soundfile as sf  # type: ignore

            data, sr = sf.read(str(audio_path), dtype="float32")
            sd.play(data, sr)
            sd.wait()
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("sounddevice_play_failed", error=str(exc))

    # Fallback: let the OS handle it (opens Media Player, slower)
    if os.name == "nt":
        try:
            os.startfile(str(p))  # type: ignore[attr-defined]
            import time
            time.sleep(0.3)
            return
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"Windows playback failed: {exc}") from exc

    raise TTSError("No audio playback backend available.")


# ---------------------------------------------------------------------- #
# SpeakController
# ---------------------------------------------------------------------- #
class SpeakController:
    """High-level controller used by the agent to speak responses."""

    def __init__(self, provider: Optional[TTSProvider] = None) -> None:
        self._provider = provider
        self._lock = asyncio.Lock()

    def _get_provider(self) -> TTSProvider:
        if self._provider is None:
            self._provider = TTSRegistry.get_active_provider()
        return self._provider

    async def warm_up(self) -> bool:
        try:
            return await self._get_provider().warm_up()
        except Exception as exc:  # noqa: BLE001
            logger.error("tts_warm_up_failed", error=str(exc))
            return False

    async def speak(self, text: str, language: Optional[str] = None) -> bool:
        """
        Synthesize and play `text`. Returns True on success.
        Never raises for playback errors — just logs and returns False.
        """
        text = (text or "").strip()
        if not text:
            return False

        provider = self._get_provider()
        suffix = "mp3" if provider.name == "EdgeTTS" else "wav"
        path = _timestamped_path(suffix=suffix)

        async with self._lock:
            try:
                out = await provider.synthesize(text, str(path), language=language)
            except TTSError as exc:
                logger.error("tts_synthesize_failed", error=str(exc))
                return False
            except Exception as exc:  # noqa: BLE001
                logger.error("tts_synthesize_unexpected", error=str(exc))
                return False

            try:
                # Run blocking playback in a worker thread so the asyncio
                # loop is not frozen while audio plays.
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _play_audio, out)
            except TTSError as exc:
                logger.error("tts_playback_failed", error=str(exc))
                return False
            except Exception as exc:  # noqa: BLE001
                logger.error("tts_playback_unexpected", error=str(exc))
                return False

        return True