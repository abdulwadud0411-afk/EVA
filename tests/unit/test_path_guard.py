"""Tests for Phase 19 PathGuard."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config_manager import ConfigManager
from app.security.path_guard import PathGuard, PathViolation


@pytest.fixture(autouse=True)
def reset_guard():
    PathGuard.reload()
    ConfigManager.load()
    yield
    PathGuard.reload()


def test_default_roots_loaded():
    allowed = PathGuard.allowed_roots()
    assert len(allowed) >= 3
    blocked = PathGuard.blocked_roots()
    assert any("Windows" in str(p) for p in blocked)


def test_workspace_allowed():
    workspace = ConfigManager.get_data_dir() / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    test_file = workspace / "test.txt"
    assert PathGuard.is_allowed(test_file) is True


def test_desktop_allowed():
    desktop = Path.home() / "Desktop"
    test_file = desktop / "eva_test.txt"
    assert PathGuard.is_allowed(test_file) is True


def test_windows_blocked():
    assert PathGuard.is_allowed("C:\\Windows\\System32\\cmd.exe") is False


def test_program_files_blocked():
    assert PathGuard.is_allowed("C:\\Program Files\\Google\\Chrome\\chrome.exe") is False


def test_outside_all_roots_blocked():
    assert PathGuard.is_allowed("D:\\random\\file.txt") is False


def test_resolve_succeeds_for_allowed():
    workspace = ConfigManager.get_data_dir() / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "resolve_test.txt"
    resolved = PathGuard.resolve(target)
    assert resolved.is_absolute()
    assert resolved.name == "resolve_test.txt"


def test_resolve_raises_for_windows():
    with pytest.raises(PathViolation, match="blocked root"):
        PathGuard.resolve("C:\\Windows\\System32\\config")


def test_resolve_raises_for_outside():
    with pytest.raises(PathViolation, match="outside all allowed"):
        PathGuard.resolve("D:\\random\\nope.txt")


def test_resolve_none_raises():
    with pytest.raises(PathViolation):
        PathGuard.resolve(None)


def test_describe_shape():
    info = PathGuard.describe()
    assert "allowed_roots" in info
    assert "blocked_roots" in info
    assert isinstance(info["allowed_roots"], list)