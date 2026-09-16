"""
Design & CAD integrations (AutoCAD, Fusion 360, SketchUp).

Registers CAD tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.design_cad.autocad_tools import (
    AutoCADOpenTool,
    AutoCADRunScriptTool,
    AutoCADExportPdfTool,
)
from app.tools.integrations.design_cad.fusion360_tools import (
    Fusion360OpenTool,
    Fusion360RunScriptTool,
)
from app.tools.integrations.design_cad.sketchup_tools import (
    SketchUpOpenTool,
    SketchUpExportTool,
)

logger = get_logger(__name__)


_TOOLS = [
    AutoCADOpenTool,
    AutoCADRunScriptTool,
    AutoCADExportPdfTool,
    Fusion360OpenTool,
    Fusion360RunScriptTool,
    SketchUpOpenTool,
    SketchUpExportTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("design_cad_tools_registered", count=len(_TOOLS))