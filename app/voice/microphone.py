"""
Microphone recording (Phase 8 + Phase 10 auto-detect).

Records audio from the default input device as 16 kHz mono WAV.
Stops automatically after silence or a maximum duration.

Auto-detection:
    1. If `voice.stt.device_index` is set and not "auto", use it.
    2. Otherwise pick the system default input device.
    3. If opening the default fails, try a fallback chain
       (all input devices in order until one works).
    4. On complete failure, raise a clear error.
"""
from __future__ import annotations

import math
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)

try:
    import numpy as np  # type: ignore
    import sounddevice as sd  # type: ignore
    import soundfile as sf  # type: ignore
    _AUDIO_AVAILABLE = True
except Exception:  # noqa: BLE001
    np = None  # type: ignore
    sd = None  # type: ignore
    sf = None  # type: ignore
    _AUDIO_AVAILABLE = False


class MicrophoneError(Exception):
    """Raised when microphone capture fails."""


# ---------------------------------------------------------------------- #
# Device discovery
# ---------------------------------------------------------------------- #
def is_available() -> bool:
    """Return True if sounddevice + soundfile are usable."""
    return _AUDIO_AVAILABLE


def _list_input_devices() -> List[int]:
    """Return indexes of every device that can capture input."""
    if not _AUDIO_AVAILABLE:
        return []
    indexes: List[int] = []
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                indexes.append(i)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mic_list_devices_failed", error=str(exc))
    return indexes


def _resolve_device_index() -> Optional[int]:
    """
    Choose the microphone device index.

    Precedence:
        1. Explicit config value (if not "auto"/None/empty)
        2. System default input device
        3. First working input device from the fallback chain
    """
    if not _AUDIO_AVAILABLE:
        return None

    # 1. Explicit config
    raw = ConfigManager.get("voice.stt.device_index", "auto")
    if raw not in (None, "", "auto", "default", -1):
        try:
            idx = int(raw)
            logger.info("mic_using_config_index", index=idx)
            return idx
        except (TypeError, ValueError):
            logger.warning("mic_config_index_invalid", value=raw)

    # 2. System default
    try:
        default_dev = sd.default.device  # (input, output) or single value
        if isinstance(default_dev, (tuple, list)) and default_dev:
            default_in = default_dev[0]
            if default_in is not None and int(default_in) >= 0:
                logger.info("mic_using_system_default", index=int(default_in))
                return int(default_in)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mic_default_lookup_failed", error=str(exc))

    # 3. Fallback chain
    candidates = _list_input_devices()
    if candidates:
        logger.info("mic_using_fallback_chain", candidates=candidates)
        return candidates[0]

    logger.error("mic_no_input_device_found")
    return None


def _try_open_stream(
    device_index: Optional[int],
    sample_rate: int,
    channels: int,
    block_frames: int,
):
    """
    Try opening an InputStream. Returns the stream, or raises.

    If `device_index` is None, opens the OS default.
    """
    return sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        blocksize=block_frames,
        device=device_index,
    )


def _open_best_stream(sample_rate: int, channels: int, block_frames: int):
    """
    Open the best available microphone stream.

    Tries the resolved index first; if it fails, falls back to each
    input device in order until one succeeds.
    """
    resolved = _resolve_device_index()

    # Try resolved index (or default if None)
    try:
        stream = _try_open_stream(resolved, sample_rate, channels, block_frames)
        logger.info("mic_stream_opened", device=resolved)
        return stream, resolved
    except Exception as exc:  # noqa: BLE001
        logger.warning("mic_open_failed", device=resolved, error=str(exc))

    # Fallback chain
    for idx in _list_input_devices():
        if idx == resolved:
            continue
        try:
            stream = _try_open_stream(idx, sample_rate, channels, block_frames)
            logger.info("mic_stream_opened_fallback", device=idx)
            return stream, idx
        except Exception as exc:  # noqa: BLE001
            logger.warning("mic_open_failed_fallback", device=idx, error=str(exc))
            continue

    raise MicrophoneError(
        "Could not open any microphone. "
        "Check Windows Sound settings and make sure a mic is connected."
    )


# ---------------------------------------------------------------------- #
# Recording
# ---------------------------------------------------------------------- #
def _recordings_dir() -> Path:
    base = ConfigManager.get_data_dir()
    d = base / "recordings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamped_path(prefix: str = "rec") -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]
    return _recordings_dir() / f"{prefix}_{ts}.wav"


def record_until_silence(
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    silence_threshold: Optional[float] = None,
    silence_duration: Optional[float] = None,
    max_seconds: Optional[float] = None,
    block_duration: float = 0.1,
) -> str:
    """
    Record from the default microphone until silence or a max duration.

    Returns the absolute path to a mono 16-bit WAV file.
    """
    if not _AUDIO_AVAILABLE:
        raise MicrophoneError(
            "Microphone not available (sounddevice/soundfile/numpy missing)."
        )

    sr = int(sample_rate or ConfigManager.get("voice.stt.sample_rate", 16000))
    ch = int(channels or ConfigManager.get("voice.stt.channels", 1))
    thr = float(silence_threshold or ConfigManager.get("voice.stt.silence_threshold", 0.01))
    sil_dur = float(silence_duration or ConfigManager.get("voice.stt.silence_duration", 1.5))
    max_sec = float(max_seconds or ConfigManager.get("voice.stt.max_record_seconds", 30))

    block_frames = int(sr * block_duration)
    blocks = []
    silence_blocks = 0
    silence_limit = max(1, int(sil_dur / block_duration))
    started = time.time()

    logger.info("microphone_recording_start", sample_rate=sr, channels=ch)

    stream, used_device = _open_best_stream(sr, ch, block_frames)

    try:
        with stream:
            while True:
                elapsed = time.time() - started
                if elapsed >= max_sec:
                    logger.info("microphone_max_duration_reached", elapsed=elapsed)
                    break

                data, overflowed = stream.read(block_frames)
                if overflowed:
                    logger.warning("microphone_overflow")

                blocks.append(data.copy())

                rms = float(
                    np.sqrt(np.mean(data.astype(np.float32) ** 2)) / 32768.0
                )
                if rms < thr:
                    silence_blocks += 1
                else:
                    silence_blocks = 0

                if silence_blocks >= silence_limit and len(blocks) > silence_limit + 2:
                    logger.info(
                        "microphone_silence_detected",
                        silence_blocks=silence_blocks,
                    )
                    break
    except MicrophoneError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MicrophoneError(f"Microphone capture failed: {exc}") from exc

    if not blocks:
        raise MicrophoneError("No audio captured.")

    audio = np.concatenate(blocks, axis=0)
    path = _timestamped_path("rec")

    try:
        sf.write(str(path), audio, sr, subtype="PCM_16")
    except Exception as exc:  # noqa: BLE001
        raise MicrophoneError(f"Failed to save audio: {exc}") from exc

    duration = len(audio) / float(sr)
    logger.info(
        "microphone_recording_saved",
        path=str(path),
        duration=duration,
        device=used_device,
    )
    return str(path)