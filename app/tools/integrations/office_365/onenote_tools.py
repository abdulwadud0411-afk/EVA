"""
Microsoft OneNote integration (Office 365).

COM automation via pywin32. Requires the desktop OneNote app.
"""
from __future__ import annotations

from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _get_onenote():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.Dispatch("OneNote.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("onenote_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: onenote_list_notebooks
# ---------------------------------------------------------------------- #
class OneNoteListNotebooksTool(AppIntegrationTool):
    APP_KEY = "onenote"
    CONFIG_SECTION = "integrations.office"

    name = "onenote_list_notebooks"
    description = "List notebooks, sections, and page IDs from OneNote."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        onenote = _get_onenote()
        if onenote is None:
            return self._not_installed_result()

        try:
            import xml.etree.ElementTree as ET  # noqa: WPS433
            xml_str = onenote.GetHierarchy("", 4)  # hsPages=4
            root = ET.fromstring(xml_str)

            notebooks = []
            for nb in root.iter():
                tag = nb.tag.split("}")[-1]
                if tag == "Notebook":
                    notebooks.append({
                        "name": nb.attrib.get("name"),
                        "id": nb.attrib.get("ID"),
                    })
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "HIERARCHY_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"count": len(notebooks), "notebooks": notebooks},
        )


# ---------------------------------------------------------------------- #
# Tool: onenote_create_page
# ---------------------------------------------------------------------- #
class OneNoteCreatePageTool(AppIntegrationTool):
    APP_KEY = "onenote"
    CONFIG_SECTION = "integrations.office"

    name = "onenote_create_page"
    description = "Create a new OneNote page in the first section of the first notebook."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "html_body": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        title = str(kwargs.get("title") or "").strip()
        html_body = str(kwargs.get("html_body") or "")
        if not title:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "title required"},
            )

        onenote = _get_onenote()
        if onenote is None:
            return self._not_installed_result()

        try:
            # Find the first section id
            import xml.etree.ElementTree as ET  # noqa: WPS433
            xml_str = onenote.GetHierarchy("", 2)  # hsSections=2
            root = ET.fromstring(xml_str)
            section_id = None
            for el in root.iter():
                tag = el.tag.split("}")[-1]
                if tag == "Section":
                    section_id = el.attrib.get("ID")
                    break
            if not section_id:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "NO_SECTION", "message": "No OneNote section found."},
                )

            page_xml = f"""<?xml version="1.0"?>
<one:Page xmlns:one="http://schemas.microsoft.com/office/onenote/2013/onenote">
  <one:Title><one:OE><one:T>{title}</one:T></one:OE></one:Title>
  <one:Outline><one:OEChildren><one:OE><one:T>{html_body}</one:T></one:OE></one:OEChildren></one:Outline>
</one:Page>"""

            new_id = onenote.CreateNewPage(section_id, page_xml, 0)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PAGE_CREATE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"title": title, "page_id": new_id},
        )


# ---------------------------------------------------------------------- #
# Tool: onenote_append_to_page
# ---------------------------------------------------------------------- #
class OneNoteAppendToPageTool(AppIntegrationTool):
    APP_KEY = "onenote"
    CONFIG_SECTION = "integrations.office"

    name = "onenote_append_to_page"
    description = "Append text to an existing OneNote page by its page ID."
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["page_id", "text"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        page_id = str(kwargs.get("page_id") or "").strip()
        text = str(kwargs.get("text") or "")
        if not page_id or not text:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "page_id + text required"},
            )

        onenote = _get_onenote()
        if onenote is None:
            return self._not_installed_result()

        try:
            append_xml = f"""<?xml version="1.0"?>
<one:Page xmlns:one="http://schemas.microsoft.com/office/onenote/2013/onenote">
  <one:Outline><one:OEChildren><one:OE><one:T>{text}</one:T></one:OE></one:OEChildren></one:Outline>
</one:Page>"""
            onenote.UpdatePageContent(append_xml, min(0), True)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "APPEND_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"page_id": page_id, "appended": len(text)},
        )