"""Security tab (Phase 21 Batch 3)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QLabel, QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager


class SecurityTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Security")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self._confirm_terminal = QCheckBox("Terminal commands require confirmation")
        self._confirm_delete = QCheckBox("File deletion requires confirmation")
        self._confirm_system = QCheckBox("System changes require confirmation")
        self._sandbox = QCheckBox("Sandbox mode for unknown tasks")
        self._rate_limit = QCheckBox("Rate limiting enabled")
        self._audit = QCheckBox("Audit log enabled")
        self._whitelist = QCheckBox("Network whitelist enabled")

        for cb in (
            self._confirm_terminal, self._confirm_delete, self._confirm_system,
            self._sandbox, self._rate_limit, self._audit, self._whitelist,
        ):
            form.addRow(cb)

        layout.addLayout(form)

        info = QLabel(
            "Changes are saved to user_config.yaml and take effect on next start."
        )
        info.setStyleSheet("color: #a0a0b8; font-size: 11px;")
        layout.addWidget(info)

        layout.addStretch(1)

        # Persist on toggle
        for cb in (
            self._confirm_terminal, self._confirm_delete, self._confirm_system,
            self._sandbox, self._rate_limit, self._audit, self._whitelist,
        ):
            cb.toggled.connect(self._on_change)

    def _load_current(self) -> None:
        self._confirm_terminal.setChecked(
            bool(ConfigManager.get("security.terminal_confirmation", True))
        )
        self._confirm_delete.setChecked(
            bool(ConfigManager.get("security.delete_confirmation", True))
        )
        self._confirm_system.setChecked(
            bool(ConfigManager.get("security.system_changes_confirmation", True))
        )
        self._sandbox.setChecked(
            bool(ConfigManager.get("security.sandbox.enabled", True))
        )
        self._rate_limit.setChecked(
            bool(ConfigManager.get("security.rate_limit.enabled", True))
        )
        self._audit.setChecked(
            bool(ConfigManager.get("security.audit.enabled", True))
        )
        self._whitelist.setChecked(
            bool(ConfigManager.get("security.network.whitelist_enabled", True))
        )

    def _on_change(self) -> None:
        try:
            ConfigManager.set("security.terminal_confirmation",
                              self._confirm_terminal.isChecked(), persist=False)
            ConfigManager.set("security.delete_confirmation",
                              self._confirm_delete.isChecked(), persist=False)
            ConfigManager.set("security.system_changes_confirmation",
                              self._confirm_system.isChecked(), persist=False)
            ConfigManager.set("security.sandbox.enabled",
                              self._sandbox.isChecked(), persist=False)
            ConfigManager.set("security.rate_limit.enabled",
                              self._rate_limit.isChecked(), persist=False)
            ConfigManager.set("security.audit.enabled",
                              self._audit.isChecked(), persist=False)
            ConfigManager.set("security.network.whitelist_enabled",
                              self._whitelist.isChecked(), persist=False)
        except Exception:  # noqa: BLE001
            pass