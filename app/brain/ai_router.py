"""
AI Router (Phase 18).

Picks the best provider/model for a request based on configured rules.

Public API:
    router = AIRouter.from_config()
    provider = router.resolve(context)   # returns (provider_name, model)
    response = await router.generate(messages, tools=..., ctx=...)

The router respects:
    - explicit user override (ctx.explicit_provider)
    - routing.enabled = false → always use primary
    - routing.mode = "manual" → always use primary
    - fallback chain on failure
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.brain.base import AIProvider
from app.brain.fallback import FallbackProvider
from app.brain.provider_registry import ProviderRegistry
from app.brain.response_models import AIResponse
from app.brain.routing_rules import (
    RoutingContext,
    RoutingRule,
    RuleMatch,
    default_rules,
)
from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RoutingDecision:
    """The router's decision for a request."""
    provider: str
    model: str = ""
    rule_name: str = ""
    reasoning: str = ""
    fallback_chain: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "rule_name": self.rule_name,
            "reasoning": self.reasoning,
            "fallback_chain": list(self.fallback_chain),
        }


class AIRouter:
    def __init__(
        self,
        rules: List[RoutingRule],
        fallback_chain: List[str],
        enabled: bool = True,
        mode: str = "auto",
    ) -> None:
        self.rules = sorted(rules, key=lambda r: r.priority)
        self.fallback_chain = list(fallback_chain)
        self.enabled = enabled
        self.mode = mode.lower()

    # ------------------------------------------------------------------ #
    # Factory
    # ------------------------------------------------------------------ #
    @classmethod
    def from_config(cls) -> "AIRouter":
        """Build a router from config.yaml."""
        enabled = bool(ConfigManager.get("ai.routing.enabled", True))
        mode = str(ConfigManager.get("ai.routing.mode", "auto")).lower()
        fallback_chain = ConfigManager.get("ai.fallback.chain", None)
        if not isinstance(fallback_chain, list):
            fallback_chain = []

        # Load user rules from config, else use defaults
        raw_rules = ConfigManager.get("ai.routing.rules", None)
        if isinstance(raw_rules, list) and raw_rules:
            rules = [RoutingRule.from_dict(r) for r in raw_rules if isinstance(r, dict)]
        else:
            rules = default_rules()

        return cls(
            rules=rules,
            fallback_chain=fallback_chain,
            enabled=enabled,
            mode=mode,
        )

    # ------------------------------------------------------------------ #
    # Resolve
    # ------------------------------------------------------------------ #
    def resolve(self, ctx: RoutingContext) -> RoutingDecision:
        """Pick the best provider/model for the request."""
        # 1. Disabled → use primary
        if not self.enabled or self.mode == "manual":
            primary = str(ConfigManager.get("ai.provider", "deepseek")).lower()
            return RoutingDecision(
                provider=primary,
                model="",
                rule_name="disabled_or_manual",
                reasoning="routing disabled or in manual mode",
                fallback_chain=self.fallback_chain,
            )

        # 2. Explicit override
        if ctx.explicit_provider:
            return RoutingDecision(
                provider=ctx.explicit_provider.lower(),
                model=ctx.explicit_model or "",
                rule_name="explicit_override",
                reasoning="user override",
                fallback_chain=self.fallback_chain,
            )

        # 3. Try each rule in priority order
        for rule in self.rules:
            # Skip the explicit_override rule (already handled above)
            if rule.name == "explicit_override":
                continue
            if rule.matches(ctx):
                provider = rule.provider or str(
                    ConfigManager.get("ai.provider", "deepseek")
                ).lower()
                model = rule.model or self._default_model(provider)
                logger.info(
                    "router_match",
                    rule=rule.name,
                    provider=provider,
                    model=model,
                )
                return RoutingDecision(
                    provider=provider,
                    model=model,
                    rule_name=rule.name,
                    reasoning=rule.description,
                    fallback_chain=self.fallback_chain,
                )

        # 4. No rule matched → primary default
        primary = str(ConfigManager.get("ai.provider", "deepseek")).lower()
        return RoutingDecision(
            provider=primary,
            model="",
            rule_name="no_match",
            reasoning="no rule matched",
            fallback_chain=self.fallback_chain,
        )

    # ------------------------------------------------------------------ #
    # Generate
    # ------------------------------------------------------------------ #
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[RoutingContext] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """Resolve the target and call it via FallbackProvider."""
        ctx = ctx or RoutingContext(text=self._extract_text(messages))
        decision = self.resolve(ctx)

        logger.info("router_generate", decision=decision.to_dict())

        # Build the primary provider
        primary = self._build_provider(decision.provider)

        # Wrap with fallback if configured
        if self.fallback_chain:
            fallback = FallbackProvider(
                primary=primary,
                fallback_chain=self.fallback_chain,
                primary_name=decision.provider,
            )
        else:
            fallback = primary

        # Override model if the rule specified one
        call_kwargs = dict(kwargs)
        if decision.model:
            call_kwargs["model"] = decision.model

        return await fallback.generate(messages, tools=tools, **call_kwargs)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_text(messages: List[Dict[str, Any]]) -> str:
        """Return the most recent user message text."""
        for msg in reversed(messages or []):
            if msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(str(item.get("text", "")))
                    return " ".join(parts)
        return ""

    @staticmethod
    def _default_model(provider: str) -> str:
        return str(ConfigManager.get(f"ai.{provider}.primary_model", ""))

    @staticmethod
    def _build_provider(name: str) -> AIProvider:
        """Instantiate a specific provider by name."""
        cls = ProviderRegistry._providers.get(name.lower())
        if cls is None:
            logger.warning("router_unknown_provider", provider=name)
            return ProviderRegistry.get_active_provider()
        section = ConfigManager.get(f"ai.{name}", {}) or {}
        try:
            return cls(section)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "router_provider_init_failed",
                provider=name,
                error=str(exc),
            )
            return ProviderRegistry.get_active_provider()