"""Tests for Phase 16 planner."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.planner import (
    Plan,
    PlanStep,
    Planner,
    PlannerError,
    refresh_allowed_tools,
)
from app.brain.provider_registry import ProviderRegistry
from app.core.config_manager import ConfigManager
from app.core.events import EventBus


@pytest.fixture(autouse=True)
def reset_tools_cache():
    refresh_allowed_tools()
    yield
    refresh_allowed_tools()


def _mock_provider(text: str):
    p = MagicMock()
    p.generate = AsyncMock(return_value=MagicMock(text=text))
    return p


def test_planstep_roundtrip():
    s = PlanStep(index=1, action="open notepad", tool_name="open_application",
                 arguments={"application": "notepad"})
    d = s.to_dict()
    s2 = PlanStep.from_dict(d)
    assert s2.index == 1
    assert s2.tool_name == "open_application"
    assert s2.arguments == {"application": "notepad"}


def test_plan_is_trivial():
    assert Plan(goal="x", steps=[]).is_trivial is True
    assert Plan(goal="x", steps=[PlanStep(index=1, action="a")]).is_trivial is True
    assert Plan(
        goal="x",
        steps=[
            PlanStep(index=1, action="a"),
            PlanStep(index=2, action="b"),
        ],
    ).is_trivial is False


@pytest.mark.asyncio
async def test_create_plan_parses_well_formed_json(monkeypatch):
    payload = (
        '{"reasoning": "simple", '
        '"steps": ['
        '{"index": 1, "action": "open notepad", '
        '"tool_name": "open_application", '
        '"arguments": {"application": "notepad"}, '
        '"expected_result": "process_running:notepad.exe"},'
        '{"index": 2, "action": "type text", '
        '"tool_name": "type_text", '
        '"arguments": {"text": "hello"}, '
        '"expected_result": ""}'
        ']}'
    )
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    plan = await Planner(event_bus=EventBus()).create_plan("open notepad and type hello")
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "open_application"
    assert plan.steps[1].arguments == {"text": "hello"}


@pytest.mark.asyncio
async def test_create_plan_rejects_empty_goal():
    with pytest.raises(PlannerError, match="Empty goal"):
        await Planner().create_plan("")


@pytest.mark.asyncio
async def test_create_plan_handles_code_fence(monkeypatch):
    payload = '```json\n{"reasoning": "x", "steps": [{"index": 1, "action": "do it", "tool_name": "", "arguments": {}, "expected_result": ""}]}\n```'
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    plan = await Planner().create_plan("test")
    assert len(plan.steps) == 1


@pytest.mark.asyncio
async def test_create_plan_rejects_unknown_tool(monkeypatch):
    payload = (
        '{"reasoning": "x", "steps": ['
        '{"index": 1, "action": "hack", "tool_name": "format_disk", "arguments": {}},'
        '{"index": 2, "action": "open", "tool_name": "open_application", "arguments": {"application": "chrome"}}'
        ']}'
    )
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    plan = await Planner().create_plan("test")
    # Unknown tool should be stripped to empty string, not removed
    assert plan.steps[0].tool_name == ""
    assert plan.steps[1].tool_name == "open_application"


@pytest.mark.asyncio
async def test_create_plan_respects_max_steps(monkeypatch):
    ConfigManager.load()
    ConfigManager.set("agent.planner.max_steps", 3, persist=False)

    steps = ",".join(
        f'{{"index": {i}, "action": "a{i}", "tool_name": "", "arguments": {{}}}}'
        for i in range(1, 11)
    )
    payload = '{"reasoning": "x", "steps": [' + steps + ']}'
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider(payload)),
    )
    plan = await Planner().create_plan("test")
    assert len(plan.steps) == 3


@pytest.mark.asyncio
async def test_create_plan_raises_on_garbage(monkeypatch):
    monkeypatch.setattr(
        ProviderRegistry, "get_active_provider",
        classmethod(lambda cls: _mock_provider("no json here")),
    )
    with pytest.raises(PlannerError, match="no parseable JSON"):
        await Planner().create_plan("test")