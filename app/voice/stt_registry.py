"""
STT provider registry (Phase 8).

Reads `voice.stt.provider` from config and instantiates the matching
STTProvider.

This module ensures provider registration happens lazily but reliably.
"""
from __future__ import annotations

from typing import Dict, List, Type

from app.core.config_manager import ConfigManager, ConfigurationError
from app.voice.base import STTProvider


class STTRegistry:
    _providers: Dict[str, Type[STTProvider]] = {}
    _registration_done: bool = False

    @classmethod
    def register(cls, name: str, provider_cls: Type[STTProvider]) -> None:
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def _ensure_registered(cls) -> None:
        if cls._registration_done:
            return
        try:
            import app.voice.stt_providers  # noqa: F401
        except Exception:  # noqa: BLE001
            pass
        cls._registration_done = True

    @classmethod
    def list_providers(cls) -> List[str]:
        cls._ensure_registered()
        return sorted(cls._providers.keys())

    @classmethod
    def get_active_provider(cls) -> STTProvider:
        cls._ensure_registered()

        name = str(ConfigManager.get("voice.stt.provider", "faster-whisper")).lower()
        provider_cls = cls._providers.get(name)
        if provider_cls is None:
            raise ConfigurationError(
                f"STT provider '{name}' is not registered. "
                f"Available: {cls.list_providers()}"
            )
        section = ConfigManager.get(f"voice.stt.{name.replace('-', '_')}", {}) or {}
        return provider_cls(section)