"""
Tests for Phase 15 skill system.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config_manager import ConfigManager
from app.core.events import EventBus
from app.skills.base import (
    Skill,
    SkillStep,
    SkillResult,
    SkillDefinitionError,
)
from app.skills.registry import SkillRegistry
from app.skills.executor import SkillExecutor
from app.skills.verifier import SkillVerifier


@pytest.fixture(autouse=True)
def clean_registry():
    SkillRegistry.clear_cache()
    yield
    SkillRegistry.clear_cache()


# ---------------------------------------------------------------------- #
# Base
# ---------------------------------------------------------------------- #
def test_skill_step_roundtrip():
    s = SkillStep(index=1, action="open", tool_name="open_application",
                  arguments={"application": "chrome"})
    d = s.to_dict()
    s2 = SkillStep.from_dict(d)
    assert s2.index == 1
    assert s2.tool_name == "open_application"
    assert s2.arguments == {"application": "chrome"}


def test_skill_from_dict():
    skill = Skill.from_dict({
        "name": "x",
        "description": "y",
        "steps": [{"index": 1, "action": "a", "tool_name": "open_application"}],
    })
    assert skill.name == "x"
    assert len(skill.steps) == 1


def test_skill_validate_empty_name():
    with pytest.raises(SkillDefinitionError):
        Skill(name="", steps=[SkillStep(index=1, action="a", tool_name="x")]).validate()


def test_skill_validate_empty_steps():
    with pytest.raises(SkillDefinitionError):
        Skill(name="x", steps=[]).validate()


# ---------------------------------------------------------------------- #
# Registry
# ---------------------------------------------------------------------- #
def test_registry_save_and_get():
    skill = Skill(
        name="test_skill",
        description="d",
        steps=[SkillStep(index=1, action="a", tool_name="open_application",
                         arguments={"application": "notepad"})],
    )
    SkillRegistry.save_skill(skill)
    assert "test_skill" in SkillRegistry.list_skills()

    fetched = SkillRegistry.get_skill("test_skill")
    assert fetched is not None
    assert fetched.name == "test_skill"
    assert len(fetched.steps) == 1


def test_registry_delete():
    SkillRegistry.save_skill(Skill(
        name="to_delete",
        steps=[SkillStep(index=1, action="a", tool_name="open_application")],
    ))
    assert SkillRegistry.delete_skill("to_delete") is True
    assert "to_delete" not in SkillRegistry.list_skills()


# ---------------------------------------------------------------------- #
# Executor
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_executor_missing_skill():
    executor = SkillExecutor()
    with pytest.raises(Exception, match="not found"):
        await executor.execute("does_not_exist_xyz")


@pytest.mark.asyncio
async def test_executor_success(monkeypatch):
    # Stub a tool result
    class _R:
        success = True
        tool = "open_application"
        data = {"application": "notepad"}
        error = None
        def to_dict(self):
            return {"success": True, "tool": self.tool, "data": self.data, "error": None}

    async def _fake_execute(name, args):
        return _R()

    from app.tools.registry import ToolRegistry
    monkeypatch.setattr(ToolRegistry, "list_tools", classmethod(lambda cls: ["open_application"]))
    monkeypatch.setattr(ToolRegistry, "execute", classmethod(lambda cls, n, a: _fake_execute(n, a)))

    skill = Skill(
        name="open_note",
        steps=[
            SkillStep(index=1, action="open notepad", tool_name="open_application",
                      arguments={"application": "notepad"}),
        ],
    )
    SkillRegistry.save_skill(skill)

    executor = SkillExecutor(event_bus=EventBus())
    result = await executor.execute("open_note")
    assert result.success is True
    assert result.steps_completed == 1
    assert result.steps_total == 1


@pytest.mark.asyncio
async def test_executor_step_failure(monkeypatch):
    class _R:
        success = False
        tool = "open_application"
        data = None
        error = {"code": "APP_NOT_FOUND", "message": "no"}
        def to_dict(self):
            return {"success": False, "tool": self.tool, "data": None, "error": self.error}

    async def _fake_execute(name, args):
        return _R()

    from app.tools.registry import ToolRegistry
    monkeypatch.setattr(ToolRegistry, "list_tools", classmethod(lambda cls: ["open_application"]))
    monkeypatch.setattr(ToolRegistry, "execute", classmethod(lambda cls, n, a: _fake_execute(n, a)))

    skill = Skill(
        name="fail_skill",
        steps=[SkillStep(index=1, action="x", tool_name="open_application")],
    )
    SkillRegistry.save_skill(skill)

    executor = SkillExecutor()
    result = await executor.execute("fail_skill")
    assert result.success is False
    assert result.error["code"] == "APP_NOT_FOUND"


@pytest.mark.asyncio
async def test_executor_missing_tools():
    skill = Skill(
        name="needs_missing",
        required_tools=["nonexistent_tool_xyz"],
        steps=[SkillStep(index=1, action="x", tool_name="open_application")],
    )
    SkillRegistry.save_skill(skill)

    executor = SkillExecutor()
    result = await executor.execute("needs_missing")
    assert result.success is False
    assert result.error["code"] == "MISSING_TOOLS"


# ---------------------------------------------------------------------- #
# Verifier
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_verifier_none_passes():
    skill = Skill(name="x", steps=[SkillStep(index=1, action="a", tool_name="x")], verification="none")
    assert await SkillVerifier().verify(skill) is True


@pytest.mark.asyncio
async def test_verifier_empty_passes():
    skill = Skill(name="x", steps=[SkillStep(index=1, action="a", tool_name="x")])
    assert await SkillVerifier().verify(skill) is True


@pytest.mark.asyncio
async def test_verifier_file_exists(monkeypatch, tmp_path):
    from app.tools import verifier as vmod
    skill = Skill(
        name="x",
        steps=[SkillStep(index=1, action="a", tool_name="x")],
        verification=f"file_exists:{tmp_path}",
    )
    monkeypatch.setattr(vmod, "file_exists", lambda p, **kw: {"verified": True})
    assert await SkillVerifier().verify(skill) is True