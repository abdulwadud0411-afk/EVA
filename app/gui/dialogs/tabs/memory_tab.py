"""Memory tab (Phase 21 Batch 3)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager


class MemoryTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Memory")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self._history_limit = QSpinBox()
        self._history_limit.setRange(2, 50)
        form.addRow("Chat history limit:", self._history_limit)

        self._retention = QSpinBox()
        self._retention.setRange(0, 3650)
        self._retention.setSuffix(" days")
        form.addRow("Retention:", self._retention)

        layout.addLayout(form)

        row = QHBoxLayout()
        self._clear_btn = QPushButton("Clear Conversation History")
        self._clear_btn.clicked.connect(self._on_clear)
        row.addWidget(self._clear_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.clicked.connect(self._on_save)
        row.addWidget(self._save_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self._status = QLabel("")
        layout.addWidget(self._status)
        layout.addStretch(1)

    def _load_current(self) -> None:
        try:
            self._history_limit.setValue(int(ConfigManager.get("ai.history_limit", 8)))
            self._retention.setValue(int(ConfigManager.get("memory.retention_days", 365)))
        except Exception:  # noqa: BLE001
            pass

    def _on_save(self) -> None:
        try:
            ConfigManager.set("ai.history_limit", self._history_limit.value())
            ConfigManager.set("memory.retention_days", self._retention.value())
            self._status.setText("✅ Memory settings saved.")
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ {exc}")

    def _on_clear(self) -> None:
        try:
            from app.memory.database import Database
            Database.execute("DELETE FROM messages")
            self._status.setText("✅ Conversation history cleared.")
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ {exc}")