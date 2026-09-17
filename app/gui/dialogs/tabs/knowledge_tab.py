"""Knowledge tab (Phase 21 Batch 3)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


class KnowledgeTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Knowledge / RAG")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self._count = QLabel("Entries: —")
        layout.addWidget(self._count)

        row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self._refresh_btn)

        self._clear_btn = QPushButton("Clear Knowledge Index")
        self._clear_btn.clicked.connect(self._on_clear)
        row.addWidget(self._clear_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self._status = QLabel("")
        layout.addWidget(self._status)
        layout.addStretch(1)

        self._refresh()

    def _refresh(self) -> None:
        try:
            from app.memory.database import Database
            row = Database.fetchone("SELECT COUNT(*) AS c FROM knowledge_entries")
            n = int(row["c"] or 0) if row else 0
            self._count.setText(f"Entries: {n}")
        except Exception as exc:  # noqa: BLE001
            self._count.setText(f"Entries: (error: {exc})")

    def _on_clear(self) -> None:
        ans = QMessageBox.question(
            self, "Confirm", "Delete all knowledge entries? This cannot be undone.",
        )
        if ans != QMessageBox.Yes:
            return
        try:
            from app.memory.database import Database
            Database.execute("DELETE FROM knowledge_entries")
            self._status.setText("✅ Knowledge index cleared.")
            self._refresh()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ {exc}")