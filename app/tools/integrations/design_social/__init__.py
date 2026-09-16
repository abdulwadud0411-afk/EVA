"""
Design & Social integrations (Figma, CapCut).

Registers tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.design_social.figma_tools import (
    FigmaGetFileTool,
    FigmaGetNodeTool,
    FigmaExportImageTool,
    FigmaListProjectsTool,
)
from app.tools.integrations.design_social.capcut_tools import (
    CapCutOpenTool,
    CapCutImportMediaTool,
    CapCutClickTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # Figma
    FigmaGetFileTool,
    FigmaGetNodeTool,
    FigmaExportImageTool,
    FigmaListProjectsTool,
    # CapCut
    CapCutOpenTool,
    CapCutImportMediaTool,
    CapCutClickTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("design_social_tools_registered", count=len(_TOOLS))