"""
EVA Tool System.

Every computer-control action is exposed as a Tool through the
ToolRegistry. The agent only *requests* tools; the runtime validates
and executes them.

Groups:
    Phase 2   - Application control
    Phase 3   - Window management
    Phase 4   - Keyboard + mouse
    Phase 5   - Screen + clipboard + media
    Phase 6   - Vision
    Phase 7   - Browser automation
    Integ.    - Third-party apps (Blender, Adobe, Office, Dev tools, ...)
"""
from app.tools.registry import ToolRegistry

# Core tools
from app.tools.app_tools import (
    OpenApplicationTool,
    CloseApplicationTool,
    ListRunningApplicationsTool,
)
from app.tools.window_tools import (
    ListWindowsTool,
    GetActiveWindowTool,
    FocusWindowTool,
    MinimizeWindowTool,
    MaximizeWindowTool,
    RestoreWindowTool,
    CloseWindowTool,
    MoveWindowTool,
    ResizeWindowTool,
)
from app.tools.keyboard_tools import (
    PressKeyTool,
    HotkeyTool,
    TypeTextTool,
    KeyDownTool,
    KeyUpTool,
)
from app.tools.mouse_tools import (
    MoveMouseTool,
    ClickTool,
    DoubleClickTool,
    RightClickTool,
    ScrollTool,
)
from app.tools.screen_tools import (
    TakeScreenshotTool,
    GetScreenSizeTool,
    GetActiveWindowScreenshotTool,
    CropScreenshotTool,
)
from app.tools.clipboard_tools import (
    GetClipboardTextTool,
    SetClipboardTextTool,
    ClearClipboardTool,
    GetClipboardInfoTool,
)
from app.tools.media_tools import (
    VolumeUpTool,
    VolumeDownTool,
    MuteTool,
    MediaControlTool,
)
from app.tools.vision_tools import (
    AnalyzeScreenTool,
    FindUiElementTool,
)
from app.tools.browser_tools import (
    BrowserOpenTool,
    BrowserCloseTool,
    OpenUrlTool,
    NewTabTool,
    CloseTabTool,
    GetPageTitleTool,
    GetPageTextTool,
    ClickElementTool,
    TypeIntoElementTool,
    SearchWebTool,
    ScrollPageTool,
    DownloadFileTool,
)


# ---------------------------------------------------------------------- #
# Core tool registration (Phase 2-7)
# ---------------------------------------------------------------------- #
def register_phase2_tools() -> None:
    ToolRegistry.register_class(OpenApplicationTool)
    ToolRegistry.register_class(CloseApplicationTool)
    ToolRegistry.register_class(ListRunningApplicationsTool)


def register_phase3_tools() -> None:
    ToolRegistry.register_class(ListWindowsTool)
    ToolRegistry.register_class(GetActiveWindowTool)
    ToolRegistry.register_class(FocusWindowTool)
    ToolRegistry.register_class(MinimizeWindowTool)
    ToolRegistry.register_class(MaximizeWindowTool)
    ToolRegistry.register_class(RestoreWindowTool)
    ToolRegistry.register_class(CloseWindowTool)
    ToolRegistry.register_class(MoveWindowTool)
    ToolRegistry.register_class(ResizeWindowTool)


def register_phase4_tools() -> None:
    ToolRegistry.register_class(PressKeyTool)
    ToolRegistry.register_class(HotkeyTool)
    ToolRegistry.register_class(TypeTextTool)
    ToolRegistry.register_class(KeyDownTool)
    ToolRegistry.register_class(KeyUpTool)
    ToolRegistry.register_class(MoveMouseTool)
    ToolRegistry.register_class(ClickTool)
    ToolRegistry.register_class(DoubleClickTool)
    ToolRegistry.register_class(RightClickTool)
    ToolRegistry.register_class(ScrollTool)


def register_phase5_tools() -> None:
    ToolRegistry.register_class(TakeScreenshotTool)
    ToolRegistry.register_class(GetScreenSizeTool)
    ToolRegistry.register_class(GetActiveWindowScreenshotTool)
    ToolRegistry.register_class(CropScreenshotTool)
    ToolRegistry.register_class(GetClipboardTextTool)
    ToolRegistry.register_class(SetClipboardTextTool)
    ToolRegistry.register_class(ClearClipboardTool)
    ToolRegistry.register_class(GetClipboardInfoTool)
    ToolRegistry.register_class(VolumeUpTool)
    ToolRegistry.register_class(VolumeDownTool)
    ToolRegistry.register_class(MuteTool)
    ToolRegistry.register_class(MediaControlTool)


def register_phase6_tools() -> None:
    ToolRegistry.register_class(AnalyzeScreenTool)
    ToolRegistry.register_class(FindUiElementTool)


def register_phase7_tools() -> None:
    ToolRegistry.register_class(BrowserOpenTool)
    ToolRegistry.register_class(BrowserCloseTool)
    ToolRegistry.register_class(OpenUrlTool)
    ToolRegistry.register_class(NewTabTool)
    ToolRegistry.register_class(CloseTabTool)
    ToolRegistry.register_class(GetPageTitleTool)
    ToolRegistry.register_class(GetPageTextTool)
    ToolRegistry.register_class(ClickElementTool)
    ToolRegistry.register_class(TypeIntoElementTool)
    ToolRegistry.register_class(SearchWebTool)
    ToolRegistry.register_class(ScrollPageTool)
    ToolRegistry.register_class(DownloadFileTool)


def register_core_tools() -> None:
    register_phase2_tools()
    register_phase3_tools()
    register_phase4_tools()
    register_phase5_tools()
    register_phase6_tools()
    register_phase7_tools()


# ---------------------------------------------------------------------- #
# Integration tools (app/tools/integrations/)
# ---------------------------------------------------------------------- #
def register_integration_tools() -> None:
    """
    Import the integrations package — sub-packages register their own
    tools on import. Failures in one group do not affect the others.
    """
    try:
        import app.tools.integrations  # noqa: F401
    except Exception:
        # Do not crash the core tool system if an optional integration
        # fails to import (e.g., missing optional dependency).
        pass


# ---------------------------------------------------------------------- #
# Auto-register on import
# ---------------------------------------------------------------------- #
register_core_tools()
register_integration_tools()