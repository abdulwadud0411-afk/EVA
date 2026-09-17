"""Tests for Phase 18 AI router."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.brain.ai_router import AIRouter, RoutingDecision
from app.brain.response_models import AIResponse
from app.brain.routing_rules import RoutingContext, RoutingRule
from app.core.config_manager import ConfigManager


def _make_router(rules=None, chain=None, enabled=True, mode="auto"):
    if rules is None:
        rules = [
            RoutingRule(
                name="simple",
                provider="ollama",
                model="qwen2.5:3b",
                priority=20,
                match_keywords=["hi", "hello"],
                max_length=40,
                requires_no_tools=True,
            ),
            RoutingRule(
                name="coding",
                provider="deepseek",
                model="deepseek-v4-pro",
                priority=30,
                match_keywords=["python", "code"],
            ),
            RoutingRule(
                name="default",
                provider="deepseek",
                model="deepseek-v4-flash",
                priority=1000,
            ),
        ]
    return AIRouter(
        rules=rules,
        fallback_chain=chain or [],
        enabled=enabled,
        mode=mode,
    )


def test_resolve_simple_greeting():
    router = _make_router()
    decision = router.resolve(RoutingContext(text="hi", has_tools=False))
    assert decision.provider == "ollama"
    assert decision.model == "qwen2.5:3b"
    assert decision.rule_name == "simple"


def test_resolve_coding():
    router = _make_router()
    decision = router.resolve(
        RoutingContext(text="write a python function", has_tools=True)
    )
    assert decision.provider == "deepseek"
    assert decision.model == "deepseek-v4-pro"
    assert decision.rule_name == "coding"


def test_resolve_default_for_unmatched():
    router = _make_router()
    decision = router.resolve(
        RoutingContext(text="what is the meaning of life", has_tools=False)
    )
    assert decision.provider == "deepseek"
    assert decision.model == "deepseek-v4-flash"
    assert decision.rule_name == "default"


def test_resolve_disabled_falls_back_to_primary():
    ConfigManager.load()
    ConfigManager.set("ai.provider", "deepseek", persist=False)
    router = _make_router(enabled=False)
    decision = router.resolve(RoutingContext(text="hi"))
    assert decision.provider == "deepseek"
    assert decision.rule_name == "disabled_or_manual"


def test_resolve_manual_mode_falls_back_to_primary():
    ConfigManager.load()
    ConfigManager.set("ai.provider", "deepseek", persist=False)
    router = _make_router(mode="manual")
    decision = router.resolve(RoutingContext(text="hi"))
    assert decision.rule_name == "disabled_or_manual"


def test_resolve_explicit_override():
    router = _make_router()
    decision = router.resolve(RoutingContext(
        text="anything", explicit_provider="openai", explicit_model="gpt-4o",
    ))
    assert decision.provider == "openai"
    assert decision.model == "gpt-4o"
    assert decision.rule_name == "explicit_override"


def test_resolve_respects_priority():
    rules = [
        RoutingRule(name="low", provider="ollama", priority=100,
                    match_keywords=["python"]),
        RoutingRule(name="high", provider="deepseek", priority=10,
                    match_keywords=["python"]),
    ]
    router = AIRouter(rules=rules, fallback_chain=[])
    decision = router.resolve(RoutingContext(text="python code"))
    assert decision.rule_name == "high"


def test_router_from_config_default():
    ConfigManager.load()
    router = AIRouter.from_config()
    assert isinstance(router, AIRouter)
    assert router.enabled is True


@pytest.mark.asyncio
async def test_generate_uses_router(monkeypatch):
    router = _make_router()
    fake_response = AIResponse(text="hi there", provider_name="ollama")

    class _StubProvider:
        async def generate(self, *a, **kw):
            return fake_response
        @property
        def capabilities(self):
            return {}
        async def validate_api_key(self):
            return True

    monkeypatch.setattr(router, "_build_provider",
                        lambda name: _StubProvider())

    result = await router.generate(
        messages=[{"role": "user", "content": "hi"}],
        ctx=RoutingContext(text="hi"),
    )
    assert result.text == "hi there"


def test_decision_to_dict():
    d = RoutingDecision(
        provider="deepseek",
        model="deepseek-v4-flash",
        rule_name="default",
        reasoning="fallback",
        fallback_chain=["ollama"],
    )
    as_dict = d.to_dict()
    assert as_dict["provider"] == "deepseek"
    assert as_dict["fallback_chain"] == ["ollama"]