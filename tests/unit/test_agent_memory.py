"""
Tests for AgentLoop memory integration (Phase 12).
"""
from __future__ import annotations

import pytest

from app.agent.agent import AgentLoop
from app.brain.response_models import AIResponse
from app.core.events import EventBus
from app.memory.memory import MemoryStore


class _StubProvider:
    """Returns a canned text response."""
    def __init__(self, reply: str = "ok"):
        self.reply = reply
        self.model = "stub-model"
        self.calls = []

    async def generate(self, messages, tools=None, tool_choice=None, **kwargs):
        self.calls.append(messages)
        return AIResponse(
            text=self.reply,
            tool_calls=[],
            provider_name="stub",
            model_used="stub-model",
        )

    @property
    def capabilities(self):
        return {"supports_tool_calling": True}

    async def validate_api_key(self):
        return True


@pytest.mark.asyncio
async def test_remember_name_command(monkeypatch):
    stub = _StubProvider(reply="should not be used")
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    agent = AgentLoop(event_bus=EventBus())
    response = await agent.run("remember my name is Rizvi")
    assert "Rizvi" in response
    # Provider should NOT have been called (memory command handled locally)
    assert len(stub.calls) == 0

    # Verify stored
    assert MemoryStore.user.get_preferred_name() == "Rizvi"


@pytest.mark.asyncio
async def test_call_me_pattern(monkeypatch):
    stub = _StubProvider()
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    agent = AgentLoop()
    response = await agent.run("call me Rizvi")
    assert "Rizvi" in response
    assert MemoryStore.user.get_preferred_name() == "Rizvi"


@pytest.mark.asyncio
async def test_bangla_name_pattern(monkeypatch):
    stub = _StubProvider()
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    agent = AgentLoop()
    response = await agent.run("amar nam Rizvi")
    assert "Rizvi" in response
    assert MemoryStore.user.get_preferred_name() == "Rizvi"


@pytest.mark.asyncio
async def test_what_is_my_name_when_known(monkeypatch):
    stub = _StubProvider()
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    MemoryStore.user.set_preferred_name("Rizvi")

    agent = AgentLoop()
    response = await agent.run("what is my name?")
    assert "Rizvi" in response
    assert len(stub.calls) == 0


@pytest.mark.asyncio
async def test_what_is_my_name_when_unknown(monkeypatch):
    stub = _StubProvider()
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    agent = AgentLoop()
    response = await agent.run("what is my name?")
    assert "don't know" in response.lower() or "not" in response.lower()
    assert len(stub.calls) == 0


@pytest.mark.asyncio
async def test_forget_name(monkeypatch):
    stub = _StubProvider()
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    MemoryStore.user.set_preferred_name("Rizvi")

    agent = AgentLoop()
    response = await agent.run("forget my name")
    assert "forgot" in response.lower() or "forget" in response.lower()
    assert MemoryStore.user.get_preferred_name() is None


@pytest.mark.asyncio
async def test_preference_in_system_prompt(monkeypatch):
    stub = _StubProvider(reply="Hello Rizvi!")
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    MemoryStore.user.set_preferred_name("Rizvi")

    agent = AgentLoop()
    await agent.run("tell me something complex to force provider call")

    # The stub captured the messages; system prompt should mention Rizvi
    assert len(stub.calls) == 1
    sys_msg = stub.calls[0][0]["content"]
    assert "Rizvi" in sys_msg


@pytest.mark.asyncio
async def test_memory_persists_across_agents(monkeypatch):
    stub = _StubProvider()
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: stub),
    )

    agent1 = AgentLoop()
    await agent1.run("remember my name is Rizvi")

    # New agent, same DB
    agent2 = AgentLoop()
    response = await agent2.run("what is my name?")
    assert "Rizvi" in response