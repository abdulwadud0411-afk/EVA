"""
Confirmation dialog (Phase 21 Batch 3).

A modal dialog for HIGH/CRITICAL actions requested by a tool.
Works with the Phase 20 ConfirmationGate: replacing the default CLI
confirmer with a GUI one.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class ConfirmationDialog(QDialog):
    def __init__(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        risk: str = "HIGH",
        reason: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("EVA — Confirmation Required")
        self.setMinimumSize(480, 320)
        self._build_ui(tool_name, arguments or {}, risk, reason)

    def _build_ui(self, tool_name, arguments, risk, reason) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Risk header
        risk_label = QLabel(f"⚠ {risk} RISK")
        color = {"CRITICAL": "#ef4444", "HIGH": "#f59e0b"}.get(risk, "#a78bfa")
        risk_label.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: 700;")
        layout.addWidget(risk_label)

        title = QLabel(f"Tool: {tool_name}")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        if reason:
            reason_label = QLabel(reason)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("color: #b8aed4;")
            layout.addWidget(reason_label)

        # Arguments
        args_label = QLabel("Arguments:")
        layout.addWidget(args_label)
        args_view = QTextEdit()
        args_view.setReadOnly(True)
        args_view.setPlainText(
            "\n".join(f"{k}: {v}" for k, v in arguments.items()) or "(none)"
        )
        args_view.setMaximumHeight(120)
        layout.addWidget(args_view)

        layout.addStretch(1)

        # Buttons
        row = QHBoxLayout()
        row.addStretch(1)

        deny = QPushButton("Deny")
        deny.clicked.connect(self.reject)
        row.addWidget(deny)

        allow = QPushButton("Allow")
        allow.setObjectName("PrimaryButton")
        allow.setStyleSheet(
            "QPushButton { background-color: #10b981; color: white;"
            " border: none; padding: 8px 20px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #34d399; }"
        )
        allow.clicked.connect(self.accept)
        row.addWidget(allow)

        layout.addLayout(row)


async def ask_confirmation(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    risk: str = "HIGH",
    reason: str = "",
) -> bool:
    """
    Async wrapper around ConfirmationDialog, usable as a
    ConfirmationGate confirmer.

    Must be called from the Qt main thread (or use QMetaObject.invokeMethod).
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        # No GUI running — deny by default
        return False

    dlg = ConfirmationDialog(tool_name, arguments, risk, reason)
    result = dlg.exec()
    return result == QDialog.Accepted