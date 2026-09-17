"""Tests for Phase 20 Sandbox."""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager
from app.security.sandbox import Sandbox, SandboxState


@pytest.fixture(autouse=True)
def reset_sandbox():
    ConfigManager.load()
    ConfigManager.set("security.sandbox.enabled", True, persist=False)
    ConfigManager.set("security.sandbox.max_sandbox_steps", 5, persist=False)
    Sandbox.reload()
    yield
    Sandbox.exit()
    Sandbox.reload()


def test_starts_inactive():
    assert Sandbox.is_active() is False


def test_enter_activates():
    Sandbox.enter("unknown task")
    assert Sandbox.is_active() is True
    assert Sandbox.state().reason == "unknown task"


def test_exit_deactivates():
    Sandbox.enter("test")
    Sandbox.exit()
    assert Sandbox.is_active() is False


def test_allow_low_risk_in_sandbox():
    Sandbox.enter("test")
    assert Sandbox.allow_tool("open_application", "LOW") is True
    assert Sandbox.allow_tool("read_file", "LOW") is True


def test_allow_medium_risk_in_sandbox():
    Sandbox.enter("test")
    assert Sandbox.allow_tool("write_file", "MEDIUM") is True


def test_block_high_risk_in_sandbox():
    Sandbox.enter("test")
    assert Sandbox.allow_tool("delete_file", "HIGH") is False


def test_block_critical_risk_in_sandbox():
    Sandbox.enter("test")
    assert Sandbox.allow_tool("format_disk", "CRITICAL") is False


def test_allows_all_when_not_active():
    # Not entered — everything allowed
    assert Sandbox.allow_tool("delete_file", "HIGH") is True
    assert Sandbox.allow_tool("format_disk", "CRITICAL") is True


def test_disabled_sandbox_allows_all():
    ConfigManager.set("security.sandbox.enabled", False, persist=False)
    Sandbox.reload()
    Sandbox.enter("test")
    assert Sandbox.allow_tool("delete_file", "HIGH") is True


def test_max_steps_enforced():
    Sandbox.configure(enabled=True, max_steps=3)
    Sandbox.enter("test")
    # Only LOW/MEDIUM allowed — each call increments step count
    assert Sandbox.allow_tool("open_application", "LOW") is True
    assert Sandbox.allow_tool("open_application", "LOW") is True
    assert Sandbox.allow_tool("open_application", "LOW") is True
    # 4th call exceeds max_steps
    assert Sandbox.allow_tool("open_application", "LOW") is False


def test_state_to_dict():
    Sandbox.enter("test reason")
    state = Sandbox.state()
    d = state.to_dict()
    assert d["active"] is True
    assert d["reason"] == "test reason"
    assert "allowed_risks" in d


def test_describe_shape():
    info = Sandbox.describe()
    assert "enabled" in info
    assert "state" in info
    assert info["state"]["active"] is False