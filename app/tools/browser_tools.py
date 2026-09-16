"""
Browser automation tools (Phase 7).

Tools:
    - browser_open           : launch the Playwright browser
    - browser_close          : close the browser
    - open_url               : navigate to a URL
    - new_tab                : open a new tab
    - close_tab              : close a tab
    - get_page_title         : get current page title
    - get_page_text          : get visible page text
    - click_element          : click an element by CSS selector
    - type_into_element      : type text into an input
    - search_web             : search DuckDuckGo
    - scroll_page            : scroll up/down
    - download_file          : download a file via a link

Uses Playwright with Chromium. Browser state is kept in a
process-wide singleton so multiple tool calls share the same session.
All URLs are validated (http/https only) before navigation.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Page,
        Playwright,
    )
    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # noqa: BLE001
    _PLAYWRIGHT_AVAILABLE = False
    Playwright = None  # type: ignore
    Browser = None  # type: ignore
    BrowserContext = None  # type: ignore
    Page = None  # type: ignore


# ---------------------------------------------------------------------- #
# Browser session singleton
# ---------------------------------------------------------------------- #
class _BrowserSession:
    """Holds the shared Playwright browser instance."""

    _playwright: Any = None
    _browser: Any = None
    _context: Any = None
    _page: Any = None
    _lock = asyncio.Lock()

    @classmethod
    async def ensure_started(cls, headless: bool = False) -> None:
        async with cls._lock:
            if cls._browser is not None and cls._browser.is_connected():
                return
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(headless=headless)
            cls._context = await cls._browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            cls._page = await cls._context.new_page()

    @classmethod
    async def get_page(cls) -> Any:
        if cls._page is None or cls._page.is_closed():
            if cls._context is None:
                raise RuntimeError("Browser context not initialised.")
            cls._page = await cls._context.new_page()
        return cls._page

    @classmethod
    async def new_tab(cls) -> Any:
        if cls._context is None:
            raise RuntimeError("Browser not started. Call browser_open first.")
        cls._page = await cls._context.new_page()
        return cls._page

    @classmethod
    async def close_current_tab(cls) -> None:
        if cls._page is not None and not cls._page.is_closed():
            await cls._page.close()
        cls._page = None

    @classmethod
    async def shutdown(cls) -> None:
        async with cls._lock:
            try:
                if cls._context is not None:
                    await cls._context.close()
                if cls._browser is not None:
                    await cls._browser.close()
                if cls._playwright is not None:
                    await cls._playwright.stop()
            except Exception:  # noqa: BLE001
                pass
            finally:
                cls._page = None
                cls._context = None
                cls._browser = None
                cls._playwright = None

    @classmethod
    def is_running(cls) -> bool:
        try:
            return cls._browser is not None and cls._browser.is_connected()
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _ensure_playwright(tool_name: str) -> Optional[ToolResult]:
    if not _PLAYWRIGHT_AVAILABLE:
        return ToolResult(
            success=False,
            tool=tool_name,
            error={
                "code": "PLATFORM_UNSUPPORTED",
                "message": "Playwright is not installed. Run: pip install playwright",
            },
        )
    return None


def _validate_url(url: str) -> Optional[str]:
    """Return an error string if the URL is not allowed."""
    if not url:
        return "URL is empty"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"URL scheme '{parsed.scheme}' is not allowed (only http/https)."
    if not parsed.netloc:
        return "URL has no host."
    return None


# ---------------------------------------------------------------------- #
# Tool: browser_open
# ---------------------------------------------------------------------- #
class BrowserOpenTool(Tool):
    name = "browser_open"
    description = (
        "Start the Playwright Chromium browser in headless mode "
        "(or headful if headless=false). Safe to call multiple times."
    )
    parameters = {
        "type": "object",
        "properties": {
            "headless": {
                "type": "boolean",
                "description": "Run browser without a visible window (default true).",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        headless = bool(kwargs.get("headless", False))
        try:
            await _BrowserSession.ensure_started(headless=headless)
        except Exception as exc:  # noqa: BLE001
            logger.error("browser_open_failed", error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "BROWSER_OPEN_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"headless": headless, "running": True},
        )


# ---------------------------------------------------------------------- #
# Tool: browser_close
# ---------------------------------------------------------------------- #
class BrowserCloseTool(Tool):
    name = "browser_close"
    description = "Close the Playwright browser and release resources."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err
        await _BrowserSession.shutdown()
        return ToolResult(success=True, tool=self.name, data={"running": False})


# ---------------------------------------------------------------------- #
# Tool: open_url
# ---------------------------------------------------------------------- #
class OpenUrlTool(Tool):
    name = "open_url"
    description = "Navigate the current tab to the given URL (http/https only)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        url = str(kwargs.get("url", "")).strip()
        problem = _validate_url(url)
        if problem:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_URL", "message": problem},
            )

        try:
            await _BrowserSession.ensure_started()
            page = await _BrowserSession.get_page()
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            title = await page.title()
        except Exception as exc:  # noqa: BLE001
            logger.error("open_url_failed", url=url, error=str(exc))
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "NAVIGATION_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"url": url, "title": title},
        )


# ---------------------------------------------------------------------- #
# Tool: new_tab
# ---------------------------------------------------------------------- #
class NewTabTool(Tool):
    name = "new_tab"
    description = "Open a new browser tab (optionally navigate to a URL)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        url = kwargs.get("url")
        if url:
            problem = _validate_url(str(url))
            if problem:
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "INVALID_URL", "message": problem},
                )

        try:
            await _BrowserSession.ensure_started()
            page = await _BrowserSession.new_tab()
            if url:
                await page.goto(str(url), timeout=30_000, wait_until="domcontentloaded")
                title = await page.title()
            else:
                title = await page.title()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "NEW_TAB_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"url": url, "title": title},
        )


# ---------------------------------------------------------------------- #
# Tool: close_tab
# ---------------------------------------------------------------------- #
class CloseTabTool(Tool):
    name = "close_tab"
    description = "Close the current tab."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        try:
            await _BrowserSession.close_current_tab()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CLOSE_TAB_FAILED", "message": str(exc)},
            )
        return ToolResult(success=True, tool=self.name, data={"closed": True})


# ---------------------------------------------------------------------- #
# Tool: get_page_title
# ---------------------------------------------------------------------- #
class GetPageTitleTool(Tool):
    name = "get_page_title"
    description = "Return the title of the current page."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        if not _BrowserSession.is_running():
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "BROWSER_NOT_RUNNING",
                    "message": "Browser is not running. Call browser_open first.",
                },
            )

        try:
            page = await _BrowserSession.get_page()
            title = await page.title()
            url = page.url
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TITLE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"title": title, "url": url},
        )


# ---------------------------------------------------------------------- #
# Tool: get_page_text
# ---------------------------------------------------------------------- #
class GetPageTextTool(Tool):
    name = "get_page_text"
    description = "Return the visible text content of the current page."
    parameters = {
        "type": "object",
        "properties": {
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default 5000).",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        if not _BrowserSession.is_running():
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "BROWSER_NOT_RUNNING",
                    "message": "Browser is not running. Call browser_open first.",
                },
            )

        try:
            max_chars = int(kwargs.get("max_chars", 5000))
        except (TypeError, ValueError):
            max_chars = 5000
        if max_chars <= 0 or max_chars > 100_000:
            max_chars = 5000

        try:
            page = await _BrowserSession.get_page()
            text = await page.evaluate("() => document.body ? document.body.innerText : ''")
            text = (text or "").strip()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TEXT_FAILED", "message": str(exc)},
            )

        truncated = text[:max_chars]
        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "text": truncated,
                "length": len(text),
                "truncated": len(text) > max_chars,
            },
        )


# ---------------------------------------------------------------------- #
# Tool: click_element
# ---------------------------------------------------------------------- #
class ClickElementTool(Tool):
    name = "click_element"
    description = "Click an element on the page identified by a CSS selector."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "timeout_ms": {"type": "integer"},
        },
        "required": ["selector"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        selector = str(kwargs.get("selector", "")).strip()
        if not selector:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "selector is required"},
            )

        try:
            timeout_ms = int(kwargs.get("timeout_ms", 10_000))
        except (TypeError, ValueError):
            timeout_ms = 10_000
        if timeout_ms <= 0 or timeout_ms > 120_000:
            timeout_ms = 10_000

        try:
            page = await _BrowserSession.get_page()
            await page.click(selector, timeout=timeout_ms)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "CLICK_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"selector": selector},
        )


# ---------------------------------------------------------------------- #
# Tool: type_into_element
# ---------------------------------------------------------------------- #
class TypeIntoElementTool(Tool):
    name = "type_into_element"
    description = "Type text into an input matched by a CSS selector."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "text": {"type": "string"},
            "clear_first": {"type": "boolean"},
            "press_enter": {"type": "boolean"},
        },
        "required": ["selector", "text"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        selector = str(kwargs.get("selector", "")).strip()
        text = kwargs.get("text")
        if not selector:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "selector is required"},
            )
        if text is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "text is required"},
            )
        text = str(text)

        clear_first = bool(kwargs.get("clear_first", True))
        press_enter = bool(kwargs.get("press_enter", False))

        try:
            page = await _BrowserSession.get_page()
            if clear_first:
                await page.fill(selector, "")
            await page.type(selector, text, delay=20)
            if press_enter:
                await page.press(selector, "Enter")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TYPE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"selector": selector, "length": len(text)},
        )


# ---------------------------------------------------------------------- #
# Tool: search_web
# ---------------------------------------------------------------------- #
class SearchWebTool(Tool):
    name = "search_web"
    description = (
        "Search the web using DuckDuckGo and return the results page URL. "
        "You can then call get_page_text to read the results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        query = str(kwargs.get("query", "")).strip()
        if not query:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "query is required"},
            )

        from urllib.parse import quote_plus
        url = f"https://duckduckgo.com/?q={quote_plus(query)}"

        try:
            await _BrowserSession.ensure_started()
            page = await _BrowserSession.get_page()
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            title = await page.title()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SEARCH_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"query": query, "url": url, "title": title},
        )


# ---------------------------------------------------------------------- #
# Tool: scroll_page
# ---------------------------------------------------------------------- #
class ScrollPageTool(Tool):
    name = "scroll_page"
    description = "Scroll the current page. Positive=down, negative=up."
    parameters = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Pixels to scroll (positive=down, negative=up).",
            },
        },
        "required": ["amount"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        try:
            amount = int(kwargs.get("amount", 0))
        except (TypeError, ValueError):
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "amount must be an integer"},
            )
        if amount == 0:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "amount must be non-zero"},
            )
        if abs(amount) > 100_000:
            amount = 100_000 if amount > 0 else -100_000

        try:
            page = await _BrowserSession.get_page()
            await page.evaluate(f"() => window.scrollBy(0, {amount})")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCROLL_FAILED", "message": str(exc)},
            )

        return ToolResult(success=True, tool=self.name, data={"amount": amount})


# ---------------------------------------------------------------------- #
# Tool: download_file
# ---------------------------------------------------------------------- #
class DownloadFileTool(Tool):
    name = "download_file"
    description = (
        "Download a file by navigating to a direct file URL. "
        "Saves to data/downloads/. Only http/https URLs allowed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = True

    async def run(self, **kwargs: Any) -> ToolResult:
        err = _ensure_playwright(self.name)
        if err is not None:
            return err

        url = str(kwargs.get("url", "")).strip()
        problem = _validate_url(url)
        if problem:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_URL", "message": problem},
            )

        download_dir = ConfigManager.get_data_dir() / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        try:
            await _BrowserSession.ensure_started()
            page = await _BrowserSession.get_page()
            async with page.expect_download(timeout=60_000) as download_info:
                await page.goto(url, timeout=30_000)
            download = await download_info.value
            target = download_dir / download.suggested_filename
            await download.save_as(str(target))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOWNLOAD_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"path": str(target), "url": url},
        )