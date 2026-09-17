"""Tests for Phase 21 GUIState (no Qt needed)."""
from __future__ import annotations

import pytest

from app.gui.gui_state import GUIState, GUIStatus


def test_initial_state_is_idle():
    gs = GUIState()
    assert gs.status == GUIStatus.IDLE
    assert gs.is_busy() is False


def test_set_status_changes_value():
    gs = GUIState()
    gs.set(GUIStatus.LISTENING)
    assert gs.status == GUIStatus.LISTENING


def test_set_same_status_no_notify():
    gs = GUIState()
    seen = []
    gs.subscribe(lambda old, new: seen.append((old, new)))
    gs.set(GUIStatus.IDLE)
    assert seen == []


def test_subscribe_receives_transitions():
    gs = GUIState()
    seen = []
    gs.subscribe(lambda old, new: seen.append((old, new)))
    gs.set(GUIStatus.LISTENING)
    gs.set(GUIStatus.THINKING)
    assert (GUIStatus.IDLE, GUIStatus.LISTENING) in seen
    assert (GUIStatus.LISTENING, GUIStatus.THINKING) in seen


def test_unsubscribe_stops_notifications():
    gs = GUIState()
    seen = []
    cb = lambda old, new: seen.append((old, new))
    gs.subscribe(cb)
    gs.unsubscribe(cb)
    gs.set(GUIStatus.LISTENING)
    assert seen == []


def test_is_busy_states():
    gs = GUIState()
    gs.set(GUIStatus.LISTENING)
    assert gs.is_busy() is True
    gs.set(GUIStatus.THINKING)
    assert gs.is_busy() is True
    gs.set(GUIStatus.SPEAKING)
    assert gs.is_busy() is True
    gs.set(GUIStatus.IDLE)
    assert gs.is_busy() is False
    gs.set(GUIStatus.ERROR)
    assert gs.is_busy() is False


def test_set_task_and_clear():
    gs = GUIState()
    gs.set_task("create a calculator")
    assert gs.current_task == "create a calculator"
    gs.clear_task()
    assert gs.current_task == ""


def test_set_error_updates_status_and_message():
    gs = GUIState()
    gs.set_error("something failed")
    assert gs.status == GUIStatus.ERROR
    assert "failed" in gs.last_error


def test_clearing_error_on_non_error_status():
    gs = GUIState()
    gs.set_error("boom")
    assert gs.last_error == "boom"
    gs.set(GUIStatus.IDLE)
    assert gs.last_error == ""


def test_reset_returns_to_idle():
    gs = GUIState()
    gs.set_task("x")
    gs.set(GUIStatus.THINKING)
    gs.reset()
    assert gs.status == GUIStatus.IDLE
    assert gs.current_task == ""


def test_listener_exception_does_not_break():
    gs = GUIState()
    seen = []

    def bad(old, new):
        raise RuntimeError("listener broke")

    def good(old, new):
        seen.append(new)

    gs.subscribe(bad)
    gs.subscribe(good)
    gs.set(GUIStatus.LISTENING)
    assert seen == [GUIStatus.LISTENING]


def test_invalid_status_string_ignored():
    gs = GUIState()
    gs.set("NONEXISTENT_STATE")  # type: ignore[arg-type]
    assert gs.status == GUIStatus.IDLE


def test_status_from_string_conversion():
    gs = GUIState()
    gs.set("LISTENING")  # type: ignore[arg-type]
    assert gs.status == GUIStatus.LISTENING