"""
Microsoft Excel integration (Office 365).

COM automation via pywin32. Requires Excel installed.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _get_excel():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.GetActiveObject("Excel.Application")
    except Exception:  # noqa: BLE001
        pass

    try:
        app = win32com.client.Dispatch("Excel.Application")
        app.Visible = True
        return app
    except Exception as exc:  # noqa: BLE001
        logger.error("excel_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: excel_open
# ---------------------------------------------------------------------- #
class ExcelOpenTool(AppIntegrationTool):
    APP_KEY = "excel"
    CONFIG_SECTION = "integrations.office"

    name = "excel_open"
    description = "Open an Excel workbook (.xlsx/.xls)."
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

        xl = _get_excel()
        if xl is None:
            return self._not_installed_result()

        try:
            wb = xl.Workbooks.Open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OPEN_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"file": str(file_path)})


# ---------------------------------------------------------------------- #
# Tool: excel_read_range
# ---------------------------------------------------------------------- #
class ExcelReadRangeTool(AppIntegrationTool):
    APP_KEY = "excel"
    CONFIG_SECTION = "integrations.office"

    name = "excel_read_range"
    description = "Read a cell range from the active Excel workbook."
    parameters = {
        "type": "object",
        "properties": {
            "sheet_name": {"type": "string"},
            "range_address": {"type": "string"},
        },
        "required": ["range_address"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        range_address = str(kwargs.get("range_address", "")).strip()
        if not range_address:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "range_address required"},
            )

        sheet_name = kwargs.get("sheet_name")

        xl = _get_excel()
        if xl is None:
            return self._not_installed_result()

        try:
            wb = xl.ActiveWorkbook
            ws = wb.Worksheets(str(sheet_name)) if sheet_name else wb.ActiveSheet
            rng = ws.Range(range_address)
            values = rng.Value
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "READ_FAILED", "message": str(exc)},
            )

        # Normalize tuple-of-tuples into list-of-lists (JSON friendly)
        rows: List[List[Any]] = []
        if isinstance(values, tuple):
            for row in values:
                if isinstance(row, tuple):
                    rows.append(list(row))
                else:
                    rows.append([row])
        else:
            rows = [[values]]

        return ToolResult(
            success=True,
            tool=self.name,
            data={"values": rows, "range": range_address},
        )


# ---------------------------------------------------------------------- #
# Tool: excel_write_range
# ---------------------------------------------------------------------- #
class ExcelWriteRangeTool(AppIntegrationTool):
    APP_KEY = "excel"
    CONFIG_SECTION = "integrations.office"

    name = "excel_write_range"
    description = "Write a 2D array of values into an Excel range."
    parameters = {
        "type": "object",
        "properties": {
            "sheet_name": {"type": "string"},
            "start_cell": {"type": "string"},
            "values": {
                "type": "array",
                "items": {"type": "array"},
            },
        },
        "required": ["start_cell", "values"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        start_cell = str(kwargs.get("start_cell", "")).strip()
        values = kwargs.get("values") or []
        if not start_cell or not isinstance(values, list):
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "start_cell + values required"},
            )

        sheet_name = kwargs.get("sheet_name")

        xl = _get_excel()
        if xl is None:
            return self._not_installed_result()

        try:
            wb = xl.ActiveWorkbook
            ws = wb.Worksheets(str(sheet_name)) if sheet_name else wb.ActiveSheet
            start = ws.Range(start_cell)
            for r, row in enumerate(values):
                for c, val in enumerate(row):
                    ws.Cells(start.Row + r, start.Column + c).Value = val
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "WRITE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"rows_written": len(values), "start_cell": start_cell},
        )


# ---------------------------------------------------------------------- #
# Tool: excel_run_macro
# ---------------------------------------------------------------------- #
class ExcelRunMacroTool(AppIntegrationTool):
    APP_KEY = "excel"
    CONFIG_SECTION = "integrations.office"

    name = "excel_run_macro"
    description = "Run a VBA macro in the active workbook."
    parameters = {
        "type": "object",
        "properties": {"macro_name": {"type": "string"}},
        "required": ["macro_name"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        macro_name = str(kwargs.get("macro_name", "")).strip()
        if not macro_name:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "macro_name required"},
            )

        xl = _get_excel()
        if xl is None:
            return self._not_installed_result()

        try:
            xl.Run(macro_name)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "MACRO_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"macro": macro_name},
        )