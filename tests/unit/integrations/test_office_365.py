"""
Tests for app.tools.integrations.office_365.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tools.registry import ToolRegistry
from app.tools.integrations.office_365.word_tools import (
    WordOpenTool,
    WordCreateTool,
    WordInsertTextTool,
    WordExportPdfTool,
)
from app.tools.integrations.office_365.excel_tools import (
    ExcelOpenTool,
    ExcelReadRangeTool,
    ExcelWriteRangeTool,
    ExcelRunMacroTool,
)
from app.tools.integrations.office_365.powerpoint_tools import (
    PowerPointOpenTool,
    PowerPointAddSlideTool,
    PowerPointExportPdfTool,
)
from app.tools.integrations.office_365.outlook_tools import (
    OutlookListInboxTool,
    OutlookSendEmailTool,
    OutlookListCalendarTool,
)
from app.tools.integrations.office_365.onenote_tools import (
    OneNoteListNotebooksTool,
    OneNoteCreatePageTool,
    OneNoteAppendToPageTool,
)


def test_office_365_registered():
    names = set(ToolRegistry.list_tools())
    expected = {
        "word_open", "word_create", "word_insert_text", "word_export_pdf",
        "excel_open", "excel_read_range", "excel_write_range", "excel_run_macro",
        "powerpoint_open", "powerpoint_add_slide", "powerpoint_export_pdf",
        "outlook_list_inbox", "outlook_send_email", "outlook_list_calendar",
        "onenote_list_notebooks", "onenote_create_page", "onenote_append_to_page",
    }
    missing = expected - names
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------- #
# Word
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_word_open_missing_file(tmp_path):
    r = await WordOpenTool().run(file_path=str(tmp_path / "no.docx"))
    assert r.success is False


@pytest.mark.asyncio
async def test_word_open_no_com(tmp_path):
    f = tmp_path / "a.docx"
    f.write_bytes(b"fake")
    with patch("app.tools.integrations.office_365.word_tools._get_word",
               return_value=None):
        r = await WordOpenTool().run(file_path=str(f))
    assert r.success is False


@pytest.mark.asyncio
async def test_word_create_no_com(tmp_path):
    out = tmp_path / "out.docx"
    with patch("app.tools.integrations.office_365.word_tools._get_word",
               return_value=None):
        r = await WordCreateTool().run(output_path=str(out))
    assert r.success is False


@pytest.mark.asyncio
async def test_word_insert_text_empty():
    r = await WordInsertTextTool().run(text="")
    assert r.success is False


@pytest.mark.asyncio
async def test_word_export_pdf_no_com(tmp_path):
    out = tmp_path / "out.pdf"
    with patch("app.tools.integrations.office_365.word_tools._get_word",
               return_value=None):
        r = await WordExportPdfTool().run(output_path=str(out))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Excel
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_excel_open_missing_file(tmp_path):
    r = await ExcelOpenTool().run(file_path=str(tmp_path / "no.xlsx"))
    assert r.success is False


@pytest.mark.asyncio
async def test_excel_open_no_com(tmp_path):
    f = tmp_path / "a.xlsx"
    f.write_bytes(b"fake")
    with patch("app.tools.integrations.office_365.excel_tools._get_excel",
               return_value=None):
        r = await ExcelOpenTool().run(file_path=str(f))
    assert r.success is False


@pytest.mark.asyncio
async def test_excel_read_range_missing_args():
    r = await ExcelReadRangeTool().run(range_address="")
    assert r.success is False


@pytest.mark.asyncio
async def test_excel_write_range_missing_values():
    r = await ExcelWriteRangeTool().run(start_cell="A1", values=None)
    assert r.success is False


@pytest.mark.asyncio
async def test_excel_run_macro_missing_name():
    r = await ExcelRunMacroTool().run(macro_name="")
    assert r.success is False


# ---------------------------------------------------------------------- #
# PowerPoint
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_powerpoint_open_missing(tmp_path):
    r = await PowerPointOpenTool().run(file_path=str(tmp_path / "no.pptx"))
    assert r.success is False


@pytest.mark.asyncio
async def test_powerpoint_add_slide_missing_title():
    r = await PowerPointAddSlideTool().run(title="")
    assert r.success is False


@pytest.mark.asyncio
async def test_powerpoint_export_no_com(tmp_path):
    out = tmp_path / "out.pdf"
    with patch("app.tools.integrations.office_365.powerpoint_tools._get_powerpoint",
               return_value=None):
        r = await PowerPointExportPdfTool().run(output_path=str(out))
    assert r.success is False


# ---------------------------------------------------------------------- #
# Outlook
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_outlook_list_inbox_no_com():
    with patch("app.tools.integrations.office_365.outlook_tools._get_outlook",
               return_value=None):
        r = await OutlookListInboxTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_outlook_send_email_missing_args():
    r = await OutlookSendEmailTool().run(to="", subject="", body="")
    assert r.success is False


@pytest.mark.asyncio
async def test_outlook_list_calendar_no_com():
    with patch("app.tools.integrations.office_365.outlook_tools._get_outlook",
               return_value=None):
        r = await OutlookListCalendarTool().run()
    assert r.success is False


# ---------------------------------------------------------------------- #
# OneNote
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_onenote_list_notebooks_no_com():
    with patch("app.tools.integrations.office_365.onenote_tools._get_onenote",
               return_value=None):
        r = await OneNoteListNotebooksTool().run()
    assert r.success is False


@pytest.mark.asyncio
async def test_onenote_create_page_missing_title():
    r = await OneNoteCreatePageTool().run(title="")
    assert r.success is False


@pytest.mark.asyncio
async def test_onenote_append_missing_args():
    r = await OneNoteAppendToPageTool().run(page_id="", text="")
    assert r.success is False