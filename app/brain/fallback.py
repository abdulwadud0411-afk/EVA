"""
Fallback provider wrapper (Phase 18).

Wraps a primary AIProvider. If the primary raises a "retriable" error
(rate limit, timeout, network error, server error), automatically tries
the next provider in the chain.

Implements the AIProvider ABC so it can be dropped in anywhere.
"""
from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional

from app.brain.base import AIProvider
from app.brain.provider_registry import ProviderRegistry
from app.brain.response_models import AIResponse
from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


# Error codes that trigger fallback
_RETRIABLE_MARKERS = (
    "429",
    "rate limit",
    "timeout",
    "timed out",
    "network",
    "connection",
    "unreachable",
    "500",
    "502",
    "503",
    "504",
)


def _is_retriable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _RETRIABLE_MARKERS)


class FallbackProvider(AIProvider):
    """Primary → chain fallback wrapper."""

    def __init__(
        self,
        primary: AIProvider,
        fallback_chain: List[str],
        primary_name: str = "",
    ) -> None:
        self._primary = primary
        self._primary_name = primary_name or self._provider_name(primary)
        # Remove the primary from the fallback chain (avoid duplicates)
        self._fallback_names = [
            n for n in (fallback_chain or [])
            if n and n.lower() != self._primary_name.lower()
        ]
        self._fallback_instances: Dict[str, AIProvider] = {}

    # ------------------------------------------------------------------ #
    # AIProvider API
    # ------------------------------------------------------------------ #
    @property
    def capabilities(self) -> Dict[str, bool]:
        return self._primary.capabilities

    async def validate_api_key(self) -> bool:
        return await self._primary.validate_api_key()

    @property
    def name(self) -> str:
        return f"Fallback({self._primary_name})"

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> AIResponse:
        # 1. Try primary
        primary_error: Optional[Exception] = None
        try:
            return await self._primary.generate(
                messages, tools=tools, tool_choice=tool_choice, **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            if not _is_retriable(exc):
                logger.warning(
                    "fallback_skip_non_retriable",
                    provider=self._primary_name,
                    error=str(exc),
                )
                raise
            primary_error = exc
            logger.warning(
                "fallback_primary_failed",
                provider=self._primary_name,
                error=str(exc),
            )

        # 2. Try each fallback in order
        last_error: Optional[Exception] = None
        for name in self._fallback_names:
            provider = self._get_fallback(name)
            if provider is None:
                continue
            try:
                logger.info("fallback_trying", provider=name)
                return await provider.generate(
                    messages, tools=tools, tool_choice=tool_choice, **kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "fallback_provider_failed",
                    provider=name,
                    error=str(exc),
                )
                last_error = exc
                continue

        # 3. All failed — re-raise the most relevant error
        if last_error is not None:
            raise last_error
        if primary_error is not None:
            raise primary_error
        raise RuntimeError(
            "All providers in the fallback chain failed (no fallback available)."
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _get_fallback(self, name: str) -> Optional[AIProvider]:
        if name in self._fallback_instances:
            return self._fallback_instances[name]

        # Look up provider class from the registry
        from app.brain import provider_registry as _registry_module
        cls = _registry_module.ProviderRegistry._providers.get(name.lower())
        if cls is None:
            logger.warning("fallback_unknown_provider", provider=name)
            return None

        section = ConfigManager.get(f"ai.{name}", {}) or {}
        try:
            instance = cls(section)
        except Exception as exc:  # noqa: BLE001
            logger.warning("fallback_init_failed", provider=name, error=str(exc))
            return None

        self._fallback_instances[name] = instance
        return instance

    @staticmethod
    def _provider_name(provider: AIProvider) -> str:
        # Try to use the provider's actual name attribute first
        name = getattr(provider, "name", "") or type(provider).__name__
        # Strip "Provider" suffix, lowercase for consistency
        for suffix in ("Provider", "TTS"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name.lower()