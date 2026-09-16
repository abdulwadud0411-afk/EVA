"""
Tool registry (Phase 2).

Holds every registered tool. The agent uses this to:
    - expose tool schemas to the AI provider
    - execute a tool call requested by the AI

Every tool call is validated before execution.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Type

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)


class ToolRegistry:
    """Registry of all available tools."""

    _tools: Dict[str, Tool] = {}

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    @classmethod
    def register(cls, tool: Tool) -> None:
        """Register a tool instance. Name must be unique."""
        if not tool.name:
            raise ValueError(f"Tool {tool!r} has no name")
        if tool.name in cls._tools:
            logger.warning("tool_already_registered", name=tool.name)
        cls._tools[tool.name] = tool
        logger.info(
            "tool_registered",
            name=tool.name,
            risk=tool.risk_level.value,
        )

    @classmethod
    def register_class(cls, tool_cls: Type[Tool]) -> None:
        """Convenience: instantiate and register."""
        cls.register(tool_cls())

    @classmethod
    def clear(cls) -> None:
        """Remove all tools (used by tests)."""
        cls._tools.clear()

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    @classmethod
    def get(cls, name: str) -> Optional[Tool]:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[str]:
        return sorted(cls._tools.keys())

    @classmethod
    def all_schemas(cls) -> List[Dict[str, Any]]:
        """Return schemas for every registered tool."""
        return [tool.schema() for tool in cls._tools.values()]

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    @classmethod
    async def execute(
        cls,
        name: str,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """
        Validate and execute a tool call.

        Always returns a ToolResult, even on failure.
        Never raises for tool errors (only for programmer errors).
        """
        start = time.perf_counter()

        tool = cls._tools.get(name)
        if tool is None:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning("tool_not_found", name=name)
            return ToolResult(
                success=False,
                tool=name,
                error={
                    "code": "TOOL_NOT_FOUND",
                    "message": f"Tool '{name}' is not registered",
                },
                duration_ms=duration_ms,
            )

        # Validate arguments against declared parameters
        validation_error = cls._validate_arguments(tool, arguments)
        if validation_error is not None:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "tool_invalid_args",
                name=name,
                error=validation_error,
            )
            return ToolResult(
                success=False,
                tool=name,
                error={
                    "code": "INVALID_ARGUMENTS",
                    "message": validation_error,
                },
                duration_ms=duration_ms,
            )

        # Execute
        try:
            logger.info("tool_executing", name=name, args=arguments)
            result = await tool.run(**arguments)
            # Fill in name and duration if the tool did not
            if not result.tool:
                result.tool = name
            result.duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "tool_executed",
                name=name,
                success=result.success,
                duration_ms=result.duration_ms,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "tool_execution_failed",
                name=name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return ToolResult(
                success=False,
                tool=name,
                error={
                    "code": "TOOL_EXECUTION_ERROR",
                    "message": str(exc),
                },
                duration_ms=duration_ms,
            )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @classmethod
    def _validate_arguments(
        cls,
        tool: Tool,
        arguments: Dict[str, Any],
    ) -> Optional[str]:
        """
        Lightweight schema check.

        Returns an error string if invalid, or None if valid.
        Handles: required fields, unexpected fields, basic type checks.
        """
        if not isinstance(arguments, dict):
            return "Arguments must be a dictionary"

        schema_params = tool.parameters or {}
        properties: Dict[str, Any] = schema_params.get("properties", {})
        required: List[str] = schema_params.get("required", [])

        # Check required fields
        for field_name in required:
            if field_name not in arguments:
                return f"Missing required argument: '{field_name}'"

        # Check that all provided args are declared (if schema has properties)
        if properties:
            for key in arguments.keys():
                if key not in properties:
                    return f"Unexpected argument: '{key}'"

        # Basic type checks
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        for key, value in arguments.items():
            if key not in properties:
                continue
            expected_type = properties[key].get("type")
            if expected_type is None:
                continue
            py_type = type_map.get(expected_type)
            if py_type is None:
                continue
            # bool is a subclass of int in Python; guard against it
            if expected_type == "integer" and isinstance(value, bool):
                return f"Argument '{key}' must be integer, got boolean"
            if not isinstance(value, py_type):
                return (
                    f"Argument '{key}' must be {expected_type}, "
                    f"got {type(value).__name__}"
                )

        return None