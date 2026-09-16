"""
Adobe After Effects integration (Adobe CC).

COM automation via pywin32. Requires AE installed.
Supports opening projects, queuing renders, and running JSX scripts.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _get_after_effects():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("AfterEffects.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        return win32com.client.Dispatch("AfterEffects.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("after_effects_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: after_effects_open_project
# ---------------------------------------------------------------------- #
class AfterEffectsOpenProjectTool(AppIntegrationTool):
    APP_KEY = "after_effects"
    CONFIG_SECTION = "integrations.adobe"

    name = "after_effects_open_project"
    description = "Open an After Effects project (.aep)."
    parameters = {
        "type": "object",
        "properties": {"project_path": {"type": "string"}},
        "required": ["project_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project_path = Path(str(kwargs.get("project_path", ""))).expanduser()
        if not project_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project_path)},
            )

        ae = _get_after_effects()
        if ae is None:
            return self._not_installed_result()

        try:
            ae.Open(str(project_path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"project": str(project_path)})


# ---------------------------------------------------------------------- #
# Tool: after_effects_add_to_render_queue
# ---------------------------------------------------------------------- #
class AfterEffectsAddToRenderQueueTool(AppIntegrationTool):
    APP_KEY = "after_effects"
    CONFIG_SECTION = "integrations.adobe"

    name = "after_effects_add_to_render_queue"
    description = "Add the active AE composition to the render queue."
    parameters = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
        },
        "required": ["output_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_path = Path(str(kwargs.get("output_path", ""))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ae = _get_after_effects()
        if ae is None:
            return self._not_installed_result()

        try:
            # JSX executes the queue add
            jsx = f'''
            var comp = app.project.activeItem;
            if (!comp) {{ throw new Error("No active composition"); }}
            var om = comp.renderQueue ? null : null;
            app.project.renderQueue.items.add(comp);
            var item = app.project.renderQueue.item(app.project.renderQueue.numItems);
            item.outputModule(1).file = new File("{output_path.as_posix()}");
            '''
            ae.DoJavaScript(jsx, 1)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "QUEUE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"output": str(output_path), "queued": True},
        )


# ---------------------------------------------------------------------- #
# Tool: after_effects_run_script
# ---------------------------------------------------------------------- #
class AfterEffectsRunScriptTool(AppIntegrationTool):
    APP_KEY = "after_effects"
    CONFIG_SECTION = "integrations.adobe"

    name = "after_effects_run_script"
    description = "Run a JSX script inside After Effects."
    parameters = {
        "type": "object",
        "properties": {"script_path": {"type": "string"}},
        "required": ["script_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        script_path = Path(str(kwargs.get("script_path", ""))).expanduser()
        if not script_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_NOT_FOUND", "message": str(script_path)},
            )

        ae = _get_after_effects()
        if ae is None:
            return self._not_installed_result()

        try:
            code = script_path.read_text(encoding="utf-8")
            ae.DoJavaScript(code, 1)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"script": str(script_path)},
        )