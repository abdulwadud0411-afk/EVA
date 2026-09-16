"""
Tests for Phase 15 demonstration learning.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config_manager import ConfigManager
from app.knowledge.learning.action_logger import ActionEvent, ActionLogger
from app.knowledge.learning.demonstration_learner import (
    DemonstrationLearner,
    DemonstrationError,
)
from app.skills.registry import SkillRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    SkillRegistry.clear_cache()
    ConfigManager.load()
    ConfigManager.set("learning.demonstration.enabled", True, persist=False)
    yield
    SkillRegistry.clear_cache()


# ---------------------------------------------------------------------- #
# ActionLogger
# ---------------------------------------------------------------------- #
def test_action_logger_append():
    logger = ActionLogger()
    logger._running = True
    logger._append("click", {"x": 10, "y": 20, "button": "left"})
    logger._append("hotkey", {"name": "ctrl+c"})
    assert logger.count() == 2
    dicts = logger.as_dicts()
    assert dicts[0]["kind"] == "click"
    assert dicts[0]["data"]["x"] == 10


def test_action_logger_max_events():
    logger = ActionLogger()
    logger._running = True
    logger._max_events = 3
    for i in range(10):
        logger._append("key", {"char": str(i)})
    assert logger.count() == 3


# ---------------------------------------------------------------------- #
# DemonstrationLearner
# ---------------------------------------------------------------------- #
def test_parse_json_variants():
    d = DemonstrationLearner()
    assert d._parse_json('{"a":1}') == {"a": 1}
    assert d._parse_json('```json\n{"a":1}\n```') == {"a": 1}
    assert d._parse_json('prefix {"a":1} suffix') == {"a": 1}
    assert d._parse_json('nope') is None


def test_events_to_text():
    d = DemonstrationLearner()
    events = [
        ActionEvent(timestamp="t", kind="click", data={"x": 5, "y": 6, "button": "left"}),
        ActionEvent(timestamp="t", kind="key", data={"char": "a"}),
        ActionEvent(timestamp="t", kind="hotkey", data={"name": "ctrl+s"}),
        ActionEvent(timestamp="t", kind="window", data={"title": "Notepad"}),
    ]
    text = d._events_to_text(events)
    assert "CLICK left at (5, 6)" in text
    assert "TYPE 'a'" in text
    assert "HOTKEY ctrl+s" in text
    assert "WINDOW 'Notepad'" in text


@pytest.mark.asyncio
async def test_learn_from_actions_missing_events():
    d = DemonstrationLearner()
    with pytest.raises(DemonstrationError, match="No action events"):
        await d.learn_from_actions([])


@pytest.mark.asyncio
async def test_learn_from_actions_success(monkeypatch):
    from app.brain.provider_registry import ProviderRegistry

    fake_response = MagicMock()
    fake_response.text = (
        '{"name": "demo_skill", "description": "test", '
        '"steps": ['
        '{"index": 1, "action": "open notepad", "tool_name": "open_application", "arguments": {"application": "notepad"}},'
        '{"index": 2, "action": "type hi", "tool_name": "type_text", "arguments": {"text": "hi"}}'
        '], "required_tools": ["open_application", "type_text"]}'
    )
    fake_provider = MagicMock()
    fake_provider.generate = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: fake_provider))

    events = [
        ActionEvent(timestamp="t", kind="click", data={"x": 1, "y": 1, "button": "left"}),
        ActionEvent(timestamp="t", kind="key", data={"char": "h"}),
        ActionEvent(timestamp="t", kind="key", data={"char": "i"}),
    ]

    skill = await DemonstrationLearner().learn_from_actions(events)
    assert skill.name == "demo_skill"
    assert len(skill.steps) == 2
    assert "demo_skill" in SkillRegistry.list_skills()


@pytest.mark.asyncio
async def test_learn_from_actions_rejects_bad_tool(monkeypatch):
    from app.brain.provider_registry import ProviderRegistry

    fake_response = MagicMock()
    fake_response.text = (
        '{"name": "x", "steps": ['
        '{"index": 1, "action": "hack", "tool_name": "format_disk", "arguments": {}},'
        '{"index": 2, "action": "ok", "tool_name": "open_application", "arguments": {"application": "x"}}'
        ']}'
    )
    fake_provider = MagicMock()
    fake_provider.generate = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(ProviderRegistry, "get_active_provider",
                        classmethod(lambda cls: fake_provider))

    events = [ActionEvent(timestamp="t", kind="click", data={"x": 1, "y": 1})]
    with pytest.raises(DemonstrationError, match="Not enough valid steps"):
        await DemonstrationLearner().learn_from_actions(events)