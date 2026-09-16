"""
Microsoft Word integration (Office 365).

COM automation via pywin32. Requires Word installed.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists, process_running

logger = get_logger(__name__)


def _get_word():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("Word.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        app = win32com.client.Dispatch("Word.Application")
        app.Visible = True
        return app
    except Exception as exc:  # noqa: BLE001
        logger.error("word_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: word_open
# ---------------------------------------------------------------------- #
class WordOpenTool(AppIntegrationTool):
    APP_KEY = "word"
    CONFIG_SECTION = "integrations.office"

    name = "word_open"
    description = "Open a Word document (.docx/.doc) in Microsoft Word."
    parameters = {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": ["file_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        file_path = Path(str(kwargs.get("file_path", ""))).expanduser()
        if not file_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FILE_NOT_FOUND", "message": str(file_path)},
            )

        word = _get_word()
        if word is None:
            return self._not_installed_result(
                hint="Install Microsoft Word and ensure pywin32 is available."
            )

        try:
            doc = word.Documents.Open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"file": str(file_path), "open": True},
        )


# ---------------------------------------------------------------------- #
# Tool: word_create
# ---------------------------------------------------------------------- #
class WordCreateTool(AppIntegrationTool):
    APP_KEY = "word"
    CONFIG_SECTION = "integrations.office"

    name = "word_create"
    description = "Create a new Word document and save it to the given path."
    parameters = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "initial_text": {"type": "string"},
        },
        "required": ["output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_path = Path(str(kwargs.get("output_path", ""))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        initial_text = str(kwargs.get("initial_text") or "")

        word = _get_word()
        if word is None:
            return self._not_installed_result()

        try:
            doc = word.Documents.Add()
            if initial_text:
                doc.Content.Text = initial_text
            doc.SaveAs(str(output_path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CREATE_FAILED", "message": str(exc)},
            )

        time.sleep(0.5)
        check = file_exists(str(output_path), min_size_bytes=100)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(output_path), "verified": check},
        )


# ---------------------------------------------------------------------- #
# Tool: word_insert_text
# ---------------------------------------------------------------------- #
class WordInsertTextTool(AppIntegrationTool):
    APP_KEY = "word"
    CONFIG_SECTION = "integrations.office"

    name = "word_insert_text"
    description = "Insert text at the end of the currently open Word document."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        text = str(kwargs.get("text") or "")
        if not text:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text is empty"},
            )

        word = _get_word()
        if word is None:
            return self._not_installed_result()

        try:
            doc = word.ActiveDocument
            rng = doc.Content
            rng.Collapse(0)  # wdCollapseEnd
            rng.InsertAfter(text)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INSERT_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"inserted_length": len(text)},
        )


# ---------------------------------------------------------------------- #
# Tool: word_export_pdf
# ---------------------------------------------------------------------- #
class WordExportPdfTool(AppIntegrationTool):
    APP_KEY = "word"
    CONFIG_SECTION = "integrations.office"

    name = "word_export_pdf"
    description = "Export the active Word document to PDF."
    parameters = {
        "type": "object",
        "properties": {"output_path": {"type": "string"}},
        "required": ["output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        output_path = Path(str(kwargs.get("output_path", ""))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        word = _get_word()
        if word is None:
            return self._not_installed_result()

        try:
            doc = word.ActiveDocument
            doc.SaveAs(str(output_path), FileFormat=17)  # wdFormatPDF
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "EXPORT_FAILED", "message": str(exc)},
            )

        time.sleep(0.7)
        check = file_exists(str(output_path), min_size_bytes=1000)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"output": str(output_path), "verified": check},
        )