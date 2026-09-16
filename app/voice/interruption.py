"""
Interruption / barge-in handler (Phase 10).

While EVA is speaking (or running a task), the user can say:
    - "stop"
    - "eva stop"
    - "be quiet"
    - "shut up"

The detector listens in short windows, STT-verifies the phrase, and
publishes Event("INTERRUPT_REQUESTED") which the TTS layer and the
agent loop react to.

Usage:
    interruption = InterruptionHandler(event_bus=bus)
    await interruption.start()
    ...
    await interruption.stop()
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger

logger = get_logger(__name__)

_SAMPLE_RATE = 16000


def _normalize(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(out).split())


class InterruptionHandler:
    """Background listener that fires INTERRUPT_REQUESTED on stop phrases."""

        # Fallback phrases if config section is missing (e.g. in isolated tests)
    _DEFAULT_PHRASES = ["stop", "eva stop", "be quiet", "shut up"]

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.enabled = bool(ConfigManager.get("voice.interruption.enabled", True))

        raw_phrases = ConfigManager.get("voice.interruption.phrases", None)
        if not raw_phrases:
            raw_phrases = self._DEFAULT_PHRASES
        self.phrases = [_normalize(p) for p in raw_phrases if p]

        self.check_interval = float(
            ConfigManager.get("voice.interruption.check_interval_seconds", 1.0)
        )

        self._stt = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._last_fired = 0.0

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> bool:
        if not self.enabled:
            return False
        if self._running:
            return True

        try:
            from app.voice.stt_registry import STTRegistry
            self._stt = STTRegistry.get_active_provider()
            ok = await self._stt.warm_up()
            if not ok:
                logger.warning("interruption_stt_warmup_failed")
                return False
        except Exception as exc:  # noqa: BLE001
            logger.error("interruption_stt_init_failed", error=str(exc))
            return False

        self._stop_flag.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, name="eva-interruption", daemon=True,
        )
        self._thread.start()
        logger.info("interruption_started", phrases=self.phrases)
        return True

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("interruption_stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------ #
    # Background loop
    # ------------------------------------------------------------------ #
    def _listen_loop(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("interruption_sounddevice_missing", error=str(exc))
            self._running = False
            return

        window_seconds = max(0.8, min(3.0, self.check_interval * 1.5))
        block_frames = int(_SAMPLE_RATE * window_seconds)

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=block_frames,
            ) as stream:
                while not self._stop_flag.is_set():
                    data, _ = stream.read(block_frames)
                    chunk = np.frombuffer(data.tobytes(), dtype=np.int16)
                    # Cooldown
                    if time.time() - self._last_fired < 1.5:
                        continue
                    self._process_blocking(chunk)
        except Exception as exc:  # noqa: BLE001
            logger.error("interruption_listen_loop_failed", error=str(exc))
            self._running = False

    def _process_blocking(self, chunk: np.ndarray) -> None:
        if self._stt is None:
            return

        # Skip if audio is silent
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0)
        if rms < 0.005:
            return

        transcript = self._transcribe(chunk)
        if not transcript:
            return

        text = _normalize(transcript)
        for phrase in self.phrases:
            if phrase and phrase in text:
                self._last_fired = time.time()
                logger.info("interruption_fired", phrase=phrase, transcript=transcript)
                try:
                    self.event_bus.publish(
                        Event(
                            "INTERRUPT_REQUESTED",
                            {"phrase": phrase, "transcript": transcript},
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("interruption_event_failed", error=str(exc))
                return

    def _transcribe(self, chunk: np.ndarray) -> str:
        tmp_path: Optional[Path] = None
        try:
            import soundfile as sf  # type: ignore
            fd, name = tempfile.mkstemp(suffix=".wav")
            try:
                os.close(fd)
            except OSError:
                pass
            tmp_path = Path(name)
            sf.write(str(tmp_path), chunk, _SAMPLE_RATE, subtype="PCM_16")

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    self._stt.transcribe(str(tmp_path))
                )
            finally:
                loop.close()
            return result.text or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("interruption_transcribe_failed", error=str(exc))
            return ""
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass