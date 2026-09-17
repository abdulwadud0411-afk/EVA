"""Tests for Phase 16 agent verifier."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agent.planner import Plan, PlanStep
from app.agent.verifier import AgentVerifier, VerifyResult
from app.core.config_manager import ConfigManager
from app.core.events import EventBus


@pytest.fixture(autouse=True)
def reset_config():
    ConfigManager.load()
    ConfigManager.set("agent.verification.enabled", True, persist=False)
    ConfigManager.set("agent.verification.use_vision", False, persist=False)
    yield


@pytest.mark.asyncio
async def test_verify_disabled():
    ConfigManager.set("agent.verification.enabled", False, persist=False)
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="a", expected_result="file_exists:C:/x"),
        {"success": True},
    )
    assert r.verified is True
    assert "disabled" in r.reason.lower()


@pytest.mark.asyncio
async def test_verify_fails_when_tool_failed():
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="a"),
        {"success": False},
    )
    assert r.verified is False


@pytest.mark.asyncio
async def test_verify_no_expected_result():
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="a"),
        {"success": True},
    )
    assert r.verified is True
    assert "no explicit expectation" in r.reason


@pytest.mark.asyncio
async def test_verify_file_exists_spec_pass(monkeypatch):
    from app.tools import verifier as vmod
    monkeypatch.setattr(
        vmod, "file_exists",
        lambda p, **kw: {"verified": True, "path": p},
    )
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="write file",
                 expected_result="file_exists:C:/tmp/x.txt"),
        {"success": True},
    )
    assert r.verified is True
    assert r.checks[0]["type"] == "file_exists"


@pytest.mark.asyncio
async def test_verify_file_exists_spec_fail(monkeypatch):
    from app.tools import verifier as vmod
    monkeypatch.setattr(
        vmod, "file_exists",
        lambda p, **kw: {"verified": False, "reason": "not found"},
    )
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="write file",
                 expected_result="file_exists:C:/tmp/missing.txt"),
        {"success": True},
    )
    assert r.verified is False


@pytest.mark.asyncio
async def test_verify_process_running_spec(monkeypatch):
    from app.tools import verifier as vmod
    monkeypatch.setattr(
        vmod, "process_running",
        lambda name, **kw: {"verified": True, "process": name},
    )
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="open notepad",
                 expected_result="process_running:notepad.exe"),
        {"success": True},
    )
    assert r.verified is True


@pytest.mark.asyncio
async def test_verify_active_window_spec(monkeypatch):
    from app.tools import verifier as vmod
    monkeypatch.setattr(
        vmod, "active_window_title_contains",
        lambda s: {"verified": True, "title": "Notepad", "looking_for": s},
    )
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="focus",
                 expected_result="active_window_contains:Notepad"),
        {"success": True},
    )
    assert r.verified is True


@pytest.mark.asyncio
async def test_verify_unknown_spec_trusts_tool():
    v = AgentVerifier()
    r = await v.verify_step(
        PlanStep(index=1, action="a", expected_result="user is happy"),
        {"success": True},
    )
    assert r.verified is True


@pytest.mark.asyncio
async def test_verify_plan_aggregates(monkeypatch):
    from app.tools import verifier as vmod
    monkeypatch.setattr(
        vmod, "file_exists",
        lambda p, **kw: {"verified": True},
    )

    class _StepR:
        def __init__(self, idx, ok):
            self.step = PlanStep(
                index=idx, action=f"a{idx}",
                expected_result="file_exists:C:/x" if ok else "",
            )
            self.success = ok
            self.result = {}
            self.error = None
            self.skipped = False

    class _Exec:
        results = [_StepR(1, True), _StepR(2, True)]

    plan = Plan(goal="g", steps=[_StepR(1, True).step, _StepR(2, True).step])
    v = AgentVerifier(event_bus=EventBus())
    r = await v.verify_plan(plan, _Exec())
    assert r.verified is True
    assert len(r.checks) == 2