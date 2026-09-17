"""Tests for Phase 19 CommandGuard."""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager
from app.security.command_guard import CommandGuard, CommandDecision


@pytest.fixture(autouse=True)
def reset_guard():
    CommandGuard.reload()
    ConfigManager.load()
    yield
    CommandGuard.reload()


def test_empty_command_blocked():
    d = CommandGuard.check("")
    assert d.allowed is False
    assert d.matched_rule == "empty"


def test_allowlisted_python():
    d = CommandGuard.check("python script.py")
    assert d.allowed is True
    assert d.matched_rule == "allowlist"


def test_allowlisted_git_status():
    d = CommandGuard.check("git status")
    assert d.allowed is True


def test_allowlisted_dir():
    d = CommandGuard.check("dir")
    assert d.allowed is True


def test_blocked_format():
    d = CommandGuard.check("format C:")
    assert d.allowed is False
    assert d.matched_rule == "blocklist"


def test_blocked_diskpart():
    d = CommandGuard.check("diskpart /s script.txt")
    assert d.allowed is False


def test_blocked_shutdown():
    d = CommandGuard.check("shutdown /s /t 0")
    assert d.allowed is False


def test_blocked_del_s():
    d = CommandGuard.check("del /s C:\\temp")
    assert d.allowed is False


def test_blocked_rm_rf():
    d = CommandGuard.check("rm -rf /")
    assert d.allowed is False


def test_blocked_powershell_encoded():
    d = CommandGuard.check("powershell -enc BASE64STRING")
    assert d.allowed is False


def test_unlisted_requires_confirmation():
    d = CommandGuard.check("weird_command_xyz")
    assert d.allowed is False
    assert d.requires_confirmation is True
    assert d.matched_rule == "unlisted"


def test_case_insensitive_allowlist():
    d = CommandGuard.check("PYTHON script.py")
    assert d.allowed is True


def test_path_with_exe_stripped():
    d = CommandGuard.check("C:\\Python\\python.exe script.py")
    assert d.allowed is True


def test_describe_shape():
    info = CommandGuard.describe()
    assert "allowlist" in info
    assert "blocklist_patterns" in info
    assert isinstance(info["allowlist"], list)


def test_decision_to_dict():
    d = CommandDecision(allowed=True, requires_confirmation=False, reason="ok")
    as_dict = d.to_dict()
    assert as_dict["allowed"] is True