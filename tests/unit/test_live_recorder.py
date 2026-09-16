"""
Tests for Phase 15 live recorder + skill logger.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config_manager import ConfigManager
from app.core.events import EventBus
from app.knowledge.learning.action_logger import ActionEvent
from app.knowledge.learning.live_recorder import LiveRecorder, LiveRecorderError
from app.skills.base import Skill, SkillResult, SkillStep
from app.skills.registry import SkillRegistry
from app.skills.skill_logger import SkillLogger


@pytest.fixture(autouse=True)
def clean_registry():
    SkillRegistry.clear_cache()
    ConfigManager.load()
    ConfigManager.set("learning.demonstration.enabled", True, persist=False)
    yield
    SkillRegistry.clear_cache()


# ---------------------------------------------------------------------- #
# SkillLogger
# ---------------------------------------------------------------------- #
def test_skill_logger_log_result():
    result = SkillResult(
        success=True,
        skill_name="test_skill_a",
        steps_total=2,
        steps_completed=2,
        results=[],
        duration_ms=100,
    )
    row_id = SkillLogger.log_result(result)
    assert row_id is not None

    recent = SkillLogger.recent(limit=10)
    assert any(r["skill_name"] == "test_skill_a" for r in recent)


def test_skill_logger_failure():
    result = SkillResult(
        success=False,
        skill_name="test_skill_b",
        steps_total=3,
        steps_completed=1,
        error={"code": "X", "message": "y"},
        duration_ms=50,
    )
    SkillLogger.log_result(result)
    recent = SkillLogger.recent(limit=10)
    matching = [r for r in recent if r["skill_name"] == "test_skill_b"]
    assert matching
    assert matching[0]["success"] == 0


def test_skill_logger_stats():
    for _ in range(3):
        SkillLogger.log_result(SkillResult(
            success=True,
            skill_name="stats_skill",
            steps_total=1,
            steps_completed=1,
        ))
    stats = SkillLogger.stats_for("stats_skill")
    assert stats["total"] >= 3
    assert stats["successes"] >= 3


# ---------------------------------------------------------------------- #
# LiveRecorder
# ---------------------------------------------------------------------- #
def test_recorder_disabled(monkeypatch):
    ConfigManager.set("learning.demonstration.enabled", False, persist=False)
    rec = LiveRecorder()
    with pytest.raises(LiveRecorderError, match="disabled"):
        rec.start()


def test_recorder_start_stop_without_hooks(monkeypatch):
    """If input hooks are unavailable, start() should raise."""
    rec = LiveRecorder()
    with patch.object(rec.action_logger, "start", return_value=False):
        with pytest.raises(LiveRecorderError, match="action logger"):
            rec.start()


@pytest.mark.asyncio
async def test_recorder_stop_and_learn_no_events(monkeypatch):
    """No events -> returns success=False."""
    rec = LiveRecorder()
    # Pretend we started
    rec._running = True
    rec._started_at = 0.0
    rec.action_logger.events = []
    rec.screenshots.capture_now = MagicMock(return_value=None)
    rec.action_logger.stop = MagicMock(return_value=[])

    result = await rec.stop_and_learn()
    assert result["success"] is False
    assert "No actions" in result["error"]


@pytest.mark.asyncio
async def test_recorder_stop_and_learn_success(monkeypatch):
    """Full happy path with stubbed learner."""
    rec = LiveRecorder()
    rec._running = True
    rec._started_at = 0.0

    # Stub: one click event
    events = [ActionEvent(timestamp="t", kind="click", data={"x": 1, "y": 2})]
    rec.action_logger.stop = MagicMock(return_value=events)
    rec.screenshots.capture_now = MagicMock(return_value=None)
    rec.screenshots.as_paths = MagicMock(return_value=[])
    rec.screenshots.count = MagicMock(return_value=0)

    fake_skill = Skill(
        name="recorded_skill",
        description="desc",
        steps=[
            SkillStep(index=1, action="a", tool_name="open_application"),
            SkillStep(index=2, action="b", tool_name="type_text"),
        ],
    )
    rec.learner.learn_from_actions = AsyncMock(return_value=fake_skill)

    result = await rec.stop_and_learn(title="My Demo")
    assert result["success"] is True
    assert result["skill"]["name"] == "recorded_skill"
    assert rec.is_running is False


@pytest.mark.asyncio
async def test_recorder_cancel():
    rec = LiveRecorder()
    rec._running = True
    rec.action_logger.stop = MagicMock(return_value=[])
    rec.cancel()
    assert rec.is_running is False


# ---------------------------------------------------------------------- #
# Built-in skills
# ---------------------------------------------------------------------- #
def test_builtin_skills_register():
    from app.skills.builtins.system_skills import register_builtin_skills
    count = register_builtin_skills(force=True)
    assert count >= 3

    names = set(SkillRegistry.list_skills())
    assert "open_notepad_and_type" in names
    assert "open_url_and_screenshot" in names
    assert "open_app_and_focus" in names


def test_builtin_skills_idempotent():
    from app.skills.builtins.system_skills import register_builtin_skills
    first = register_builtin_skills(force=True)
    second = register_builtin_skills(force=False)
    assert first >= 3
    assert second == 0    # already registered