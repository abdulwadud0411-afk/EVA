"""
Provider registry - instantiates the active AIProvider from configuration.

Registration happens at import time of `app.brain.providers`.
"""
from __future__ import annotations

from typing import Dict, List, Type

from app.brain.base import AIProvider
from app.core.config_manager import ConfigManager, ConfigurationError


class ProviderRegistry:
    _providers: Dict[str, Type[AIProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: Type[AIProvider]) -> None:
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def list_providers(cls) -> List[str]:
        return sorted(cls._providers.keys())

    @classmethod
    def get_active_provider(cls) -> AIProvider:
        """Instantiate the provider selected in config (ai.provider)."""
        name = str(ConfigManager.get("ai.provider", "deepseek")).lower()
        provider_cls = cls._providers.get(name)
        if provider_cls is None:
            raise ConfigurationError(
                f"AI provider '{name}' is not registered. "
                f"Available: {cls.list_providers()}"
            )
        section = ConfigManager.get(f"ai.{name}", {}) or {}
        return provider_cls(section)