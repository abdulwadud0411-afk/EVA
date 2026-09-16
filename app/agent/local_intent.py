"""
Local intent matcher (Optimization Patch).

Catches common, simple commands WITHOUT calling DeepSeek.
Saves ~70% of tokens by handling routine requests locally.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IntentResult:
    matched: bool
    intent: str = ""
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    direct_response: Optional[str] = None
    confidence: float = 0.0


_SITE_MAP = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "reddit": "https://www.reddit.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "whatsapp": "https://web.whatsapp.com",
    "chatgpt": "https://chat.openai.com",
    "deepseek": "https://chat.deepseek.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
}


def _site_to_url(site: str) -> str:
    return _SITE_MAP.get(site, f"https://www.{site}.com")


def _media_action(text: str) -> str:
    t = text.lower()
    if "next" in t:
        return "next"
    if "prev" in t:
        return "prev"
    if "stop" in t:
        return "stop"
    return "play_pause"


class LocalIntentMatcher:
    def __init__(self) -> None:
        self._patterns: List[tuple] = []
        self._build()

    def _build(self) -> None:
        self._patterns.append((
            "open_application",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:open|launch|start|run)\s+"
                r"(?P<app>notepad|calculator|calc|paint|cmd|powershell|"
                r"chrome|firefox|edge|brave|vscode|vs\s*code|"
                r"explorer|file\s+explorer|task\s*manager|taskmgr|"
                r"settings|control\s+panel|snipping\s+tool)"
                r"(?:\s+(?:app|application|browser|window))?$",
                re.IGNORECASE,
            ),
            "open_application",
            lambda m: {"application": m.group("app").strip().lower()},
        ))

        self._patterns.append((
            "open_url",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:open|go\s+to|visit|navigate\s+to)\s+"
                r"(?P<site>youtube|google|gmail|facebook|twitter|x|"
                r"instagram|reddit|github|stackoverflow|whatsapp|"
                r"chatgpt|deepseek|wikipedia|amazon|netflix)"
                r"(?:\s+(?:website|site|page|\.com))?$",
                re.IGNORECASE,
            ),
            "open_url",
            lambda m: {"url": _site_to_url(m.group("site").strip().lower())},
        ))

        self._patterns.append((
            "open_url",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:open|go\s+to|visit|navigate\s+to)\s+"
                r"(?P<url>https?://\S+)$",
                re.IGNORECASE,
            ),
            "open_url",
            lambda m: {"url": m.group("url").strip()},
        ))

        self._patterns.append((
            "volume_up",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:volume\s+up|increase\s+volume|turn\s+up|louder)$",
                re.IGNORECASE,
            ),
            "volume_up",
            lambda m: {},
        ))

        self._patterns.append((
            "volume_down",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:volume\s+down|decrease\s+volume|turn\s+down|quieter)$",
                re.IGNORECASE,
            ),
            "volume_down",
            lambda m: {},
        ))

        self._patterns.append((
            "mute",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:mute|unmute|toggle\s+mute|silence)$",
                re.IGNORECASE,
            ),
            "mute",
            lambda m: {},
        ))

        self._patterns.append((
            "take_screenshot",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:take\s+(?:a\s+)?screenshot|screenshot|capture\s+screen)$",
                re.IGNORECASE,
            ),
            "take_screenshot",
            lambda m: {},
        ))

        self._patterns.append((
            "media_control",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:play|pause|play\s+music|pause\s+music|"
                r"next\s+(?:track|song)|prev(?:ious)?\s+(?:track|song)|"
                r"stop\s+music)$",
                re.IGNORECASE,
            ),
            "media_control",
            lambda m: {"action": _media_action(m.group(0))},
        ))

        self._patterns.append((
            "get_active_window",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:what\s+(?:window\s+is\s+)?(?:active|focused)\??|"
                r"active\s+window\??|current\s+window\??)$",
                re.IGNORECASE,
            ),
            "get_active_window",
            lambda m: {},
        ))

        self._patterns.append((
            "list_windows",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:list\s+windows|show\s+windows|what\s+windows\s+are\s+open|"
                r"open\s+windows|running\s+windows)$",
                re.IGNORECASE,
            ),
            "list_windows",
            lambda m: {},
        ))

        self._patterns.append((
            "minimize_window",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?minimi[sz]e\s+(?P<title>.+)$",
                re.IGNORECASE,
            ),
            "minimize_window",
            lambda m: {"title": m.group("title").strip()},
        ))

        self._patterns.append((
            "maximize_window",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?maximi[sz]e\s+(?P<title>.+)$",
                re.IGNORECASE,
            ),
            "maximize_window",
            lambda m: {"title": m.group("title").strip()},
        ))

        self._patterns.append((
            "focus_window",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:focus|switch\s+to|bring\s+up)\s+(?P<title>.+)$",
                re.IGNORECASE,
            ),
            "focus_window",
            lambda m: {"title": m.group("title").strip()},
        ))

        self._patterns.append((
            "get_clipboard_text",
            re.compile(
                r"^(?:eva[, ]*)?(?:please\s+)?"
                r"(?:what(?:'s|\s+is)\s+in\s+(?:my\s+)?clipboard|"
                r"read\s+clipboard|show\s+clipboard|paste)$",
                re.IGNORECASE,
            ),
            "get_clipboard_text",
            lambda m: {},
        ))

        self._patterns.append((
            "greeting",
            re.compile(
                r"^(?:hi|hello|hey|হ্যালো|হাই|নমস্কার|assalamu\s+alaikum)"
                r"(?:\s+eva)?[!.?]?$",
                re.IGNORECASE,
            ),
            "",
            lambda m: {"response": "Hello! How can I help you?"},
        ))

        self._patterns.append((
            "how_are_you",
            re.compile(
                r"^(?:eva[, ]*)?(?:how\s+are\s+you|how\s+r\s+u|kemon\s+aso|"
                r"কেমন\s+আছো|কেমন\s+আছেন)[?!.]?$",
                re.IGNORECASE,
            ),
            "",
            lambda m: {"response": "I'm doing well, thank you! How can I help you?"},
        ))

    def match(self, user_input: str) -> IntentResult:
        text = (user_input or "").strip()
        if not text:
            return IntentResult(matched=False)

        for intent, pattern, tool_name, arg_builder in self._patterns:
            m = pattern.match(text)
            if not m:
                continue
            try:
                args = arg_builder(m) or {}
            except Exception:  # noqa: BLE001
                args = {}

            if tool_name == "" and "response" in args:
                return IntentResult(
                    matched=True,
                    intent=intent,
                    tool_name="",
                    arguments={},
                    direct_response=args["response"],
                    confidence=0.95,
                )
            return IntentResult(
                matched=True,
                intent=intent,
                tool_name=tool_name,
                arguments=args,
                confidence=0.9,
            )

        return IntentResult(matched=False)


_matcher: Optional[LocalIntentMatcher] = None


def get_matcher() -> LocalIntentMatcher:
    global _matcher
    if _matcher is None:
        _matcher = LocalIntentMatcher()
    return _matcher


def match_local(user_input: str) -> IntentResult:
    return get_matcher().match(user_input)