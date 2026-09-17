"""Storage tab (Phase 21 Batch 3)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


class StorageTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Storage")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        self._stats = QLabel("—")
        self._stats.setWordWrap(True)
        layout.addWidget(self._stats)

        row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh Stats")
        self._refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self._refresh_btn)

        self._cleanup_btn = QPushButton("Run Cleanup")
        self._cleanup_btn.clicked.connect(self._on_cleanup)
        row.addWidget(self._cleanup_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self._status = QLabel("")
        layout.addWidget(self._status)
        layout.addStretch(1)

    def _refresh(self) -> None:
        try:
            from app.storage.manager import StorageManager
            stats = StorageManager.stats()
            total_mb = stats.get("total_bytes", 0) / (1024 * 1024)
            files = stats.get("total_files", 0)
            self._stats.setText(
                f"Total: {files} files, {total_mb:.1f} MB\n"
                f"Root: {stats.get('data_root', '?')}"
            )
        except Exception as exc:  # noqa: BLE001
            self._stats.setText(f"Error: {exc}")

    def _on_cleanup(self) -> None:
        try:
            from app.storage.manager import StorageManager
            results = StorageManager.cleanup_all()
            removed = sum(r.get("removed", 0) for r in results.values())
            self._status.setText(f"✅ Cleanup done — {removed} file(s) removed.")
            self._refresh()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ {exc}")