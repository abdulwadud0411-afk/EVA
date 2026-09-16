"""
EVA Voice System (Phase 8-9).

Modules:
    base              — STTProvider abstract base class
    interface         — TranscriptionResult and other data models
    microphone        — sounddevice-based recording
    stt_registry      — registry for STT providers
    stt_providers     — concrete STT adapters
    tts_base          — TTSProvider abstract base class
    tts               — SpeakController
    tts_registry      — registry for TTS providers
    tts_providers     — concrete TTS adapters
"""
from app.voice.interface import TranscriptionResult, RecordingResult  # noqa: F401
from app.voice.base import STTProvider, STTError  # noqa: F401
from app.voice.tts_base import TTSProvider, TTSError  # noqa: F401