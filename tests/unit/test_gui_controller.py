"""Tests for Phase 21 GUIController (no Qt needed)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.brain.response_models import AIResponse
from app.core.events import Event, EventBus
from app.gui.controller import GUIController
from app.gui.gui_state import GUIStatus


class _StubAgent:
    def __init__(self, reply="ok", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    async def run(self, text, voice_turn=False):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_send_message_returns_reply(bus):
    stub = _StubAgent(reply="Hello from EVA")
    ctrl = GUIController(event_bus=bus, agent=stub)

    reply = await ctrl.send_message("hi")
    assert reply == "Hello from EVA"
    assert stub.calls == ["hi"]


@pytest.mark.asyncio
async def test_send_message_emits_callbacks(bus):
    stub = _StubAgent(reply="hi")
    ctrl = GUIController(event_bus=bus, agent=stub)

    users, assistants = [], []
    ctrl.on_user_message(lambda t: users.append(t))
    ctrl.on_assistant_message(lambda t: assistants.append(t))

    await ctrl.send_message("hello")
    assert users == ["hello"]
    assert assistants == ["hi"]


@pytest.mark.asyncio
async def test_send_empty_message_returns_empty(bus):
    stub = _StubAgent()
    ctrl = GUIController(event_bus=bus, agent=stub)
    reply = await ctrl.send_message("   ")
    assert reply == ""
    assert stub.calls == []


@pytest.mark.asyncio
async def test_send_message_error_emits_error_callback(bus):
    stub = _StubAgent(error=RuntimeError("boom"))
    ctrl = GUIController(event_bus=bus, agent=stub)

    errors = []
    ctrl.on_error(lambda m: errors.append(m))

    reply = await ctrl.send_message("hi")
    assert reply == ""
    assert errors and "boom" in errors[0]
    assert ctrl.state.status == GUIStatus.ERROR


@pytest.mark.asyncio
async def test_state_transitions_during_send(bus):
    stub = _StubAgent(reply="ok")
    ctrl = GUIController(event_bus=bus, agent=stub)

    statuses = []
    ctrl.state.subscribe(lambda old, new: statuses.append(new))

    await ctrl.send_message("hi")
    assert GUIStatus.THINKING in statuses
    assert statuses[-1] == GUIStatus.IDLE


@pytest.mark.asyncio
async def test_toggle_listening_starts_and_stops(bus):
    ctrl = GUIController(event_bus=bus, agent=_StubAgent())
    started = await ctrl.toggle_listening()
    assert started is True
    assert ctrl.state.status == GUIStatus.LISTENING
    stopped = await ctrl.toggle_listening()
    assert stopped is False
    assert ctrl.state.status == GUIStatus.IDLE


@pytest.mark.asyncio
async def test_cancel_sets_flag(bus):
    ctrl = GUIController(event_bus=bus, agent=_StubAgent())
    assert ctrl.is_cancelled() is False
    await ctrl.cancel_current_task()
    assert ctrl.is_cancelled() is True


@pytest.mark.asyncio
async def test_tool_events_forwarded_to_callback(bus):
    ctrl = GUIController(event_bus=bus, agent=_StubAgent())
    tool_events = []
    ctrl.on_tool_event(lambda e: tool_events.append(e))

    bus.publish(Event("TOOL_STARTED", {"name": "open_application"}))
    bus.publish(Event("TOOL_FINISHED", {"name": "open_application"}))

    assert len(tool_events) == 2
    assert tool_events[0]["event"] == "started"
    assert tool_events[1]["event"] == "finished"


@pytest.mark.asyncio
async def test_error_event_updates_state(bus):
    ctrl = GUIController(event_bus=bus, agent=_StubAgent())
    bus.publish(Event("ERROR", {"message": "network failed"}))
    assert ctrl.state.status == GUIStatus.ERROR
    assert "network" in ctrl.state.last_error


@pytest.mark.asyncio
async def test_speaking_events_update_state(bus):
    ctrl = GUIController(event_bus=bus, agent=_StubAgent())
    bus.publish(Event("SPEAKING_STARTED", {}))
    assert ctrl.state.status == GUIStatus.SPEAKING
    bus.publish(Event("SPEAKING_FINISHED", {}))
    assert ctrl.state.status == GUIStatus.IDLE


@pytest.mark.asyncio
async def test_set_agent_replaces_agent(bus):
    a1 = _StubAgent(reply="first")
    a2 = _StubAgent(reply="second")
    ctrl = GUIController(event_bus=bus, agent=a1)
    ctrl.set_agent(a2)
    reply = await ctrl.send_message("hi")
    assert reply == "second"