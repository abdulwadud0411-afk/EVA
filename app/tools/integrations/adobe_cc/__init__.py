"""
Adobe Creative Cloud integrations (Photoshop, Illustrator, Premiere, After Effects).

All tools use pywin32 COM automation against the user's legally
installed Adobe applications. No paid middleware is used.

Registers Adobe tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.adobe_cc.photoshop_tools import (
    PhotoshopOpenTool,
    PhotoshopRunActionTool,
    PhotoshopExportTool,
)
from app.tools.integrations.adobe_cc.illustrator_tools import (
    IllustratorOpenTool,
    IllustratorExportTool,
    IllustratorRunScriptTool,
)
from app.tools.integrations.adobe_cc.premiere_tools import (
    PremiereOpenProjectTool,
    PremiereImportMediaTool,
    PremiereExportTool,
)
from app.tools.integrations.adobe_cc.after_effects_tools import (
    AfterEffectsOpenProjectTool,
    AfterEffectsAddToRenderQueueTool,
    AfterEffectsRunScriptTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # Photoshop
    PhotoshopOpenTool,
    PhotoshopRunActionTool,
    PhotoshopExportTool,
    # Illustrator
    IllustratorOpenTool,
    IllustratorExportTool,
    IllustratorRunScriptTool,
    # Premiere
    PremiereOpenProjectTool,
    PremiereImportMediaTool,
    PremiereExportTool,
    # After Effects
    AfterEffectsOpenProjectTool,
    AfterEffectsAddToRenderQueueTool,
    AfterEffectsRunScriptTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("adobe_cc_tools_registered", count=len(_TOOLS))