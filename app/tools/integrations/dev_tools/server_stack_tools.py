"""
XAMPP / WAMP server stack integration.

Starts and stops local Apache/MySQL services via the respective
control panels (xampp-control.exe / wampmanager.exe).

No paid service.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _xampp_root() -> Path | None:
    for p in (r"C:\xampp", r"C:\XAMPP", r"D:\xampp"):
        path = Path(p)
        if path.exists():
            return path
    return None


def _wamp_root() -> Path | None:
    for p in (r"C:\wamp64", r"C:\wamp", r"D:\wamp64", r"D:\wamp"):
        path = Path(p)
        if path.exists():
            return path
    return None


def _start_service(exe: str) -> subprocess.Popen:
    return subprocess.Popen(
        [exe],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# XAMPP
# ---------------------------------------------------------------------- #
class XamppStartTool(AppIntegrationTool):
    APP_KEY = "xampp"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "xampp_start"
    description = "Start XAMPP Control Panel (Apache/MySQL can be started there)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path() or (
            str(_xampp_root() / "xampp-control.exe") if _xampp_root() else None
        )
        if not exe or not Path(exe).exists():
            return self._not_installed_result()
        try:
            _start_service(exe)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"launched": True})


class XamppStopTool(AppIntegrationTool):
    APP_KEY = "xampp"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "xampp_stop"
    description = "Stop XAMPP services (kills httpd/mysqld)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        stopped: List[str] = []
        for name in ("httpd.exe", "mysqld.exe"):
            try:
                r = subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if r.returncode == 0:
                    stopped.append(name)
            except Exception:  # noqa: BLE001
                continue
        return ToolResult(
            success=True,
            tool=self.name,
            data={"stopped": stopped},
        )


# ---------------------------------------------------------------------- #
# WAMP
# ---------------------------------------------------------------------- #
class WampStartTool(AppIntegrationTool):
    APP_KEY = "wamp"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "wamp_start"
    description = "Start the WAMP Manager tray icon."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        exe = self._discover_path() or (
            str(_wamp_root() / "wampmanager.exe") if _wamp_root() else None
        )
        if not exe or not Path(exe).exists():
            return self._not_installed_result()
        try:
            _start_service(exe)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"launched": True})


class WampStopTool(AppIntegrationTool):
    APP_KEY = "wamp"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "wamp_stop"
    description = "Stop WAMP's Apache and MySQL services."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        stopped: List[str] = []
        for name in ("httpd.exe", "mysqld.exe", "wampmanager.exe"):
            try:
                r = subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if r.returncode == 0:
                    stopped.append(name)
            except Exception:  # noqa: BLE001
                continue
        return ToolResult(success=True, tool=self.name, data={"stopped": stopped})