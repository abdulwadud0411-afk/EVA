"""
Registers every available wake-word provider (Phase 10).

Registers:
    - "openwakeword" : openWakeWord neural detector
    - "stt_verify"   : Faster-Whisper STT-based phrase matcher
"""
from app.voice.wakeword_registry import WakeWordRegistry
from app.voice.wakeword_providers.openwakeword_provider import OpenWakeWordProvider
from app.voice.wakeword_providers.stt_verify_provider import STTVerifyProvider

WakeWordRegistry.register("openwakeword", OpenWakeWordProvider)
WakeWordRegistry.register("stt_verify", STTVerifyProvider)