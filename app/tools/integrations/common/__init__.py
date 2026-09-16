"""
Common integration helpers (ffmpeg, export, project templates).

These tools are used by other integrations but can also be called
directly by EVA. They cover tasks that apply across many apps.

Registers tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.common.media_processing_tools import (
    FfmpegConvertTool,
    FfmpegExtractAudioTool,
    FfmpegTrimTool,
    FfmpegConcatTool,
    FfmpegThumbnailTool,
)
from app.tools.integrations.common.export_tools import (
    BatchConvertTool,
    VerifyOutputTool,
)
from app.tools.integrations.common.project_tools import (
    CreateProjectFolderTool,
    DuplicateAsTemplateTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # Media (ffmpeg)
    FfmpegConvertTool,
    FfmpegExtractAudioTool,
    FfmpegTrimTool,
    FfmpegConcatTool,
    FfmpegThumbnailTool,
    # Export helpers
    BatchConvertTool,
    VerifyOutputTool,
    # Project helpers
    CreateProjectFolderTool,
    DuplicateAsTemplateTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("common_tools_registered", count=len(_TOOLS))