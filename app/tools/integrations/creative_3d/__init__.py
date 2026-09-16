"""
Creative 3D integrations (Blender, Unreal, Cinema 4D, ComfyUI).

Registers all 3D/creative tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.creative_3d.blender_tools import (
    BlenderRunScriptTool,
    BlenderRenderTool,
    BlenderOpenFileTool,
)
from app.tools.integrations.creative_3d.unreal_tools import (
    UnrealPingTool,
    UnrealRunConsoleCommandTool,
    UnrealListActorsTool,
)
from app.tools.integrations.creative_3d.cinema4d_tools import (
    Cinema4DRunScriptTool,
    Cinema4DRenderTool,
)
from app.tools.integrations.creative_3d.comfyui_tools import (
    ComfyUIPingTool,
    ComfyUIListModelsTool,
    ComfyUIListWorkflowsTool,
    ComfyUIRunWorkflowTool,
    ComfyUIQueueStatusTool,
    ComfyUIGetOutputTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # Blender
    BlenderRunScriptTool,
    BlenderRenderTool,
    BlenderOpenFileTool,
    # Unreal
    UnrealPingTool,
    UnrealRunConsoleCommandTool,
    UnrealListActorsTool,
    # Cinema 4D
    Cinema4DRunScriptTool,
    Cinema4DRenderTool,
    # ComfyUI
    ComfyUIPingTool,
    ComfyUIListModelsTool,
    ComfyUIListWorkflowsTool,
    ComfyUIRunWorkflowTool,
    ComfyUIQueueStatusTool,
    ComfyUIGetOutputTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("creative_3d_tools_registered", count=len(_TOOLS))