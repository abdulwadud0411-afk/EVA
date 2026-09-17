"""
EVA Main Window — JARVIS-style layout (Phase 22 redesign).

Layout:
    ┌──────────────────────────────────────────────────────┐
    │ [E] EVA ●Online    [🕐 clock]         [⚙ Settings]  │
    ├───────────┬──────────────────────┬───────────────────┤
    │ System    │                      │ Conversation      │
    │ Stats     │      EVA SPHERE      │ [Clear] [Extract] │
    │ ────      │                      │                   │
    │ EVA State │      E. V. A         │   messages…       │
    │ ────      │    ● Ready           │                   │
    │ Camera    │                      │                   │
    │ ────      │  [📷][🎤][📞][📸][⌨] │  [input] [➤]      │
    │ Uptime    │                      │                   │
    └───────────┴──────────────────────┴───────────────────┘

All colors / sphere / particle lines remain EVA purple theme.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.gui.controller import GUIController
from app.gui.gui_state import GUIState, GUIStatus
from app.gui.theme import PALETTE
from app.gui.widgets.call_button import CallButton
from app.gui.widgets.conversation_panel import ConversationPanel
from app.gui.widgets.stats_panel import LeftSidebar
from app.gui.widgets.vector_icons import (
    CameraIcon,
    KeyboardIcon,
    MicIcon,
    ScreenshotIcon,
)
from app.gui.widgets.voice_orb import VoiceOrb

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    _user_msg_sig = Signal(str)
    _assistant_msg_sig = Signal(str)
    _tool_event_sig = Signal(dict)
    _error_sig = Signal(str)
    _status_sig = Signal(object)
    _enable_input_sig = Signal(bool)

    def __init__(
        self,
        controller: Optional[GUIController] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller or GUIController()
        self.state: GUIState = self.controller.state

        self.setWindowTitle("EVA — Personal AI Desktop Assistant")
        self.setMinimumSize(1280, 760)
        self._apply_size()
        self._build_ui()
        self._wire()
        self._start_clock()

    def _apply_size(self) -> None:
        w = int(ConfigManager.get("gui.window.width", 1400))
        h = int(ConfigManager.get("gui.window.height", 900))
        self.resize(w, h)

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(12)

        # Left sidebar (stats cards)
        self.left_sidebar = LeftSidebar()
        body.addWidget(self.left_sidebar, 0)

        # Center (sphere + title + status + action buttons)
        center = QFrame()
        center.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(10, 10, 10, 10)
        cl.setSpacing(8)
        cl.addStretch(1)

        self.voice_orb = VoiceOrb()
        self.voice_orb.setMinimumHeight(400)
        cl.addWidget(self.voice_orb, 0, Qt.AlignCenter)

        self.center_title = QLabel("E.V.A")
        self.center_title.setAlignment(Qt.AlignCenter)
        self.center_title.setStyleSheet(
            f"color: {PALETTE.fg_primary}; font-size: 22px;"
            f"font-weight: 800; letter-spacing: 8px; background: transparent;"
        )
        cl.addWidget(self.center_title)

        badge_wrap = QHBoxLayout()
        badge_wrap.addStretch(1)
        self.status_badge = QLabel("● Ready")
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                color: {PALETTE.fg_secondary};
                background-color: {PALETTE.bg_tertiary};
                border: 1px solid {PALETTE.border};
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 11px;
            }}
        """)
        badge_wrap.addWidget(self.status_badge)
        badge_wrap.addStretch(1)
        cl.addLayout(badge_wrap)

        cl.addSpacing(8)

        # Action buttons row (custom vector icons — no emoji)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch(1)

        self.cam_btn = CameraIcon(size=52)
        self.cam_btn.setToolTip("Camera (not yet supported)")
        actions.addWidget(self.cam_btn)

        self.mic_btn = MicIcon(size=52)
        self.mic_btn.setToolTip("Push-to-talk / voice toggle")
        self.mic_btn.clicked.connect(self._on_mic_clicked)
        actions.addWidget(self.mic_btn)

        self.call_button = CallButton(diameter=52)
        actions.addWidget(self.call_button)

        self.screenshot_btn = ScreenshotIcon(size=52)
        self.screenshot_btn.setToolTip("Take screenshot")
        self.screenshot_btn.clicked.connect(self._on_screenshot)
        actions.addWidget(self.screenshot_btn)

        self.kb_btn = KeyboardIcon(size=52)
        self.kb_btn.setToolTip("Keyboard shortcuts")
        self.kb_btn.clicked.connect(self._show_keyboard_help)
        actions.addWidget(self.kb_btn)

        actions.addStretch(1)
        cl.addLayout(actions)

        cl.addStretch(1)
        body.addWidget(center, 1)

        # Right conversation panel
        self.conversation = ConversationPanel()
        body.addWidget(self.conversation, 0)

        root.addLayout(body, 1)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {PALETTE.bg_primary};
                border: 1px solid {PALETTE.border};
                border-radius: 12px;
            }}
        """)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        # Logo
        logo = QLabel()
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        logo_path = ConfigManager.get_project_root() / "assets" / "logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                logo.setPixmap(
                    pix.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText("E")
            logo.setStyleSheet(
                f"color: {PALETTE.accent}; font-size: 22px;"
                f"font-weight: 800; background: transparent;"
            )
        lay.addWidget(logo)

        title = QLabel("EVA")
        title.setStyleSheet(
            f"color: {PALETTE.fg_primary}; font-size: 16px;"
            f"font-weight: 800; letter-spacing: 3px; background: transparent;"
        )
        lay.addWidget(title)

        self.online_badge = QLabel("● Online")
        self.online_badge.setStyleSheet(f"""
            QLabel {{
                color: {PALETTE.success};
                background-color: rgba(16, 185, 129, 30);
                border-radius: 10px;
                padding: 3px 12px;
                font-size: 10px;
                font-weight: 600;
            }}
        """)
        lay.addWidget(self.online_badge)

        lay.addStretch(1)

        self.clock_lbl = QLabel("")
        self.clock_lbl.setStyleSheet(f"""
            QLabel {{
                color: {PALETTE.fg_primary};
                background-color: {PALETTE.bg_tertiary};
                border: 1px solid {PALETTE.border};
                border-radius: 14px;
                padding: 6px 20px;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        lay.addWidget(self.clock_lbl)

        lay.addStretch(1)

        self.settings_btn = QPushButton("⚙  Settings")
        self.settings_btn.setFixedHeight(34)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PALETTE.accent};
                color: white;
                border: none;
                border-radius: 17px;
                padding: 0 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {PALETTE.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {PALETTE.accent_pressed};
            }}
        """)
        self.settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(self.settings_btn)

        return header

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        self.conversation.message_submitted.connect(self._on_user_submit)
        self.call_button.toggled.connect(self._on_call_toggled)

        self._user_msg_sig.connect(self.conversation.add_user_message)
        self._assistant_msg_sig.connect(self.conversation.add_assistant_message)
        self._tool_event_sig.connect(self._on_tool_event_ui)
        self._error_sig.connect(self._on_error_ui)
        self._status_sig.connect(self._on_status_changed)
        self._enable_input_sig.connect(self.conversation.set_input_enabled)

        self.controller.on_user_message(lambda t: self._user_msg_sig.emit(t))
        self.controller.on_assistant_message(
            lambda t: self._assistant_msg_sig.emit(t)
        )
        self.controller.on_tool_event(lambda d: self._tool_event_sig.emit(d))
        self.controller.on_error(lambda m: self._error_sig.emit(m))
        self.state.subscribe(lambda old, new: self._status_sig.emit(new))

    def _start_clock(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    def _tick_clock(self) -> None:
        now = datetime.now()
        # No emoji inside strftime — Windows locale can't encode it.
        time_str = now.strftime("%I:%M:%S %p").lstrip("0")
        date_str = now.strftime("%B %d, %Y")
        self.clock_lbl.setText(f"{time_str}  |  {date_str}")

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #
    @Slot(str)
    def _on_user_submit(self, text: str) -> None:
        self.conversation.set_input_enabled(False)

        def _run() -> None:
            try:
                asyncio.run(self.controller.send_message(text))
            except Exception as exc:  # noqa: BLE001
                logger.error("gui_send_failed", error=str(exc))
                self._error_sig.emit(str(exc))
            finally:
                self._enable_input_sig.emit(True)

        threading.Thread(target=_run, daemon=True).start()

    @Slot(bool)
    def _on_call_toggled(self, active: bool) -> None:
        def _run() -> None:
            try:
                asyncio.run(self.controller.toggle_listening())
            except Exception as exc:  # noqa: BLE001
                logger.error("call_toggle_failed", error=str(exc))

        threading.Thread(target=_run, daemon=True).start()

    @Slot()
    def _on_mic_clicked(self) -> None:
        self.call_button.click()

    @Slot()
    def _on_screenshot(self) -> None:
        """Quick screenshot button."""
        try:
            from app.tools.screen_tools import capture_for_vision
            path = capture_for_vision()
            self.conversation.add_assistant_message(
                f"Screenshot saved: {path}"
            )
        except Exception as exc:  # noqa: BLE001
            self.conversation.add_assistant_message(f"[error] {exc}")

    @Slot()
    def _show_keyboard_help(self) -> None:
        self.conversation.add_assistant_message(
            "Keyboard shortcuts:\n"
            "  Enter    — send message\n"
            "  Ctrl+Q   — panic stop\n"
            "  Hey EVA  — wake (voice)"
        )

    @Slot(object)
    def _on_status_changed(self, status: GUIStatus) -> None:
        self.voice_orb.set_status(status)
        self.call_button.sync_status(status)

        text_map = {
            GUIStatus.IDLE: "● Ready",
            GUIStatus.LISTENING: "● Listening…",
            GUIStatus.THINKING: "● Thinking…",
            GUIStatus.SPEAKING: "● Speaking…",
            GUIStatus.ERROR: "● Error",
        }
        color_map = {
            GUIStatus.IDLE: PALETTE.fg_secondary,
            GUIStatus.LISTENING: PALETTE.listening,
            GUIStatus.THINKING: PALETTE.thinking,
            GUIStatus.SPEAKING: PALETTE.speaking,
            GUIStatus.ERROR: PALETTE.error,
        }
        self.status_badge.setText(text_map.get(status, "● Ready"))
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                color: {color_map.get(status, PALETTE.fg_secondary)};
                background-color: {PALETTE.bg_tertiary};
                border: 1px solid {PALETTE.border};
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 11px;
            }}
        """)

    @Slot(dict)
    def _on_tool_event_ui(self, payload: dict) -> None:
        logger.info(
            "gui_tool_event",
            event=payload.get("event"),
            tool=payload.get("name"),
        )

    @Slot(str)
    def _on_error_ui(self, message: str) -> None:
        self.conversation.add_assistant_message(f"[error] {message}")

    @Slot()
    def _open_settings(self) -> None:
        try:
            from app.gui.dialogs.settings_dialog import SettingsDialog
            dlg = SettingsDialog(self)
            dlg.exec()
            try:
                self.left_sidebar.eva_state._refresh()
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logger.error("open_settings_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        logger.info("gui_window_closed")
        super().closeEvent(event)