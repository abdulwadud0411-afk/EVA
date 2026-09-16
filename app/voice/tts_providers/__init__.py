"""
Registers every available TTS provider (Phase 9).

Importing this module ensures all adapters are registered with
`TTSRegistry` before use.
"""
from app.voice.tts_registry import TTSRegistry
from app.voice.tts_providers.piper_tts import PiperTTS
from app.voice.tts_providers.edge_tts import EdgeTTS

TTSRegistry.register("piper", PiperTTS)
TTSRegistry.register("edge", EdgeTTS)
TTSRegistry.register("edge-tts", EdgeTTS)