"""Tests for Phase 19 terminal tool."""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager
from app.security.command_guard import CommandGuard
from app.tools.terminal_tools import RunTerminalCommandTool


@pytest.fixture(autouse=True)
def reset_guard():
    CommandGuard.reload()
    ConfigManager.load()
    yield
    CommandGuard.reload()


@pytest.mark.asyncio
async def test_empty_command():
    r = await RunTerminalCommandTool().run(command="")
    assert r.success is False
    assert r.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_blocked_command():
    r = await RunTerminalCommandTool().run(command="format C:")
    assert r.success is False
    assert r.error["code"] == "COMMAND_BLOCKED"


@pytest.mark.asyncio
async def test_unlisted_requires_confirmation():
    r = await RunTerminalCommandTool().run(command="weird_thing_xyz --help")
    assert r.success is False
    assert r.error["code"] == "CONFIRMATION_REQUIRED"


@pytest.mark.asyncio
async def test_allowlisted_python_runs(tmp_path):
    """Run a harmless python one-liner via the allowlisted `python` command."""
    script = tmp_path / "print_ok.py"
    script.write_text("print('EVATEST')\n", encoding="utf-8")

    r = await RunTerminalCommandTool().run(
        command=f'python "{script}"',
        timeout_seconds=30,
    )
    assert r.success is True, r.error
    assert "EVATEST" in r.data["stdout"]


@pytest.mark.asyncio
async def test_allowlisted_with_confirmed_flag_still_runs():
    """Confirmed flag doesn't break allowlisted commands."""
    from app.core.config_manager import ConfigManager as CM
    workspace = CM.get_data_dir() / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    s = workspace / "quick.py"
    s.write_text("print('X')", encoding="utf-8")

    r = await RunTerminalCommandTool().run(
        command=f'python "{s}"',
        confirmed=True,
        timeout_seconds=30,
    )
    assert r.success is True


@pytest.mark.asyncio
async def test_timeout_returns_error(tmp_path):
    script = tmp_path / "sleep.py"
    script.write_text("import time; time.sleep(10)\n", encoding="utf-8")
    r = await RunTerminalCommandTool().run(
        command=f'python "{script}"',
        timeout_seconds=1,
    )
    assert r.success is False
    assert r.error["code"] == "TIMEOUT"


@pytest.mark.asyncio
async def test_nonzero_exit_reported():
    r = await RunTerminalCommandTool().run(
        command='python -c "import sys; sys.exit(2)"',
        timeout_seconds=15,
    )
    assert r.success is False
    assert r.data["returncode"] == 2
    assert r.error["code"] == "NONZERO_EXIT"