"""
Utility integrations (Git, Docker, Archive tools).

Registers utility tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.utilities.git_tools import (
    GitCloneTool,
    GitStatusTool,
    GitCommitTool,
    GitPushTool,
    GitPullTool,
)
from app.tools.integrations.utilities.docker_tools import (
    DockerListContainersTool,
    DockerStartContainerTool,
    DockerStopContainerTool,
    DockerComposeUpTool,
    DockerComposeDownTool,
)
from app.tools.integrations.utilities.archive_tools import (
    ArchiveCompressTool,
    ArchiveExtractTool,
    ArchiveListTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # Git
    GitCloneTool,
    GitStatusTool,
    GitCommitTool,
    GitPushTool,
    GitPullTool,
    # Docker
    DockerListContainersTool,
    DockerStartContainerTool,
    DockerStopContainerTool,
    DockerComposeUpTool,
    DockerComposeDownTool,
    # Archive
    ArchiveCompressTool,
    ArchiveExtractTool,
    ArchiveListTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("utilities_tools_registered", count=len(_TOOLS))