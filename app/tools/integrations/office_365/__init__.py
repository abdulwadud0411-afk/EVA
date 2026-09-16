"""
Microsoft Office 365 integrations (Word, Excel, PowerPoint, Outlook, OneNote).

All tools use pywin32 COM automation against the user's legally
installed Microsoft Office applications. No paid middleware is used.

Registers Office tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
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

logger = get_logger(__name__)


_TOOLS = [
    # Word
    WordOpenTool,
    WordCreateTool,
    WordInsertTextTool,
    WordExportPdfTool,
    # Excel
    ExcelOpenTool,
    ExcelReadRangeTool,
    ExcelWriteRangeTool,
    ExcelRunMacroTool,
    # PowerPoint
    PowerPointOpenTool,
    PowerPointAddSlideTool,
    PowerPointExportPdfTool,
    # Outlook
    OutlookListInboxTool,
    OutlookSendEmailTool,
    OutlookListCalendarTool,
    # OneNote
    OneNoteListNotebooksTool,
    OneNoteCreatePageTool,
    OneNoteAppendToPageTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("office_365_tools_registered", count=len(_TOOLS))