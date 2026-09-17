"""
Right-side conversation panel (JARVIS layout, EVA purple theme).

Header : title + Clear + Extract buttons
Body   : scrollable messages
Footer : input box + send arrow
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.gui.theme import PALETTE
from app.gui.widgets.message_bubble import MessageBubble


class ConversationPanel(QFrame):
    """Right-side conversation panel."""

    message_submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ConversationPanel")
        self.setStyleSheet(f"""
            QFrame#ConversationPanel {{
                background-color: {PALETTE.bg_primary};
                border: 1px solid {PALETTE.border};
                border-radius: 12px;
            }}
        """)
        self.setMinimumWidth(360)
        self.setMaximumWidth(480)
        self._max_messages = int(ConfigManager.get("gui.chat.max_messages", 500))
        self._bubble_count = 0
        self._build_ui()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # --- Header --- #
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("Conversation")
        title.setStyleSheet(
            f"color: {PALETTE.fg_primary}; font-size: 14px;"
            f"font-weight: 700; background: transparent;"
        )
        header.addWidget(title)
        header.addStretch(1)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PALETTE.bg_tertiary};
                color: {PALETTE.fg_secondary};
                border: 1px solid {PALETTE.border};
                border-radius: 6px;
                padding: 2px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {PALETTE.bg_secondary};
                color: {PALETTE.fg_primary};
            }}
        """)
        self._clear_btn.clicked.connect(self.clear)
        header.addWidget(self._clear_btn)

        self._export_btn = QPushButton("Extract")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PALETTE.accent};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {PALETTE.accent_hover};
            }}
        """)
        self._export_btn.clicked.connect(self._on_export)
        header.addWidget(self._export_btn)

        root.addLayout(header)

        # --- Messages --- #
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("background: transparent;")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._messages_layout = QVBoxLayout(self._container)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(6)
        self._messages_layout.addStretch(1)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        # --- Input --- #
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message…")
        self._input.setFixedHeight(40)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {PALETTE.bg_input};
                color: {PALETTE.fg_primary};
                border: 1px solid {PALETTE.border};
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PALETTE.border_focus};
            }}
        """)
        self._input.returnPressed.connect(self._submit)
        input_row.addWidget(self._input, 1)

        self._send = QPushButton("➤")
        self._send.setFixedSize(40, 40)
        self._send.setCursor(Qt.PointingHandCursor)
        self._send.setStyleSheet(f"""
            QPushButton {{
                background-color: {PALETTE.accent};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {PALETTE.accent_hover};
            }}
        """)
        self._send.clicked.connect(self._submit)
        input_row.addWidget(self._send)

        root.addLayout(input_row)

    # ------------------------------------------------------------------ #
    def add_user_message(self, text: str) -> None:
        self._add_bubble(text, "user")

    def add_assistant_message(self, text: str) -> None:
        self._add_bubble(text, "assistant")

    def clear(self) -> None:
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._bubble_count = 0

    def set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send.setEnabled(enabled)

    def focus_input(self) -> None:
        self._input.setFocus()

    # ------------------------------------------------------------------ #
    def _submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.message_submitted.emit(text)

    def _add_bubble(self, text: str, role: str) -> None:
        bubble = MessageBubble(text=text, role=role)
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, bubble
        )
        self._bubble_count += 1
        if self._bubble_count > self._max_messages:
            self._trim_oldest()
        QTimer.singleShot(30, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _trim_oldest(self) -> None:
        if self._messages_layout.count() <= 1:
            return
        item = self._messages_layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        self._bubble_count -= 1

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save conversation", "conversation.txt", "Text (*.txt)",
        )
        if not path:
            return
        try:
            lines = []
            for i in range(self._messages_layout.count() - 1):
                w = self._messages_layout.itemAt(i).widget()
                if w is None:
                    continue
                for child in w.findChildren(QLabel):
                    name = child.objectName()
                    if name == "BubbleTextUser":
                        lines.append(f"You: {child.text()}")
                    elif name == "BubbleTextAssistant":
                        lines.append(f"EVA: {child.text()}")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(lines))
            QMessageBox.information(self, "Export", f"Saved to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))