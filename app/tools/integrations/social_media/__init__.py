"""
Social & Media integrations.

Registers social tool classes with the ToolRegistry at import time.
"""
from app.core.logger import get_logger
from app.tools.registry import ToolRegistry

from app.tools.integrations.social_media.spotify_tools import (
    SpotifyPlayPauseTool,
    SpotifyNextTool,
    SpotifyPreviousTool,
    SpotifyPlayTrackTool,
)
from app.tools.integrations.social_media.youtube_music_tools import (
    YouTubeMusicSearchTool,
    YouTubeMusicPlayTool,
)
from app.tools.integrations.social_media.telegram_tools import (
    TelegramOpenChatTool,
    TelegramSendMessageTool,
)
from app.tools.integrations.social_media.discord_tools import (
    DiscordOpenChannelTool,
    DiscordSendMessageTool,
)
from app.tools.integrations.social_media.zoom_tools import (
    ZoomStartMeetingTool,
    ZoomJoinMeetingTool,
)
from app.tools.integrations.social_media.whatsapp_tools import (
    WhatsAppOpenChatTool,
    WhatsAppSendMessageTool,
)
from app.tools.integrations.social_media.facebook_tools import (
    FacebookOpenMessengerTool,
    FacebookSendMessageTool,
)
from app.tools.integrations.social_media.instagram_tools import (
    InstagramOpenTool,
    InstagramOpenProfileTool,
)

logger = get_logger(__name__)


_TOOLS = [
    # Spotify
    SpotifyPlayPauseTool,
    SpotifyNextTool,
    SpotifyPreviousTool,
    SpotifyPlayTrackTool,
    # YouTube Music
    YouTubeMusicSearchTool,
    YouTubeMusicPlayTool,
    # Telegram
    TelegramOpenChatTool,
    TelegramSendMessageTool,
    # Discord
    DiscordOpenChannelTool,
    DiscordSendMessageTool,
    # Zoom
    ZoomStartMeetingTool,
    ZoomJoinMeetingTool,
    # WhatsApp
    WhatsAppOpenChatTool,
    WhatsAppSendMessageTool,
    # Facebook
    FacebookOpenMessengerTool,
    FacebookSendMessageTool,
    # Instagram
    InstagramOpenTool,
    InstagramOpenProfileTool,
]


def register() -> None:
    for tool_cls in _TOOLS:
        ToolRegistry.register_class(tool_cls)


register()
logger.info("social_media_tools_registered", count=len(_TOOLS))