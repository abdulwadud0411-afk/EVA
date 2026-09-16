"""
Integrations Layer — registers every application integration tool
with the central ToolRegistry.

Sub-modules register their tools at import time. This file simply
imports them in dependency order.

Groups:
    - common         : ffmpeg, export, project helpers
    - creative_3d    : Blender, Unreal, Cinema 4D, ComfyUI
    - adobe_cc       : Photoshop, Illustrator, Premiere, After Effects
    - design_social  : Figma, CapCut
    - design_cad     : AutoCAD, Fusion 360, SketchUp
    - media_extended : DaVinci Resolve, OBS Studio
    - office_365     : Word, Excel, PowerPoint, Outlook, OneNote
    - dev_tools      : VS Code, VS, Android Studio, Unity, Flutter, ...
    - utilities      : Git, Docker, Archive
    - social_media   : Spotify, Telegram, Discord, Zoom, WhatsApp, ...
"""
from __future__ import annotations

from app.core.logger import get_logger

logger = get_logger(__name__)


_REGISTERED_GROUPS = []


def _try_import(module_path: str, group_name: str) -> None:
    try:
        __import__(module_path, fromlist=["_"])
        _REGISTERED_GROUPS.append(group_name)
        logger.info("integration_group_registered", group=group_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "integration_group_failed",
            group=group_name,
            error=str(exc),
        )


# Common helpers first (used by other groups)
_try_import("app.tools.integrations.common", "common")

# Application-specific groups
_try_import("app.tools.integrations.creative_3d", "creative_3d")
_try_import("app.tools.integrations.adobe_cc", "adobe_cc")
_try_import("app.tools.integrations.design_social", "design_social")
_try_import("app.tools.integrations.design_cad", "design_cad")
_try_import("app.tools.integrations.media_extended", "media_extended")
_try_import("app.tools.integrations.office_365", "office_365")
_try_import("app.tools.integrations.dev_tools", "dev_tools")
_try_import("app.tools.integrations.utilities", "utilities")
_try_import("app.tools.integrations.social_media", "social_media")


def list_registered_groups() -> list:
    return list(_REGISTERED_GROUPS)