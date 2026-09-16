"""
Abstract AI provider interface.

Every provider (DeepSeek, OpenAI, Anthropic, ...) implements this ABC.
The agent core MUST depend only on this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.brain.response_models import AIResponse


class AIProvider(ABC):
    """Provider-agnostic LLM interface."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """Return a normalized AIResponse."""
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """
        Feature flags the agent & GUI can query.

        Expected keys (missing = False):
            supports_tool_calling, supports_vision, supports_reasoning,
            supports_streaming, supports_json, supports_audio
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_api_key(self) -> bool:
        """Return True if the currently configured credentials work."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__