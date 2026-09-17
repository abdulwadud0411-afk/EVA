"""
Settings dialog (Phase 21 Batch 3).

Tabbed settings window: AI, Voice, Memory, Knowledge, Skills, Storage, Security.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from app.gui.dialogs.tabs import (
    AITab, VoiceTab, MemoryTab, KnowledgeTab, SkillsTab, StorageTab, SecurityTab,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EVA — Settings")
        self.setMinimumSize(640, 560)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(AITab(), "AI")
        tabs.addTab(VoiceTab(), "Voice")
        tabs.addTab(MemoryTab(), "Memory")
        tabs.addTab(KnowledgeTab(), "Knowledge")
        tabs.addTab(SkillsTab(), "Skills")
        tabs.addTab(StorageTab(), "Storage")
        tabs.addTab(SecurityTab(), "Security")
        layout.addWidget(tabs, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)


def open_settings(parent=None) -> None:
    """Show the settings dialog modally."""
    dlg = SettingsDialog(parent)
    dlg.exec()