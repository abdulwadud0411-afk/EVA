"""
TTS provider registry (Phase 9).

Reads `voice.tts.provider` from config and instantiates the matching
TTSProvider.

This module ensures provider registration happens lazily but reliably,
so callers never see an empty registry by mistake.
"""
from __future__ import annotations

from typing import Dict, List, Type

from app.core.config_manager import ConfigManager, ConfigurationError
from app.voice.tts_base import TTSProvider


class TTSRegistry:
    _providers: Dict[str, Type[TTSProvider]] = {}
    _registration_done: bool = False

    @classmethod
    def register(cls, name: str, provider_cls: Type[TTSProvider]) -> None:
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def _ensure_registered(cls) -> None:
        """Import provider modules to trigger registration, exactly once."""
        if cls._registration_done:
            return
        try:
            import app.voice.tts_providers  # noqa: F401
        except Exception:  # noqa: BLE001
            pass
        cls._registration_done = True

    @classmethod
    def list_providers(cls) -> List[str]:
        cls._ensure_registered()
        return sorted(cls._providers.keys())

    @classmethod
    def get_active_provider(cls) -> TTSProvider:
        cls._ensure_registered()

        name = str(ConfigManager.get("voice.tts.provider", "edge")).lower()
        provider_cls = cls._providers.get(name)
        if provider_cls is None:
            raise ConfigurationError(
                f"TTS provider '{name}' is not registered. "
                f"Available: {cls.list_providers()}"
            )
        section = ConfigManager.get(f"voice.tts.{name}", {}) or {}
        return provider_cls(section)