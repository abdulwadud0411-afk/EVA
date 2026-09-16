"""
Vision-based screen understanding tools (Phase 6).

Tools:
    - analyze_screen    : screenshot + prompt -> text description
    - find_ui_element   : screenshot + element name -> coordinates

Both tools delegate to the VisionClient, which uses the active AI
provider's vision model (DeepSeek by default).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.brain.vision import VisionClient, VisionError
from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel
from app.tools.screen_tools import capture_for_vision

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Tool: analyze_screen
# ---------------------------------------------------------------------- #
class AnalyzeScreenTool(Tool):
    name = "analyze_screen"
    description = (
        "Take a screenshot and ask the vision model to describe what "
        "is visible. Returns the model's text description."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Optional question about the screen contents.",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        prompt = kwargs.get("prompt")
        try:
            image_path = capture_for_vision()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CAPTURE_FAILED", "message": str(exc)},
            )

        try:
            client = VisionClient()
            result = await client.analyze_image(image_path, prompt=prompt)
        except VisionError as exc:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VISION_FAILED", "message": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("analyze_screen_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VISION_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "text": result.get("text", ""),
                "screenshot": str(image_path),
                "model_used": result.get("model_used"),
            },
        )


# ---------------------------------------------------------------------- #
# Tool: find_ui_element
# ---------------------------------------------------------------------- #
class FindUiElementTool(Tool):
    name = "find_ui_element"
    description = (
        "Locate a UI element (button, icon, text) on the current "
        "screen. Returns its screen coordinates and confidence."
    )
    parameters = {
        "type": "object",
        "properties": {
            "element": {
                "type": "string",
                "description": "Description of the UI element to find.",
            },
        },
        "required": ["element"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        element = str(kwargs.get("element", "")).strip()
        if not element:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "element description is required",
                },
            )

        try:
            image_path = capture_for_vision()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CAPTURE_FAILED", "message": str(exc)},
            )

        try:
            client = VisionClient()
            result = await client.find_element(image_path, element)
        except VisionError as exc:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VISION_FAILED", "message": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("find_ui_element_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VISION_FAILED", "message": str(exc)},
            )

        if not result.get("found"):
            return ToolResult(
                success=True,
                tool=self.name,
                data={
                    "found": False,
                    "element": result.get("element", element),
                    "reason": result.get("reason", ""),
                    "confidence": result.get("confidence", 0.0),
                    "screenshot": str(image_path),
                },
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "found": True,
                "element": result.get("element", element),
                "x": result.get("x"),
                "y": result.get("y"),
                "confidence": result.get("confidence", 0.0),
                "reason": result.get("reason", ""),
                "screenshot": str(image_path),
            },
        )