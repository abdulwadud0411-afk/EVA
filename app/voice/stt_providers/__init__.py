"""
Registers every available STT provider.

Importing this module ensures all adapters are registered with
`STTRegistry` before use.
"""
from app.voice.stt_registry import STTRegistry
from app.voice.stt_providers.faster_whisper_stt import FasterWhisperSTT

STTRegistry.register("faster-whisper", FasterWhisperSTT)
STTRegistry.register("faster_whisper", FasterWhisperSTT)