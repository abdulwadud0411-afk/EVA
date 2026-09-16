"""
Developer Tools integrations.

Covers: VS Code, Visual Studio, Android Studio, Xcode, Unity,
WebStorm, Flutter, React Native, XAMPP/WAMP, Python environments.

Registers tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.dev_tools.vscode_tools import (
    VSCodeOpenTool,
    VSCodeOpenFolderTool,
    VSCodeInstallExtensionTool,
    VSCodeRunCommandTool,
)
from app.tools.integrations.dev_tools.visual_studio_tools import (
    VisualStudioOpenSolutionTool,
    VisualStudioBuildTool,
)
from app.tools.integrations.dev_tools.android_studio_tools import (
    AndroidStudioOpenProjectTool,
    AndroidStudioRunGradleTool,
)
from app.tools.integrations.dev_tools.xcode_tools import (
    XcodeOpenProjectTool,
    XcodeBuildTool,
)
from app.tools.integrations.dev_tools.unity_tools import (
    UnityOpenProjectTool,
    UnityRunBatchMethodTool,
)
from app.tools.integrations.dev_tools.webstorm_tools import (
    WebStormOpenProjectTool,
)
from app.tools.integrations.dev_tools.flutter_tools import (
    FlutterCreateProjectTool,
    FlutterRunTool,
    FlutterBuildTool,
)
from app.tools.integrations.dev_tools.react_native_tools import (
    ReactNativeInitTool,
    ReactNativeRunAndroidTool,
    ReactNativeRunIosTool,
)
from app.tools.integrations.dev_tools.server_stack_tools import (
    XamppStartTool,
    XamppStopTool,
    WampStartTool,
    WampStopTool,
)
from app.tools.integrations.dev_tools.python_env_tools import (
    PythonCreateVenvTool,
    PythonPipInstallTool,
    PythonRunScriptTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # VS Code
    VSCodeOpenTool,
    VSCodeOpenFolderTool,
    VSCodeInstallExtensionTool,
    VSCodeRunCommandTool,
    # Visual Studio
    VisualStudioOpenSolutionTool,
    VisualStudioBuildTool,
    # Android Studio
    AndroidStudioOpenProjectTool,
    AndroidStudioRunGradleTool,
    # Xcode
    XcodeOpenProjectTool,
    XcodeBuildTool,
    # Unity
    UnityOpenProjectTool,
    UnityRunBatchMethodTool,
    # WebStorm
    WebStormOpenProjectTool,
    # Flutter
    FlutterCreateProjectTool,
    FlutterRunTool,
    FlutterBuildTool,
    # React Native
    ReactNativeInitTool,
    ReactNativeRunAndroidTool,
    ReactNativeRunIosTool,
    # Server stacks
    XamppStartTool,
    XamppStopTool,
    WampStartTool,
    WampStopTool,
    # Python
    PythonCreateVenvTool,
    PythonPipInstallTool,
    PythonRunScriptTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("dev_tools_registered", count=len(_TOOLS))