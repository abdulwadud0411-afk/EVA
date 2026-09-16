"""
Hybrid wake-word detector (Phase 10).

Flow:
    Microphone ──▶ openWakeWord (fast gate) ──▶ STT verify (accurate)
                                    │
                                    └── if verified ──▶ WAKE_WORD_DETECTED

Modes (config: voice.wake_word.mode):
    - "offline" : openWakeWord only (fast, inaccurate for custom phrases)
    - "stt"     : STT verification only (slow, accurate)
    - "hybrid"  : openWakeWord gate + STT verify (default, best)
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable, Optional

import numpy as np

from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger
from app.voice.wakeword_base import WakeWordDetection
from app.voice.wakeword_registry import WakeWordRegistry

logger = get_logger(__name__)

_SAMPLE_RATE = 16000


class WakeWordDetector:
    """
    Hybrid wake-word detector.

    Usage:
        detector = WakeWordDetector(event_bus=bus)
        await detector.start()
        ... later ...
        await detector.stop()

    Publishes Event("WAKE_WORD_DETECTED", {...}) whenever the phrase
    is verified (or detected in offline mode).
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        on_detected: Optional[Callable[[WakeWordDetection], None]] = None,
    ) -> None:
        self.event_bus = event_bus or EventBus()
        self.on_detected = on_detected

        self.mode = str(ConfigManager.get("voice.wake_word.mode", "hybrid")).lower()
        self.enabled = bool(ConfigManager.get("voice.wake_word.enabled", True))
        self.cooldown = float(ConfigManager.get("voice.wake_word.cooldown_seconds", 2.0))

        # Providers (populated in start())
        self._gate = None          # openWakeWord
        self._verifier = None      # STT-based

        # Runtime state
        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._last_trigger: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> bool:
        if not self.enabled:
            logger.info("wakeword_disabled")
            return False
        if self._running:
            return True

        # Instantiate providers based on mode
        try:
            if self.mode in ("offline", "hybrid"):
                self._gate = WakeWordRegistry.get_provider("openwakeword")
            if self.mode in ("stt", "hybrid"):
                self._verifier = WakeWordRegistry.get_provider("stt_verify")
        except Exception as exc:  # noqa: BLE001
            logger.error("wakeword_provider_init_failed", error=str(exc))
            return False

        # Warm up
        if self._gate is not None:
            ok = await self._gate.warm_up()
            if not ok:
                logger.warning("wakeword_gate_warmup_failed")
                self._gate = None
        if self._verifier is not None:
            ok = await self._verifier.warm_up()
            if not ok:
                logger.warning("wakeword_verifier_warmup_failed")
                self._verifier = None

                # If both providers are unavailable, don't start
        if self._gate is None and self._verifier is None:
            logger.error("wakeword_no_provider_available")
            return False

        # Mode may need adjusting if one provider is unavailable
        if self.mode == "hybrid":
            if self._gate is None and self._verifier is not None:
                self.mode = "stt"
            elif self._verifier is None and self._gate is not None:
                self.mode = "offline"

        # Start background listening thread
        self._stop_flag.clear()
        self._running = True
        self._loop_thread = threading.Thread(
            target=self._listen_loop, name="eva-wakeword", daemon=True,
        )
        self._loop_thread.start()
        logger.info("wakeword_started", mode=self.mode)
        return True

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_flag.set()
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=3.0)
            self._loop_thread = None
        if self._gate is not None:
            try:
                self._gate.reset()
            except Exception:  # noqa: BLE001
                pass
        logger.info("wakeword_stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------ #
    # Background listening loop
    # ------------------------------------------------------------------ #
    def _listen_loop(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("wakeword_sounddevice_missing", error=str(exc))
            self._running = False
            return

        block_seconds = 0.1
        block_frames = int(_SAMPLE_RATE * block_seconds)

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=block_frames,
            ) as stream:
                while not self._stop_flag.is_set():
                    data, overflowed = stream.read(block_frames)
                    if overflowed:
                        continue
                    chunk = np.frombuffer(data.tobytes(), dtype=np.int16)
                    self._process_blocking(chunk)
        except Exception as exc:  # noqa: BLE001
            # IMPORTANT: if this happens during stop(), it is not an error.
            if not self._stop_flag.is_set():
                logger.error("wakeword_listen_loop_failed", error=str(exc))
                self._running = False

        block_seconds = 0.1
        block_frames = int(_SAMPLE_RATE * block_seconds)

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=block_frames,
            ) as stream:
                while not self._stop_flag.is_set():
                    data, overflowed = stream.read(block_frames)
                    if overflowed:
                        continue
                    chunk = np.frombuffer(data.tobytes(), dtype=np.int16)
                    self._process_blocking(chunk)
        except Exception as exc:  # noqa: BLE001
            logger.error("wakeword_listen_loop_failed", error=str(exc))
            self._running = False

    def _process_blocking(self, chunk: np.ndarray) -> None:
        """Called from the background thread for every 100ms block."""
        if self._gate is None and self._verifier is None:
            return

        # Cooldown check
        if time.time() - self._last_trigger < self.cooldown:
            return

        detection: WakeWordDetection = WakeWordDetection(triggered=False)

        # Step 1 — fast gate
        if self.mode in ("offline", "hybrid") and self._gate is not None:
            gate_det = self._run_async(self._gate.process_chunk(chunk))
            if gate_det is not None and gate_det.triggered:
                if self.mode == "offline":
                    detection = gate_det
                else:
                    # Step 2 — STT verify on the same chunk
                    if self._verifier is not None:
                        # Give the verifier a slightly larger window of audio
                        verified = self._run_async(
                            self._verifier.process_chunk(chunk)
                        )
                        if verified is not None and verified.triggered:
                            detection = verified

        # STT-only mode
        elif self.mode == "stt" and self._verifier is not None:
            verified = self._run_async(self._verifier.process_chunk(chunk))
            if verified is not None and verified.triggered:
                detection = verified

        if detection.triggered:
            self._last_trigger = time.time()
            self._on_detection(detection)

    def _on_detection(self, det: WakeWordDetection) -> None:
        logger.info(
            "wakeword_detected",
            phrase=det.phrase,
            confidence=det.confidence,
            mode=self.mode,
        )
        try:
            self.event_bus.publish(
                Event(
                    "WAKE_WORD_DETECTED",
                    {
                        "phrase": det.phrase,
                        "confidence": det.confidence,
                        "mode": self.mode,
                        "metadata": det.metadata,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("wakeword_event_publish_failed", error=str(exc))

        if self.on_detected is not None:
            try:
                self.on_detected(det)
            except Exception as exc:  # noqa: BLE001
                logger.warning("wakeword_on_detected_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    # Async bridge
    # ------------------------------------------------------------------ #
    def _run_async(self, coro) -> Optional[WakeWordDetection]:
        """
        Run an async provider call from the background (sync) thread
        using a fresh event loop.
        """
        with self._lock:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            except Exception as exc:  # noqa: BLE001
                logger.warning("wakeword_async_call_failed", error=str(exc))
                return None
            finally:
                loop.close()