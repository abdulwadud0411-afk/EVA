"""
Unreal Engine integration (Creative 3D).

Unreal Editor is controlled via its built-in Remote Control HTTP API,
which is enabled by the "Remote Control API" plugin that ships with UE.

Endpoint default: http://127.0.0.1:30010

Tools:
    - unreal_ping                 : verify Remote Control API is reachable
    - unreal_run_console_command  : execute a console command in the editor
    - unreal_list_actors          : list actors in the current level
"""
from __future__ import annotations

from typing import Any, Dict, List

import httpx

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _base_url(tool: "AppIntegrationTool") -> str:
    return str(tool._config("remote_control_url", "http://127.0.0.1:30010")).rstrip("/")


async def _rc_get(url: str, timeout: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.get(url)


async def _rc_put(url: str, payload: Dict[str, Any], timeout: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.put(url, json=payload)


# ---------------------------------------------------------------------- #
# Tool: unreal_ping
# ---------------------------------------------------------------------- #
class UnrealPingTool(AppIntegrationTool):
    APP_KEY = "unreal"
    CONFIG_SECTION = "integrations.unreal"

    name = "unreal_ping"
    description = "Check whether Unreal Editor's Remote Control API is reachable."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = _base_url(self)
        try:
            r = await _rc_get(f"{base}/remote/info", timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "UNREAL_UNREACHABLE",
                    "message": f"Remote Control API not reachable at {base}: {exc}",
                },
            )
        return ToolResult(
            success=r.status_code == 200,
            tool=self.name,
            data={"endpoint": base, "status": r.status_code},
        )


# ---------------------------------------------------------------------- #
# Tool: unreal_run_console_command
# ---------------------------------------------------------------------- #
class UnrealRunConsoleCommandTool(AppIntegrationTool):
    APP_KEY = "unreal"
    CONFIG_SECTION = "integrations.unreal"

    name = "unreal_run_console_command"
    description = "Execute an Unreal console command inside the editor."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
        },
        "required": ["command"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        command = str(kwargs.get("command", "")).strip()
        if not command:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "command required"},
            )

        base = _base_url(self)
        url = f"{base}/remote/object/call"
        payload = {
            "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
            "functionName": "ExecuteConsoleCommand",
            "parameters": {
                "WorldContextObject": None,
                "Command": command,
                "SpecificPlayer": None,
            },
        }
        try:
            r = await _rc_put(url, payload, timeout=15.0)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RC_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.status_code in (200, 201, 204),
            tool=self.name,
            data={"command": command, "status": r.status_code},
        )


# ---------------------------------------------------------------------- #
# Tool: unreal_list_actors
# ---------------------------------------------------------------------- #
class UnrealListActorsTool(AppIntegrationTool):
    APP_KEY = "unreal"
    CONFIG_SECTION = "integrations.unreal"

    name = "unreal_list_actors"
    description = "List actors in the currently loaded Unreal level."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer"},
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            limit = int(kwargs.get("limit") or 100)
        except (TypeError, ValueError):
            limit = 100
        if limit <= 0 or limit > 5000:
            limit = 100

        base = _base_url(self)
        url = f"{base}/remote/object/describe"
        # Query the world for actors via the level's actor iterator.
        payload = {
            "objectPath": "/Game/Maps/CurrentLevel.CurrentLevel:PersistentLevel",
            "functionName": "GetActors",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.put(url, json=payload)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "RC_FAILED", "message": str(exc)},
            )

        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            data = {}

        actors: List[Dict[str, Any]] = []
        raw = data.get("ReturnValue") or data.get("Actors") or []
        if isinstance(raw, list):
            for item in raw[:limit]:
                if isinstance(item, dict):
                    actors.append({
                        "name": item.get("Name") or item.get("ObjectName"),
                        "path": item.get("Path") or item.get("ObjectPath"),
                    })

        return ToolResult(
            success=r.status_code == 200,
            tool=self.name,
            data={"count": len(actors), "actors": actors},
        )