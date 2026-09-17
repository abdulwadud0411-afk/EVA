"""Tests for Phase 16 recovery."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.planner import PlanStep
from app.agent.recovery import Recovery, RecoveryOutcome
from app.brain.provider_registry import ProviderRegistry
from app.core.config_manager import ConfigManager
from app.core.events import EventBus


@pytest.fixture(autouse=True)
def reset_config():
    ConfigManager.load()
    ConfigManager.set("agent.recovery.enabled", True, persist=False)
    ConfigManager.set("agent.recovery.max_retries", 2, persist=False)
    ConfigManager.set("agent.recovery.ask_ai_for_alternative", True, persist=False)
    yield


def _mock_provider(text: str):
    p = MagicMock()
    p.generate = AsyncMock(return_value=MagicMock(text=text))
    return p


@pytest.mark.asyncio
async def test_recovery_disabled():
    ConfigManager.set("agent.recovery.enabled", False, persist=False)
    r = Recovery()
    out = await r.attempt(
        PlanStep(index=1, action="a", tool_name="open_application"),
        {"code": "TOOL_FAILED", "message": "nope"},
    )
    assert out.recovered is False
    assert "disabled" in out.reason.lower()


@pytest.mark.asyncio
async def test_recovery_max_retries_exceeded():
    r = Recovery()
    out = await r.attempt(
        PlanStep(index=1, action="a", tool_name="open_application"),
        {"code": "TOOL_FAILED", "message": "nope"},
        attempt=5,
    )
    assert out.recovered is False
    assert "max retries" in out.reason.lower()


@pytest.mark.asyncio
async def test_recovery_simple_fallback_timeout(monkeypatch):
    ConfigManager.set("agent.recovery.ask_ai_for_alternative", False, persist=False)
    r = Recovery()
    step = PlanStep(index=1, action="a", tool_name="open_application")
    out = await r.attempt(step, {"code": "TIMEOUT", "message": "slow"})
    assert out.recovered is True
    assert out.alternative_step is step


@pytest.mark.asyncio
async def test_recovery_ai_alternative(monkeypatch):
    payload = (
        '{"reasoning": "try different app", '
        '"alternative_step": {'
        '"index": 1, '
        '"action": "open firefox", '
        '"tool_name": "open_application", '
        '"arguments": {"application": "firefox"}, '
        '"expected_result": "process_running:firefox.exe"}}'
    )
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    r = Recovery(event_bus=EventBus())
    out = await r.attempt(
        PlanStep(index=1, action="open chrome", tool_name="open_application",
                 arguments={"application": "chrome"}),
        {"code": "APP_NOT_FOUND", "message": "no chrome"},
    )
    assert out.recovered is True
    assert out.alternative_step is not None
    assert out.alternative_step.arguments == {"application": "firefox"}


@pytest.mark.asyncio
async def test_recovery_ai_null_alternative(monkeypatch):
    payload = '{"reasoning": "no alternative", "alternative_step": null}'
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    r = Recovery()
    out = await r.attempt(
        PlanStep(index=1, action="a", tool_name="open_application"),
        {"code": "APP_NOT_FOUND", "message": "no"},
    )
    assert out.recovered is False


@pytest.mark.asyncio
async def test_recovery_ai_unknown_tool_rejected(monkeypatch):
    payload = (
        '{"reasoning": "x", "alternative_step": {'
        '"index": 1, "action": "hack", "tool_name": "format_disk", '
        '"arguments": {}, "expected_result": ""}}'
    )
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    r = Recovery()
    out = await r.attempt(
        PlanStep(index=1, action="a", tool_name="open_application"),
        {"code": "APP_NOT_FOUND", "message": "no"},
    )
    assert out.recovered is False
    assert "unknown tool" in out.reason.lower()


@pytest.mark.asyncio
async def test_recovery_ai_failure_graceful(monkeypatch):
    class _Boom:
        async def generate(self, **kw):
            raise RuntimeError("api down")

    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _Boom()),
    )
    r = Recovery()
    out = await r.attempt(
        PlanStep(index=1, action="a", tool_name="open_application"),
        {"code": "APP_NOT_FOUND", "message": "no"},
    )
    assert out.recovered is False
    assert "AI failed" in out.reason