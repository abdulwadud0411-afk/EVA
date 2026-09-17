"""
GUI widgets package (Phase 21 + 2.5A + 2.5B + 22).
"""
# Phase 21 — base widgets
from app.gui.widgets.logo_widget import LogoWidget  # noqa: F401
from app.gui.widgets.mic_indicator import MicIndicator  # noqa: F401
from app.gui.widgets.voice_animation import VoiceAnimation  # noqa: F401
from app.gui.widgets.message_bubble import MessageBubble  # noqa: F401
from app.gui.widgets.chat_panel import ChatPanel  # noqa: F401
from app.gui.widgets.call_button import CallButton  # noqa: F401

# Phase 2.5A — Voice Orb (LOCKED design)
from app.gui.widgets.glowing_sphere import GlowingSphere  # noqa: F401
from app.gui.widgets.particle_field import ParticleField  # noqa: F401
from app.gui.widgets.voice_orb import VoiceOrb  # noqa: F401

# Phase 2.5B — Dashboard panels
from app.gui.widgets.clock_widget import ClockWidget  # noqa: F401
from app.gui.widgets.system_monitor import (  # noqa: F401
    SystemMonitorPanel,
    GaugeWidget,
    color_for_percent,
)
from app.gui.widgets.info_panel import InfoPanel  # noqa: F401

# Phase 22 — JARVIS layout
from app.gui.widgets.stats_panel import (  # noqa: F401
    LeftSidebar,
    StatsCard,
    LabeledBar,
    SystemStatsCard,
    EvaStateCard,
    CameraCard,
    UptimeCard,
)
from app.gui.widgets.conversation_panel import ConversationPanel  # noqa: F401

# Phase 22 — Vector icons (replace emoji)
from app.gui.widgets.vector_icons import (  # noqa: F401
    CameraIcon,
    MicIcon,
    KeyboardIcon,
    ScreenshotIcon,
)

__all__ = [
    # Phase 21
    "LogoWidget", "MicIndicator", "VoiceAnimation",
    "MessageBubble", "ChatPanel", "CallButton",
    # Phase 2.5A
    "GlowingSphere", "ParticleField", "VoiceOrb",
    # Phase 2.5B
    "ClockWidget", "SystemMonitorPanel", "GaugeWidget",
    "color_for_percent", "InfoPanel",
    # Phase 22
    "LeftSidebar", "StatsCard", "LabeledBar",
    "SystemStatsCard", "EvaStateCard", "CameraCard", "UptimeCard",
    "ConversationPanel",
    "CameraIcon", "MicIcon", "KeyboardIcon", "ScreenshotIcon",
]