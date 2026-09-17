"""Skills tab (Phase 21 Batch 3)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


class SkillsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Learned Skills")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self._refresh_btn)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.clicked.connect(self._on_delete)
        row.addWidget(self._delete_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def _refresh(self) -> None:
        self._list.clear()
        try:
            from app.skills.registry import SkillRegistry
            for name in SkillRegistry.list_skills():
                item = QListWidgetItem(name)
                item.setData(0x0100, name)  # Qt.UserRole
                self._list.addItem(item)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ {exc}")

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        name = item.data(0x0100)
        ans = QMessageBox.question(self, "Confirm", f"Delete skill '{name}'?")
        if ans != QMessageBox.Yes:
            return
        try:
            from app.skills.registry import SkillRegistry
            ok = SkillRegistry.delete_skill(name)
            self._status.setText(f"✅ Deleted '{name}'" if ok else f"❌ Not found")
            self._refresh()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ {exc}")