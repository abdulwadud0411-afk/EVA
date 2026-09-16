"""
Tests for AgentLoop (Phase 1 + Phase 2 + Phase 7 + Fix Patch).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.agent.agent import AgentLoop
from app.brain.response_models import AIResponse, ToolCall
from app.core.config_manager import ConfigManager
from app.core.events import EventBus
from app.tools.base import Tool, ToolResult, RiskLevel
from app.tools.registry import ToolRegistry


_COMPLEX_PROMPT = "design a python calculator and save the result to a markdown file"
_COMPLEX_HELLO = "tell me about the history of computing in three sentences"
_COMPLEX_BOOM = "explain quantum entanglement in simple terms"


class _StubProvider:
    def __init__(self, responses: Optional[List[AIResponse]] = None,
                 reply: str = "ok",
                 tool_calls: Optional[List[ToolCall]] = None):
        if responses is not None:
            self._queue = list(responses)
        else:
            self._queue = [
                AIResponse(
                    text=reply,
                    tool_calls=tool_calls or [],
                    provider_name="stub",
                    model_used="stub-model",
                )
            ]
        self.model = "stub-model"
        self.calls: List[Dict[str, Any]] = []

    async def generate(self, messages, tools=None, tool_choice=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools})
        if not self._queue:
            return AIResponse(text="(no more responses)", provider_name="stub")
        return self._queue.pop(0)

    @property
    def capabilities(self):
        return {"supports_tool_calling": True}

    async def validate_api_key(self):
        return True


@pytest.fixture(autouse=True)
def clean_registry():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


class _RecordingTool(Tool):
    name = "record"
    description = "Record a value."
    parameters = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    calls: List[Dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> ToolResult:
        _RecordingTool.calls.append(kwargs)
        return ToolResult(success=True, tool=self.name, data={"value": kwargs.get("value")})


@pytest.mark.asyncio
async def test_agent_returns_text(monkeypatch):
    stub = _StubProvider(reply="Hello from EVA")
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    agent = AgentLoop(event_bus=EventBus())
    result = await agent.run(_COMPLEX_HELLO)
    assert result == "Hello from EVA"


@pytest.mark.asyncio
async def test_agent_maintains_history(monkeypatch):
    stub = _StubProvider(reply="ok")
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    ConfigManager.load()
    ConfigManager.set("ai.history_limit", 2, persist=False)
    agent = AgentLoop()
    await agent.run("design a complex algorithm for sorting numbers")
    await agent.run("explain the theory of relativity simply")
    await agent.run("describe the water cycle in detail")
    assert len(agent.history) <= 2


@pytest.mark.asyncio
async def test_agent_propagates_provider_error(monkeypatch):
    class _Boom(_StubProvider):
        async def generate(self, *a, **kw):
            raise RuntimeError("boom")
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: _Boom()))
    agent = AgentLoop()
    with pytest.raises(RuntimeError, match="boom"):
        await agent.run(_COMPLEX_BOOM)


@pytest.mark.asyncio
async def test_agent_passes_tool_schemas(monkeypatch):
    ToolRegistry.register_class(_RecordingTool)
    stub = _StubProvider(reply="hi")
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    agent = AgentLoop()
    await agent.run(_COMPLEX_HELLO)
    assert len(stub.calls) == 1
    tools = stub.calls[0]["tools"]
    assert tools is not None
    names = [t["function"]["name"] for t in tools]
    assert "record" in names


@pytest.mark.asyncio
async def test_agent_executes_tool_call_then_returns_final_text(monkeypatch):
    _RecordingTool.calls = []
    ToolRegistry.register_class(_RecordingTool)
    tool_call = ToolCall(id="call_1", name="record", arguments={"value": "hello"})
    first = AIResponse(text=None, tool_calls=[tool_call],
                       provider_name="stub", finish_reason="tool_calls")
    second = AIResponse(text="Done!", provider_name="stub")
    stub = _StubProvider(responses=[first, second])
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    agent = AgentLoop()
    result = await agent.run("record the value hello in the system")
    assert _RecordingTool.calls == [{"value": "hello"}]
    assert result == "Done!"
    assert len(stub.calls) == 2


@pytest.mark.asyncio
async def test_agent_skips_duplicate_tool_calls(monkeypatch):
    _RecordingTool.calls = []
    ToolRegistry.register_class(_RecordingTool)
    tc = ToolCall(id="call_1", name="record", arguments={"value": "same"})
    tc2 = ToolCall(id="call_2", name="record", arguments={"value": "same"})
    first = AIResponse(text=None, tool_calls=[tc], provider_name="stub")
    second = AIResponse(text=None, tool_calls=[tc2], provider_name="stub")
    final = AIResponse(text="Finished.", provider_name="stub")
    stub = _StubProvider(responses=[first, second, final])
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    ConfigManager.load()
    ConfigManager.set("agent.detect_duplicate_tool_calls", True, persist=False)
    agent = AgentLoop()
    result = await agent.run("record same value twice please")
    assert len(_RecordingTool.calls) == 1
    assert result == "Finished."


@pytest.mark.asyncio
async def test_agent_respects_max_tool_steps(monkeypatch):
    ToolRegistry.register_class(_RecordingTool)
    def make_tool_call(i: int) -> AIResponse:
        return AIResponse(
            text=None,
            tool_calls=[ToolCall(id=f"c{i}", name="record", arguments={"value": str(i)})],
            provider_name="stub",
        )
    responses = [make_tool_call(i) for i in range(10)]
    stub = _StubProvider(responses=responses)
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    ConfigManager.load()
    ConfigManager.set("agent.max_steps", 3, persist=False)
    agent = AgentLoop()
    result = await agent.run("record a long sequence of distinct values")
    assert "maximum" in result.lower() or "tool steps" in result.lower()
    assert len(stub.calls) <= 3


@pytest.mark.asyncio
async def test_agent_publishes_tool_events(monkeypatch):
    ToolRegistry.register_class(_RecordingTool)
    tool_call = ToolCall(id="c1", name="record", arguments={"value": "x"})
    first = AIResponse(text=None, tool_calls=[tool_call], provider_name="stub")
    second = AIResponse(text="all done", provider_name="stub")
    stub = _StubProvider(responses=[first, second])
    from app.brain.provider_registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: stub))
    seen: List[str] = []
    bus = EventBus()
    bus.subscribe(lambda e: seen.append(e.type))
    agent = AgentLoop(event_bus=bus)
    await agent.run("record a value for testing")
    assert "TOOL_STARTED" in seen
    assert "TOOL_FINISHED" in seen