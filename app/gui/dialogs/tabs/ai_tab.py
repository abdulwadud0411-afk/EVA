"""
AI Provider tab (Phase 21 Batch 3).

Re-uses Phase 17 SettingsManager + ProviderCatalog + check_provider.
"""
from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.logger import get_logger
from app.settings.provider_catalog import ProviderCatalog
from app.settings.settings_manager import SettingsManager
from app.settings.test_connection import check_provider

logger = get_logger(__name__)


class AITab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_current()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("AI Provider")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self._provider = QComboBox()
        for key in ProviderCatalog.list_providers():
            self._provider.addItem(ProviderCatalog.display_names().get(key, key), key)
        self._provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self._provider)

        self._model = QComboBox()
        self._model.setEditable(True)
        form.addRow("Model:", self._model)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("sk-…")
        form.addRow("API Key:", self._api_key)

        self._base_url = QLineEdit()
        form.addRow("Base URL:", self._base_url)

        layout.addLayout(form)

        # Buttons
        row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._on_test)
        row.addWidget(self._test_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.clicked.connect(self._on_save)
        row.addWidget(self._save_btn)

        row.addStretch(1)
        layout.addLayout(row)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        layout.addStretch(1)

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #
    def _load_current(self) -> None:
        try:
            snapshot = SettingsManager.get_ai_settings()
            key = snapshot.get("provider", "deepseek")
            idx = self._provider.findData(key)
            if idx >= 0:
                self._provider.setCurrentIndex(idx)
            self._api_key.setText(SettingsManager.get_api_key(key) or "")
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Load failed: {exc}")

    def _on_provider_changed(self, _idx: int) -> None:
        key = self._provider.currentData()
        if not key:
            return
        self._model.clear()
        self._model.addItems(ProviderCatalog.models_for(key))
        cfg = SettingsManager.get_provider_config(key)
        self._base_url.setText(
            cfg.get("base_url", ProviderCatalog.default_base_url(key))
        )
        self._api_key.setText(SettingsManager.get_api_key(key) or "")

        if not ProviderCatalog.requires_api_key(key):
            self._api_key.setEnabled(False)
            self._api_key.setPlaceholderText("(no key needed)")
        else:
            self._api_key.setEnabled(True)

    def _on_test(self) -> None:
        key = self._provider.currentData()
        api_key = self._api_key.text().strip() or None
        base_url = self._base_url.text().strip() or None
        model = self._model.currentText().strip() or None

        self._status.setText("Testing…")
        self._test_btn.setEnabled(False)

        def _worker() -> None:
            try:
                result = asyncio.run(
                    check_provider(key, api_key=api_key, base_url=base_url, model=model)
                )
                msg = ("✅ " if result.success else "❌ ") + result.message
            except Exception as exc:  # noqa: BLE001
                msg = f"❌ {exc}"
            self._status.setText(msg)
            self._test_btn.setEnabled(True)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_save(self) -> None:
        key = self._provider.currentData()
        try:
            SettingsManager.set_provider_config(
                key,
                api_key=self._api_key.text().strip() or None,
                base_url=self._base_url.text().strip() or None,
                model=self._model.currentText().strip() or None,
            )
            SettingsManager.set_active_provider(key)
            self._status.setText(f"✅ Saved. Active provider: {key}")
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"❌ Save failed: {exc}")