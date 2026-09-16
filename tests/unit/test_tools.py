"""
Tests for the Phase 2 tool system.

Covers:
    - Tool ABC and ToolResult structure
    - ToolRegistry registration, listing, schema generation
    - Argument validation (missing required, unexpected, wrong type)
    - Execution success and failure paths
    - Real Phase 2 tools (app_tools) — with subprocess mocked
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

import pytest

from app.tools.base import Tool, ToolResult, RiskLevel
from app.tools.registry import ToolRegistry


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure a fresh registry for every test."""
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


# ---------------------------------------------------------------------- #
# A minimal dummy tool used for registry tests
# ---------------------------------------------------------------------- #
class _EchoTool(Tool):
    name = "echo"
    description = "Echo the given text back."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["text"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        count = int(kwargs.get("count", 1))
        return ToolResult(success=True, tool=self.name, data={"text": text * count})


class _BoomTool(Tool):
    name = "boom"
    description = "Always raises."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("intentional failure")


# ---------------------------------------------------------------------- #
# Base classes
# ---------------------------------------------------------------------- #
def test_tool_result_to_dict_roundtrip():
    r = ToolResult(success=True, tool="x", data={"a": 1}, duration_ms=5)
    d = r.to_dict()
    assert d == {
        "success": True,
        "tool": "x",
        "data": {"a": 1},
        "error": None,
        "duration_ms": 5,
    }


def test_tool_schema_shape():
    schema = _EchoTool().schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "echo"
    assert schema["function"]["parameters"]["required"] == ["text"]


def test_tool_without_name_raises():
    class _NoName(Tool):
        name = ""
        async def run(self, **kwargs):
            return ToolResult(success=True, tool="")

    with pytest.raises(ValueError, match="has no name"):
        ToolRegistry.register(_NoName())


# ---------------------------------------------------------------------- #
# Registration & listing
# ---------------------------------------------------------------------- #
def test_register_and_list():
    ToolRegistry.register(_EchoTool())
    ToolRegistry.register(_BoomTool())
    assert ToolRegistry.list_tools() == ["boom", "echo"]


def test_register_class_instantiates():
    ToolRegistry.register_class(_EchoTool)
    assert ToolRegistry.get("echo") is not None


def test_all_schemas_contains_every_tool():
    ToolRegistry.register_class(_EchoTool)
    ToolRegistry.register_class(_BoomTool)
    schemas = ToolRegistry.all_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == {"echo", "boom"}


# ---------------------------------------------------------------------- #
# Validation
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_execute_missing_required_argument():
    ToolRegistry.register_class(_EchoTool)
    result = await ToolRegistry.execute("echo", {})
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENTS"
    assert "text" in result.error["message"]


@pytest.mark.asyncio
async def test_execute_unexpected_argument():
    ToolRegistry.register_class(_EchoTool)
    result = await ToolRegistry.execute("echo", {"text": "hi", "bogus": 1})
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENTS"
    assert "bogus" in result.error["message"]


@pytest.mark.asyncio
async def test_execute_wrong_type():
    ToolRegistry.register_class(_EchoTool)
    result = await ToolRegistry.execute("echo", {"text": "hi", "count": "not-an-int"})
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENTS"
    assert "count" in result.error["message"]


@pytest.mark.asyncio
async def test_execute_bool_for_integer_is_rejected():
    ToolRegistry.register_class(_EchoTool)
    result = await ToolRegistry.execute("echo", {"text": "hi", "count": True})
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENTS"


# ---------------------------------------------------------------------- #
# Execution
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_execute_unknown_tool():
    result = await ToolRegistry.execute("does_not_exist", {})
    assert result.success is False
    assert result.error["code"] == "TOOL_NOT_FOUND"


@pytest.mark.asyncio
async def test_execute_success():
    ToolRegistry.register_class(_EchoTool)
    result = await ToolRegistry.execute("echo", {"text": "ha", "count": 3})
    assert result.success is True
    assert result.tool == "echo"
    assert result.data == {"text": "hahaha"}
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_execute_catches_exception():
    ToolRegistry.register_class(_BoomTool)
    result = await ToolRegistry.execute("boom", {})
    assert result.success is False
    assert result.error["code"] == "TOOL_EXECUTION_ERROR"
    assert "intentional failure" in result.error["message"]


# ---------------------------------------------------------------------- #
# Real Phase 2 tools: app_tools (with subprocess mocked)
# ---------------------------------------------------------------------- #
def test_real_phase2_tools_registered():
    """Importing app.tools should register the three Phase 2 tools."""
    import importlib
    import app.tools as tools_pkg
    importlib.reload(tools_pkg)

    names = set(ToolRegistry.list_tools())
    assert {"open_application", "close_application", "list_running_applications"} <= names


@pytest.mark.asyncio
async def test_open_application_success():
    """open_application should call subprocess.Popen and verify via tasklist."""
    import app.tools.app_tools as app_tools_module
    app_tools_module.OpenApplicationTool()  # ensure imported
    from app.tools.app_tools import OpenApplicationTool

    tool = OpenApplicationTool()

    fake_tasklist = type(
        "R", (), {
            "stdout": "Image Name    PID\nnotepad.exe    1234\n",
            "returncode": 0,
        }
    )()

    with patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run", return_value=fake_tasklist), \
         patch("time.sleep", return_value=None):
        result = await tool.run(application="notepad")

    assert mock_popen.called
    assert result.success is True
    assert result.data["application"] == "notepad"
    assert result.data["command"] == "notepad"
    assert result.data["verified_running"] is True


@pytest.mark.asyncio
async def test_open_application_missing_argument():
    from app.tools.app_tools import OpenApplicationTool
    result = await OpenApplicationTool().run()
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_open_application_popen_failure():
    from app.tools.app_tools import OpenApplicationTool
    with patch("subprocess.Popen", side_effect=FileNotFoundError):
        result = await OpenApplicationTool().run(application="ghostapp")
    assert result.success is False
    assert result.error["code"] == "APP_NOT_FOUND"


@pytest.mark.asyncio
async def test_close_application_success():
    from app.tools.app_tools import CloseApplicationTool

    fake = type(
        "R", (), {
            "stdout": "SUCCESS: The process \"notepad.exe\" has been terminated.",
            "stderr": "",
            "returncode": 0,
        }
    )()

    with patch("subprocess.run", return_value=fake):
        result = await CloseApplicationTool().run(application="notepad")

    assert result.success is True
    assert result.data["process_name"] == "notepad.exe"


@pytest.mark.asyncio
async def test_close_application_not_found():
    from app.tools.app_tools import CloseApplicationTool

    fake = type(
        "R", (), {
            "stdout": "ERROR: The process \"ghost.exe\" not found.",
            "stderr": "",
            "returncode": 128,
        }
    )()

    with patch("subprocess.run", return_value=fake):
        result = await CloseApplicationTool().run(application="ghost")

    assert result.success is False
    assert result.error["code"] == "PROCESS_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_running_applications_success():
    from app.tools.app_tools import ListRunningApplicationsTool

    fake = type(
        "R", (), {
            "stdout": (
                '"chrome.exe","1234","Console","1","100,000 K"\n'
                '"notepad.exe","5678","Console","1","5,000 K"\n'
            ),
            "returncode": 0,
        }
    )()

    with patch("subprocess.run", return_value=fake):
        result = await ListRunningApplicationsTool().run(limit=10)

    assert result.success is True
    assert "chrome.exe" in result.data["processes"]
    assert "notepad.exe" in result.data["processes"]
    assert result.data["count"] == 2


@pytest.mark.asyncio
async def test_list_running_applications_respects_limit():
    from app.tools.app_tools import ListRunningApplicationsTool

    lines = "\n".join(f'"app{i}.exe","{i}","Console","1","1 K"' for i in range(50))
    fake = type("R", (), {"stdout": lines + "\n", "returncode": 0})()

    with patch("subprocess.run", return_value=fake):
        result = await ListRunningApplicationsTool().run(limit=5)

    assert result.success is True
    assert len(result.data["processes"]) == 5