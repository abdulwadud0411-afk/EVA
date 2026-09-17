"""Tests for Phase 16 executor."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.executor import Executor, ExecutionResult
from app.agent.planner import Plan, PlanStep
from app.core.config_manager import ConfigManager
from app.core.events import EventBus
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    ToolRegistry.clear()
    ConfigManager.load()
    ConfigManager.set("agent.executor.step_timeout_seconds", 5, persist=False)
    ConfigManager.set("agent.executor.stop_on_first_failure", False, persist=False)
    yield
    ToolRegistry.clear()


def _plan(*specs):
    steps = [
        PlanStep(
            index=i,
            action=spec.get("action", f"step {i}"),
            tool_name=spec.get("tool", ""),
            arguments=spec.get("args", {}),
            critical=spec.get("critical", True),
        )
        for i, spec in enumerate(specs, start=1)
    ]
    return Plan(goal="test goal", steps=steps)


@pytest.mark.asyncio
async def test_executor_runs_simple_plan(monkeypatch):
    async def _fake_execute(name, args):
        return ToolResult(success=True, tool=name, data={"ok": True})

    monkeypatch.setattr(
        ToolRegistry, "execute",
        classmethod(lambda cls, n, a: _fake_execute(n, a)),
    )

    plan = _plan({"action": "a", "tool": "open_application", "args": {"application": "notepad"}},
                 {"action": "b", "tool": "type_text", "args": {"text": "hi"}})
    result = await Executor(event_bus=EventBus()).execute(plan)
    assert result.success is True
    assert result.steps_completed == 2


@pytest.mark.asyncio
async def test_executor_stops_on_critical_failure(monkeypatch):
    async def _fake_execute(name, args):
        return ToolResult(
            success=False,
            tool=name,
            error={"code": "APP_NOT_FOUND", "message": "no"},
        )

    monkeypatch.setattr(
        ToolRegistry, "execute",
        classmethod(lambda cls, n, a: _fake_execute(n, a)),
    )

    plan = _plan(
        {"action": "a", "tool": "open_application", "args": {"application": "x"}, "critical": True},
        {"action": "b", "tool": "type_text", "args": {"text": "y"}, "critical": True},
    )
    result = await Executor().execute(plan)
    assert result.success is False
    assert result.steps_completed == 0
    assert len(result.results) == 1  # stopped after first failure


@pytest.mark.asyncio
async def test_executor_no_tool_step_counts_as_success():
    plan = _plan({"action": "just think", "tool": ""})
    result = await Executor().execute(plan)
    assert result.success is True
    assert result.steps_completed == 1


@pytest.mark.asyncio
async def test_executor_calls_recovery(monkeypatch):
    call_count = {"n": 0}

    async def _fake_execute(name, args):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return ToolResult(
                success=False,
                tool=name,
                error={"code": "APP_NOT_FOUND", "message": "no"},
            )
        return ToolResult(success=True, tool=name, data={})

    monkeypatch.setattr(
        ToolRegistry, "execute",
        classmethod(lambda cls, n, a: _fake_execute(n, a)),
    )

    class _FakeRecovery:
        async def attempt(self, step, failure, attempt=1):
            from app.agent.recovery import RecoveryOutcome
            return RecoveryOutcome(
                recovered=True,
                alternative_step=PlanStep(
                    index=step.index,
                    action="retry",
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                ),
            )

    plan = _plan({"action": "a", "tool": "open_application", "args": {"application": "x"}})
    result = await Executor().execute(plan, recovery=_FakeRecovery())
    assert result.success is True


@pytest.mark.asyncio
async def test_executor_handles_timeout(monkeypatch):
    import asyncio

    async def _slow(name, args):
        await asyncio.sleep(10)
        return ToolResult(success=True, tool=name)

    monkeypatch.setattr(
        ToolRegistry, "execute",
        classmethod(lambda cls, n, a: _slow(n, a)),
    )
    ConfigManager.set("agent.executor.step_timeout_seconds", 1, persist=False)

    plan = _plan({"action": "a", "tool": "open_application", "args": {}})
    result = await Executor().execute(plan)
    assert result.success is False
    assert result.results[0].error["code"] == "TIMEOUT"


@pytest.mark.asyncio
async def test_executor_cancel_flag(monkeypatch):
    async def _fake_execute(name, args):
        return ToolResult(success=True, tool=name)

    monkeypatch.setattr(
        ToolRegistry, "execute",
        classmethod(lambda cls, n, a: _fake_execute(n, a)),
    )
    plan = _plan({"action": "a", "tool": "open_application", "args": {}},
                 {"action": "b", "tool": "type_text", "args": {}})
    result = await Executor().execute(plan, cancel_flag=lambda: True)
    assert result.success is False
    assert "cancelled" in result.final_message.lower()


@pytest.mark.asyncio
async def test_execution_result_to_dict():
    plan = _plan({"action": "a", "tool": "open_application"})
    result = await Executor().execute(plan)
    d = result.to_dict()
    assert d["goal"] == "test goal"
    assert "results" in d