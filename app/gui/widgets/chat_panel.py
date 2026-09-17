"""
Chat panel (Phase 21).

Scrollable list of MessageBubble widgets + input box + send button.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.gui.widgets.message_bubble import MessageBubble


class ChatPanel(QFrame):
    """Chat interface with input box and message list."""

    message_submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LeftPanel")
        self._max_messages = int(ConfigManager.get("gui.chat.max_messages", 500))
        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Scroll area (message list)
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("ChatScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._container = QWidget()
        self._container.setObjectName("ChatContainer")
        self._messages_layout = QVBoxLayout(self._container)
        self._messages_layout.setContentsMargins(4, 4, 4, 4)
        self._messages_layout.setSpacing(2)
        self._messages_layout.addStretch(1)

        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        # Input row
        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QLineEdit(self)
        self._input.setObjectName("ChatInput")
        self._input.setPlaceholderText("Ask EVA anything…")
        self._input.returnPressed.connect(self._submit)

        self._send = QPushButton("Send", self)
        self._send.setObjectName("PrimaryButton")
        self._send.setFixedWidth(80)
        self._send.clicked.connect(self._submit)

        row.addWidget(self._input, 1)
        row.addWidget(self._send, 0)

        root.addLayout(row)

        self._bubble_count = 0

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def add_user_message(self, text: str) -> None:
        self._add_bubble(text, role="user")

    def add_assistant_message(self, text: str) -> None:
        self._add_bubble(text, role="assistant")

    def clear(self) -> None:
        while self._messages_layout.count() > 1:  # keep stretch
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._bubble_count = 0

    def set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send.setEnabled(enabled)

    def focus_input(self) -> None:
        self._input.setFocus()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.message_submitted.emit(text)

    def _add_bubble(self, text: str, role: str) -> None:
        bubble = MessageBubble(text=text, role=role)
        # Insert before the trailing stretch
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, bubble,
        )
        self._bubble_count += 1

        if self._bubble_count > self._max_messages:
            self._trim_oldest()

        # Auto-scroll
        from PySide6.QtCore import QTimer
        QTimer.singleShot(30, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _trim_oldest(self) -> None:
        if self._messages_layout.count() <= 1:
            return
        item = self._messages_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        self._bubble_count -= 1