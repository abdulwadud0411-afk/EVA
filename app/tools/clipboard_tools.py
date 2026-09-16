"""
Clipboard tools (Phase 5).

Tools:
    - get_clipboard_text
    - set_clipboard_text
    - clear_clipboard
    - get_clipboard_info

Uses pyperclip for text access. Image clipboard access requires
pywin32 (available on Windows).
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)

try:
    import pyperclip  # type: ignore
    _PYPERCLIP_AVAILABLE = True
except Exception:  # noqa: BLE001
    pyperclip = None  # type: ignore
    _PYPERCLIP_AVAILABLE = False


def _ensure_pyperclip(tool_name: str) -> Optional[ToolResult]:
    if not _PYPERCLIP_AVAILABLE:
        return ToolResult(
            success=False,
            tool=tool_name,
            error={
                "code": "PLATFORM_UNSUPPORTED",
                "message": "Clipboard access requires pyperclip.",
            },
        )
    return None


# ---------------------------------------------------------------------- #
# Tool: get_clipboard_text
# ---------------------------------------------------------------------- #
class GetClipboardTextTool(Tool):
    name = "get_clipboard_text"
    description = "Return the current text contents of the clipboard."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_pyperclip(self.name)
        if err is not None:
            return err

        try:
            text = pyperclip.paste()  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("clipboard_read_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "READ_FAILED", "message": str(exc)},
            )

        text = text or ""
        return ToolResult(
            success=True,
            tool=self.name,
            data={"text": text, "length": len(text)},
        )


# ---------------------------------------------------------------------- #
# Tool: set_clipboard_text
# ---------------------------------------------------------------------- #
class SetClipboardTextTool(Tool):
    name = "set_clipboard_text"
    description = "Copy the given text into the clipboard."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_pyperclip(self.name)
        if err is not None:
            return err

        text = kwargs.get("text")
        if text is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text is required"},
            )

        text = str(text)
        try:
            pyperclip.copy(text)  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.error("clipboard_write_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "WRITE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"length": len(text)},
        )


# ---------------------------------------------------------------------- #
# Tool: clear_clipboard
# ---------------------------------------------------------------------- #
class ClearClipboardTool(Tool):
    name = "clear_clipboard"
    description = "Clear the clipboard (set to empty string)."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_pyperclip(self.name)
        if err is not None:
            return err

        try:
            pyperclip.copy("")  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CLEAR_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"cleared": True})


# ---------------------------------------------------------------------- #
# Tool: get_clipboard_info
# ---------------------------------------------------------------------- #
class GetClipboardInfoTool(Tool):
    name = "get_clipboard_info"
    description = (
        "Report basic information about the clipboard: whether it "
        "contains text, image, or is empty."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_pyperclip(self.name)
        if err is not None:
            return err

        has_text = False
        text_length = 0
        preview = ""
        try:
            text = pyperclip.paste() or ""  # type: ignore
            has_text = bool(text.strip())
            text_length = len(text)
            preview = text[:100]
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "READ_FAILED", "message": str(exc)},
            )

        # Try to detect image content via win32clipboard (Windows only)
        has_image = False
        try:
            import win32clipboard  # type: ignore
            win32clipboard.OpenClipboard()
            try:
                has_image = bool(win32clipboard.IsClipboardFormatAvailable(8))  # CF_DIB
            finally:
                win32clipboard.CloseClipboard()
        except Exception:  # noqa: BLE001
            has_image = False

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "has_text": has_text,
                "text_length": text_length,
                "has_image": has_image,
                "preview": preview,
                "empty": not has_text and not has_image,
            },
        )