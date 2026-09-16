"""
CapCut integration (Design & Social).

CapCut has no public API. Automation is done via UI control using
pyautogui + window management. This is a best-effort integration:
it can launch CapCut, import media through the "Import" dialog, and
click on-screen elements by template matching (future).

Tools:
    - capcut_open          : launch CapCut
    - capcut_import_media  : open Import dialog and send media paths
    - capcut_click         : click on a position (fallback)
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import process_running, wait_for_process

logger = get_logger(__name__)


def _ensure_pyautogui():
    try:
        import pyautogui  # type: ignore
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return pyautogui
    except Exception as exc:  # noqa: BLE001
        logger.error("pyautogui_not_available", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: capcut_open
# ---------------------------------------------------------------------- #
class CapCutOpenTool(AppIntegrationTool):
    APP_KEY = "capcut"
    CONFIG_SECTION = "integrations.capcut"

    name = "capcut_open"
    description = "Launch CapCut and wait until its window is visible."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        executable = self._discover_path()
        if not executable:
            return self._not_installed_result(
                hint="Install CapCut or set integrations.capcut.executable_path."
            )

        # Already running?
        if process_running("CapCut")["verified"]:
            return ToolResult(
                success=True,
                tool=self.name,
                data={"already_running": True},
            )

        try:
            subprocess.Popen(
                [executable],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )

        check = wait_for_process("CapCut", timeout=20.0)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"launched": True, "verified": check},
        )


# ---------------------------------------------------------------------- #
# Tool: capcut_import_media
# ---------------------------------------------------------------------- #
class CapCutImportMediaTool(AppIntegrationTool):
    APP_KEY = "capcut"
    CONFIG_SECTION = "integrations.capcut"

    name = "capcut_import_media"
    description = (
        "Bring the CapCut window forward and open the Import dialog. "
        "Then type the file paths (best-effort UI automation)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "media_paths": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["media_paths"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        paths: List[str] = list(kwargs.get("media_paths") or [])
        if not paths:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "media_paths empty"},
            )
        for p in paths:
            if not Path(p).exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "MEDIA_NOT_FOUND", "message": str(p)},
                )

        gui = _ensure_pyautogui()
        if gui is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "PLATFORM_UNSUPPORTED",
                    "message": "pyautogui not available.",
                },
            )

        # Focus CapCut window
        try:
            import win32gui  # type: ignore
            import win32con  # type: ignore

            target_hwnd = None

            def _enum(hwnd, _):
                nonlocal target_hwnd
                if target_hwnd:
                    return True
                title = win32gui.GetWindowText(hwnd)
                if "CapCut" in title:
                    target_hwnd = hwnd
                return True

            win32gui.EnumWindows(_enum, None)
            if target_hwnd:
                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
                time.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("capcut_focus_failed", error=str(exc))

        # Trigger Import (Ctrl+I is CapCut's default)
        try:
            gui.hotkey("ctrl", "i")
            time.sleep(1.0)
            # Fill the file dialog by typing paths (best-effort).
            joined = '" "'.join(paths)
            gui.typewrite(f'"{joined}"', interval=0.02)
            time.sleep(0.3)
            gui.press("enter")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "UI_AUTOMATION_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"imported": paths, "count": len(paths), "note": "best-effort UI automation"},
        )


# ---------------------------------------------------------------------- #
# Tool: capcut_click
# ---------------------------------------------------------------------- #
class CapCutClickTool(AppIntegrationTool):
    APP_KEY = "capcut"
    CONFIG_SECTION = "integrations.capcut"

    name = "capcut_click"
    description = (
        "Click at absolute coordinates inside the focused CapCut window. "
        "Useful for clicking known buttons during scripted workflows."
    )
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        gui = _ensure_pyautogui()
        if gui is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PLATFORM_UNSUPPORTED", "message": "pyautogui missing"},
            )

        try:
            x = int(kwargs.get("x"))
            y = int(kwargs.get("y"))
        except (TypeError, ValueError):
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "x, y must be integers"},
            )

        try:
            gui.click(x=x, y=y)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CLICK_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"x": x, "y": y})