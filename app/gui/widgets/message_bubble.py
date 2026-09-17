"""
Chat message bubble (Phase 21).

A single message row: avatar + bubble + timestamp.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.theme import FONTS


class MessageBubble(QWidget):
    def __init__(
        self,
        text: str,
        role: str = "assistant",
        timestamp: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._role = role
        self._build_ui(text, timestamp)

    def _build_ui(self, text: str, timestamp: str) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(10)

        is_user = self._role == "user"

        # Avatar
        avatar = QLabel("R" if is_user else "E")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        if is_user:
            avatar.setStyleSheet(
                "background-color: #7c3aed; color: white;"
                "border-radius: 16px; font-weight: 700;"
            )
        else:
            avatar.setStyleSheet(
                "background-color: #22d3ee; color: #0f0b1e;"
                "border-radius: 16px; font-weight: 700;"
            )

        # Bubble
        bubble = QFrame()
        bubble.setObjectName("BubbleUser" if is_user else "BubbleAssistant")
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(4, 4, 4, 4)
        bubble_layout.setSpacing(4)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_label.setObjectName(
            "BubbleTextUser" if is_user else "BubbleTextAssistant"
        )
        text_label.setStyleSheet(
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_md}px;"
            "background: transparent;"
        )
        bubble_layout.addWidget(text_label)

        ts = timestamp or datetime.now().strftime("%H:%M")
        ts_label = QLabel(ts)
        ts_label.setObjectName("BubbleTimestamp")
        ts_label.setStyleSheet(
            f"color: #7a6f96; font-size: {FONTS.size_xs}px; background: transparent;"
        )
        if is_user:
            ts_label.setAlignment(Qt.AlignRight)
        else:
            ts_label.setAlignment(Qt.AlignLeft)
        bubble_layout.addWidget(ts_label)

        # Layout order
        if is_user:
            root.addStretch(1)
            root.addWidget(bubble)
            root.addWidget(avatar, 0, Qt.AlignTop)
        else:
            root.addWidget(avatar, 0, Qt.AlignTop)
            root.addWidget(bubble)
            root.addStretch(1)