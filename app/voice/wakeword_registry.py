"""
Wake-word provider registry (Phase 10).

Reads `voice.wake_word.mode` and instantiates the correct provider:
    - "offline"  : openWakeWord only
    - "stt"      : STT-based detection only
    - "hybrid"   : openWakeWord as gate, STT as verifier
"""
from __future__ import annotations

from typing import Dict, List, Type

from app.core.config_manager import ConfigManager, ConfigurationError
from app.voice.wakeword_base import WakeWordProvider


class WakeWordRegistry:
    _providers: Dict[str, Type[WakeWordProvider]] = {}
    _registration_done: bool = False

    @classmethod
    def register(cls, name: str, provider_cls: Type[WakeWordProvider]) -> None:
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def _ensure_registered(cls) -> None:
        if cls._registration_done:
            return
        try:
            import app.voice.wakeword_providers  # noqa: F401
        except Exception:
            pass
        cls._registration_done = True

    @classmethod
    def list_providers(cls) -> List[str]:
        cls._ensure_registered()
        return sorted(cls._providers.keys())

    @classmethod
    def get_provider(cls, name: str) -> WakeWordProvider:
        """Return a specific provider by name."""
        cls._ensure_registered()
        key = name.lower()
        provider_cls = cls._providers.get(key)
        if provider_cls is None:
            raise ConfigurationError(
                f"Wake-word provider '{name}' is not registered. "
                f"Available: {cls.list_providers()}"
            )
        section = ConfigManager.get(f"voice.wake_word.{key}", {}) or {}
        return provider_cls(section)

    @classmethod
    def get_active_provider(cls) -> WakeWordProvider:
        """
        Return the provider selected by `voice.wake_word.mode`.

        Modes:
            offline -> "openwakeword"
            stt     -> "stt_verify"
            hybrid  -> "openwakeword" (with STT verification in the detector)
        """
        cls._ensure_registered()
        mode = str(ConfigManager.get("voice.wake_word.mode", "hybrid")).lower()
        mapping = {
            "offline": "openwakeword",
            "stt": "stt_verify",
            "hybrid": "openwakeword",
        }
        provider_name = mapping.get(mode)
        if provider_name is None:
            raise ConfigurationError(f"Unknown wake_word.mode: {mode}")
        return cls.get_provider(provider_name)