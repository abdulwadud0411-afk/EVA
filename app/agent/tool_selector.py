"""
Dynamic tool selection (Optimization Patch).

Returns only the tool schemas likely relevant to the user's message.
Reduces token usage by ~70-80%.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

logger = get_logger(__name__)


_GROUPS: List[tuple] = [
    (
        re.compile(
            r"\b(open|launch|start|run|close|kill|quit|notepad|chrome|"
            r"firefox|edge|brave|vscode|calculator|calc|paint|cmd|"
            r"powershell|explorer|task\s*manager|taskmgr|settings|"
            r"control\s+panel|snipping\s+tool|app|application|program)\b",
            re.IGNORECASE,
        ),
        {"open_application", "close_application", "list_running_applications"},
    ),
    (
        re.compile(
            r"\b(youtube|google|gmail|facebook|twitter|instagram|reddit|"
            r"github|stackoverflow|whatsapp|wikipedia|amazon|netflix|"
            r"browser|search|web|url|website|webpage|http|https|"
            r"duckduckgo|navigate|link|tab|click|type\s+in)\b",
            re.IGNORECASE,
        ),
        {
            "browser_open", "browser_close", "open_url", "new_tab",
            "close_tab", "get_page_title", "get_page_text",
            "click_element", "type_into_element", "search_web",
            "scroll_page", "download_file",
        },
    ),
    (
        re.compile(
            r"\b(window|minimi[sz]e|maximi[sz]e|restore|focus|resize|"
            r"move|active|switch\s+to|bring\s+up)\b",
            re.IGNORECASE,
        ),
        {
            "list_windows", "get_active_window", "focus_window",
            "minimize_window", "maximize_window", "restore_window",
            "close_window", "move_window", "resize_window",
        },
    ),
    (
        re.compile(
            r"\b(type|press|key|hotkey|ctrl|alt|shift|enter|tab|"
            r"escape|keyboard)\b",
            re.IGNORECASE,
        ),
        {"press_key", "hotkey", "type_text", "key_down", "key_up"},
    ),
    (
        re.compile(
            r"\b(click|mouse|cursor|move\s+mouse|scroll|double\s+click|"
            r"right\s+click)\b",
            re.IGNORECASE,
        ),
        {"move_mouse", "click", "double_click", "right_click", "scroll"},
    ),
    (
        re.compile(
            r"\b(screenshot|screen\s+shot|capture|screen|resolution|"
            r"display|crop)\b",
            re.IGNORECASE,
        ),
        {
            "take_screenshot", "get_screen_size",
            "get_active_window_screenshot", "crop_screenshot",
        },
    ),
    (
        re.compile(
            r"\b(clipboard|copy|paste|cut)\b",
            re.IGNORECASE,
        ),
        {
            "get_clipboard_text", "set_clipboard_text",
            "clear_clipboard", "get_clipboard_info",
        },
    ),
    (
        re.compile(
            r"\b(volume|mute|unmute|sound|audio|play|pause|next\s+track|"
            r"previous\s+track|song|music|media)\b",
            re.IGNORECASE,
        ),
        {"volume_up", "volume_down", "mute", "media_control"},
    ),
    (
        re.compile(
            r"\b(look\s+at|see\s+my\s+screen|analyze\s+screen|vision|"
            r"what(?:'s|\s+is)\s+on\s+my\s+screen|find\s+(?:the|a))\b",
            re.IGNORECASE,
        ),
        {"analyze_screen", "find_ui_element"},
    ),
]


_ALWAYS_INCLUDE: Set[str] = set()


class ToolSelector:
    def select_schemas(self, user_input: str) -> List[Dict]:
        text = user_input or ""
        selected: Set[str] = set(_ALWAYS_INCLUDE)
        matched_any = False

        for pattern, tools in _GROUPS:
            if pattern.search(text):
                selected.update(tools)
                matched_any = True

        all_names = set(ToolRegistry.list_tools())

        if not matched_any or not selected:
            logger.info("tool_selector_fallback_all")
            return ToolRegistry.all_schemas()

        selected = selected & all_names
        if not selected:
            return ToolRegistry.all_schemas()

        schemas: List[Dict] = []
        for name in selected:
            tool = ToolRegistry.get(name)
            if tool is not None:
                schemas.append(tool.schema())

        logger.info(
            "tool_selector_selected",
            count=len(schemas),
            names=sorted(selected),
        )
        return schemas


_selector: Optional[ToolSelector] = None


def get_selector() -> ToolSelector:
    global _selector
    if _selector is None:
        _selector = ToolSelector()
    return _selector


def select_tool_schemas(user_input: str) -> List[Dict]:
    return get_selector().select_schemas(user_input)