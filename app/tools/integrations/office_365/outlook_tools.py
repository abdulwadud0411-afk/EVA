"""
Microsoft Outlook integration (Office 365).

COM automation via pywin32. Requires Outlook installed and configured.
Sending emails requires explicit user confirmation (HIGH risk).
"""
from __future__ import annotations

from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _get_outlook():
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error("pywin32_not_available", error=str(exc))
        return None

    try:
        return win32com.client.Dispatch("Outlook.Application")
    except Exception as exc:  # noqa: BLE001
        logger.error("outlook_com_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: outlook_list_inbox
# ---------------------------------------------------------------------- #
class OutlookListInboxTool(AppIntegrationTool):
    APP_KEY = "outlook"
    CONFIG_SECTION = "integrations.office"

    name = "outlook_list_inbox"
    description = "List recent emails from Outlook's Inbox."
    parameters = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            limit = int(kwargs.get("limit") or 20)
        except (TypeError, ValueError):
            limit = 20
        if limit <= 0 or limit > 200:
            limit = 20

        outlook = _get_outlook()
        if outlook is None:
            return self._not_installed_result()

        try:
            ns = outlook.GetNamespace("MAPI")
            inbox = ns.GetDefaultFolder(6)  # olFolderInbox
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
            messages: List[dict] = []
            for i, item in enumerate(items):
                if i >= limit:
                    break
                messages.append({
                    "subject": getattr(item, "Subject", None),
                    "sender": getattr(item, "SenderName", None),
                    "received": str(getattr(item, "ReceivedTime", "")),
                    "unread": bool(getattr(item, "UnRead", False)),
                })
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OUTLOOK_READ_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"count": len(messages), "messages": messages},
        )


# ---------------------------------------------------------------------- #
# Tool: outlook_send_email
# ---------------------------------------------------------------------- #
class OutlookSendEmailTool(AppIntegrationTool):
    APP_KEY = "outlook"
    CONFIG_SECTION = "integrations.office"

    name = "outlook_send_email"
    description = "Compose and send an email via Outlook."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        to = str(kwargs.get("to") or "").strip()
        subject = str(kwargs.get("subject") or "").strip()
        body = str(kwargs.get("body") or "")
        cc = str(kwargs.get("cc") or "").strip()

        if not to or not subject:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "to + subject required"},
            )

        outlook = _get_outlook()
        if outlook is None:
            return self._not_installed_result()

        try:
            mail = outlook.CreateItem(0)  # olMailItem
            mail.To = to
            if cc:
                mail.CC = cc
            mail.Subject = subject
            mail.Body = body
            mail.Send()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SEND_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"to": to, "subject": subject, "sent": True},
        )


# ---------------------------------------------------------------------- #
# Tool: outlook_list_calendar
# ---------------------------------------------------------------------- #
class OutlookListCalendarTool(AppIntegrationTool):
    APP_KEY = "outlook"
    CONFIG_SECTION = "integrations.office"

    name = "outlook_list_calendar"
    description = "List upcoming calendar events from Outlook."
    parameters = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            limit = int(kwargs.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        if limit <= 0 or limit > 100:
            limit = 10

        outlook = _get_outlook()
        if outlook is None:
            return self._not_installed_result()

        try:
            ns = outlook.GetNamespace("MAPI")
            cal = ns.GetDefaultFolder(9)  # olFolderCalendar
            items = cal.Items
            items.Sort("[Start]")
            items.IncludeRecurrences = True
            events: List[dict] = []
            for i, item in enumerate(items):
                if i >= limit:
                    break
                events.append({
                    "subject": getattr(item, "Subject", None),
                    "start": str(getattr(item, "Start", "")),
                    "end": str(getattr(item, "End", "")),
                    "location": getattr(item, "Location", None),
                })
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CALENDAR_READ_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"count": len(events), "events": events},
        )