"""
Extended media integrations (DaVinci Resolve, OBS Studio, Audacity).

Registers tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.media_extended.davinci_resolve_tools import (
    DaVinciOpenProjectTool,
    DaVinciImportMediaTool,
    DaVinciRenderTool,
)
from app.tools.integrations.media_extended.obs_studio_tools import (
    OBSStartRecordingTool,
    OBSStopRecordingTool,
    OBSStartStreamingTool,
    OBSStopStreamingTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # DaVinci
    DaVinciOpenProjectTool,
    DaVinciImportMediaTool,
    DaVinciRenderTool,
    # OBS
    OBSStartRecordingTool,
    OBSStopRecordingTool,
    OBSStartStreamingTool,
    OBSStopStreamingTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("media_extended_tools_registered", count=len(_TOOLS))