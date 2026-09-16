"""
Tests for Phase 7 browser tools.

Playwright is mocked via a fake page object so tests run offline.
The browser session is also reset between tests.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


@pytest.fixture
def mock_browser(monkeypatch):
    """Patch the browser session and Playwright availability."""
    import app.tools.browser_tools as bt

    fake_page = MagicMock()
    fake_page.is_closed = MagicMock(return_value=False)
    fake_page.title = AsyncMock(return_value="Test Page")
    fake_page.url = "https://example.com/"
    fake_page.goto = AsyncMock()
    fake_page.click = AsyncMock()
    fake_page.fill = AsyncMock()
    fake_page.type = AsyncMock()
    fake_page.press = AsyncMock()
    fake_page.evaluate = AsyncMock(return_value="Visible page text")

    fake_context = MagicMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)

    fake_browser = MagicMock()
    fake_browser.is_connected = MagicMock(return_value=True)

    monkeypatch.setattr(bt, "_PLAYWRIGHT_AVAILABLE", True)

    async def _ensure_started(headless: bool = True) -> None:
        bt._BrowserSession._page = fake_page
        bt._BrowserSession._context = fake_context
        bt._BrowserSession._browser = fake_browser

    monkeypatch.setattr(bt._BrowserSession, "ensure_started", staticmethod(_ensure_started))
    monkeypatch.setattr(bt._BrowserSession, "get_page", staticmethod(lambda: _get_page(fake_page)))
    monkeypatch.setattr(bt._BrowserSession, "new_tab", staticmethod(lambda: _new_tab(fake_page)))
    monkeypatch.setattr(bt._BrowserSession, "close_current_tab", staticmethod(lambda: _noop()))
    monkeypatch.setattr(bt._BrowserSession, "is_running", staticmethod(lambda: True))
    monkeypatch.setattr(bt._BrowserSession, "shutdown", staticmethod(lambda: _noop()))

    return bt, fake_page


async def _get_page(page):
    return page


async def _new_tab(page):
    return page


async def _noop():
    return None


# ---------------------------------------------------------------------- #
# browser_open / browser_close
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_browser_open(mock_browser):
    bt, _ = mock_browser
    result = await bt.BrowserOpenTool().run(headless=True)
    assert result.success is True
    assert result.data["running"] is True


@pytest.mark.asyncio
async def test_browser_close(mock_browser):
    bt, _ = mock_browser
    result = await bt.BrowserCloseTool().run()
    assert result.success is True


# ---------------------------------------------------------------------- #
# open_url
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_open_url_success(mock_browser):
    bt, page = mock_browser
    result = await bt.OpenUrlTool().run(url="https://example.com")
    assert result.success is True
    assert result.data["title"] == "Test Page"
    page.goto.assert_called_once()


@pytest.mark.asyncio
async def test_open_url_rejects_file_scheme(mock_browser):
    bt, _ = mock_browser
    result = await bt.OpenUrlTool().run(url="file:///C:/secret.txt")
    assert result.success is False
    assert result.error["code"] == "INVALID_URL"


@pytest.mark.asyncio
async def test_open_url_rejects_javascript(mock_browser):
    bt, _ = mock_browser
    result = await bt.OpenUrlTool().run(url="javascript:alert(1)")
    assert result.success is False
    assert result.error["code"] == "INVALID_URL"


@pytest.mark.asyncio
async def test_open_url_empty(mock_browser):
    bt, _ = mock_browser
    result = await bt.OpenUrlTool().run(url="")
    assert result.success is False
    assert result.error["code"] == "INVALID_URL"


# ---------------------------------------------------------------------- #
# new_tab / close_tab
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_new_tab_with_url(mock_browser):
    bt, page = mock_browser
    result = await bt.NewTabTool().run(url="https://example.com")
    assert result.success is True


@pytest.mark.asyncio
async def test_new_tab_bad_url(mock_browser):
    bt, _ = mock_browser
    result = await bt.NewTabTool().run(url="ftp://example.com")
    assert result.success is False
    assert result.error["code"] == "INVALID_URL"


@pytest.mark.asyncio
async def test_close_tab(mock_browser):
    bt, _ = mock_browser
    result = await bt.CloseTabTool().run()
    assert result.success is True


# ---------------------------------------------------------------------- #
# get_page_title / get_page_text
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_page_title(mock_browser):
    bt, _ = mock_browser
    result = await bt.GetPageTitleTool().run()
    assert result.success is True
    assert result.data["title"] == "Test Page"


@pytest.mark.asyncio
async def test_get_page_text(mock_browser):
    bt, _ = mock_browser
    result = await bt.GetPageTextTool().run()
    assert result.success is True
    assert "Visible page text" in result.data["text"]


@pytest.mark.asyncio
async def test_get_page_text_truncates(mock_browser, monkeypatch):
    bt, page = mock_browser
    page.evaluate = AsyncMock(return_value="x" * 10000)
    result = await bt.GetPageTextTool().run(max_chars=100)
    assert result.success is True
    assert len(result.data["text"]) == 100
    assert result.data["truncated"] is True


# ---------------------------------------------------------------------- #
# click_element
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_click_element(mock_browser):
    bt, page = mock_browser
    result = await bt.ClickElementTool().run(selector="#submit")
    assert result.success is True
    page.click.assert_called_once()


@pytest.mark.asyncio
async def test_click_element_missing_selector(mock_browser):
    bt, _ = mock_browser
    result = await bt.ClickElementTool().run()
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------- #
# type_into_element
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_type_into_element(mock_browser):
    bt, page = mock_browser
    result = await bt.TypeIntoElementTool().run(
        selector="#search", text="hello", press_enter=True
    )
    assert result.success is True
    page.type.assert_called_once()
    page.press.assert_called_once_with("#search", "Enter")


@pytest.mark.asyncio
async def test_type_into_element_missing_text(mock_browser):
    bt, _ = mock_browser
    result = await bt.TypeIntoElementTool().run(selector="#x")
    assert result.success is False


# ---------------------------------------------------------------------- #
# search_web
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_search_web(mock_browser):
    bt, page = mock_browser
    result = await bt.SearchWebTool().run(query="gta 6 trailer")
    assert result.success is True
    assert "duckduckgo.com" in result.data["url"]


@pytest.mark.asyncio
async def test_search_web_empty(mock_browser):
    bt, _ = mock_browser
    result = await bt.SearchWebTool().run(query="")
    assert result.success is False
    assert result.error["code"] == "INVALID_ARGUMENT"


# ---------------------------------------------------------------------- #
# scroll_page
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_scroll_page(mock_browser):
    bt, page = mock_browser
    result = await bt.ScrollPageTool().run(amount=500)
    assert result.success is True
    page.evaluate.assert_called_once()


@pytest.mark.asyncio
async def test_scroll_page_zero(mock_browser):
    bt, _ = mock_browser
    result = await bt.ScrollPageTool().run(amount=0)
    assert result.success is False


# ---------------------------------------------------------------------- #
# Platform guard
# ---------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_browser_platform_guard(monkeypatch):
    import app.tools.browser_tools as bt
    monkeypatch.setattr(bt, "_PLAYWRIGHT_AVAILABLE", False)
    result = await bt.BrowserOpenTool().run()
    assert result.success is False
    assert result.error["code"] == "PLATFORM_UNSUPPORTED"


# ---------------------------------------------------------------------- #
# Registration
# ---------------------------------------------------------------------- #
def test_all_phase7_tools_registered():
    import importlib
    import app.tools as tools_pkg
    importlib.reload(tools_pkg)

    names = set(ToolRegistry.list_tools())
    expected = {
        "browser_open", "browser_close", "open_url", "new_tab", "close_tab",
        "get_page_title", "get_page_text", "click_element",
        "type_into_element", "search_web", "scroll_page", "download_file",
    }
    missing = expected - names
    assert not missing, f"Missing Phase 7 tools: {missing}"