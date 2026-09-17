"""
Info panel (Phase 21 — Batch 2.5B).

Compact summary of EVA's internal state:
    - Memory : conversation count, user preferences count
    - Skills : learned skill count
    - Tools  : registered tool count
    - LLM    : current AI provider + health dot

All reads are wrapped in try/except so the panel never crashes.
Updates every 5 seconds.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.gui.theme import FONTS, PALETTE


class _InfoRow(QWidget):
    """One row: label on the left, value on the right."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        self._label = QLabel(label)
        self._label.setStyleSheet(
            f"color: {PALETTE.fg_muted};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_xs}px;"
            "background: transparent;"
        )

        self._value = QLabel("—")
        self._value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._value.setStyleSheet(
            f"color: {PALETTE.fg_primary};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_sm}px;"
            f"font-weight: {FONTS.weight_medium};"
            "background: transparent;"
        )

        row.addWidget(self._label, 1)
        row.addWidget(self._value, 0)

    def set_value(self, text: str, color: Optional[str] = None) -> None:
        self._value.setText(str(text))
        c = color or PALETTE.fg_primary
        self._value.setStyleSheet(
            f"color: {c};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_sm}px;"
            f"font-weight: {FONTS.weight_medium};"
            "background: transparent;"
        )


class InfoPanel(QFrame):
    """Compact state summary."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RightPanel")
        self.setMinimumWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel("EVA State")
        title.setObjectName("StatusHeader")
        layout.addWidget(title)

        self._row_memory = _InfoRow("Memory entries")
        self._row_skills = _InfoRow("Skills learned")
        self._row_tools = _InfoRow("Tools registered")
        self._row_provider = _InfoRow("AI Provider")
        self._row_health = _InfoRow("Health")

        for row in (
            self._row_memory, self._row_skills,
            self._row_tools, self._row_provider, self._row_health,
        ):
            layout.addWidget(row)

        layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)
        self.refresh()

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        data = self.gather()
        self._row_memory.set_value(str(data["memory"]))
        self._row_skills.set_value(str(data["skills"]))
        self._row_tools.set_value(str(data["tools"]))
        self._row_provider.set_value(data["provider"])
        self._row_health.set_value(
            data["health"],
            PALETTE.success if data["health"] == "OK" else PALETTE.warning,
        )

    # ------------------------------------------------------------------ #
    # Static gatherer (testable)
    # ------------------------------------------------------------------ #
    @staticmethod
    def gather() -> dict:
        """Read state from config / memory / tool registry (safe)."""
        memory_count = 0
        skills_count = 0
        tools_count = 0
        provider = "—"
        health = "OK"

        # Provider
        try:
            provider = str(ConfigManager.get("ai.provider", "deepseek"))
        except Exception:  # noqa: BLE001
            health = "WARN"

        # Memory + skills
        try:
            from app.memory.database import Database
            row = Database.fetchone(
                "SELECT COUNT(*) AS c FROM knowledge_entries"
            )
            if row is not None:
                memory_count = int(row["c"] or 0)
        except Exception:  # noqa: BLE001
            pass

        try:
            from app.memory.database import Database
            row = Database.fetchone("SELECT COUNT(*) AS c FROM skills")
            if row is not None:
                skills_count = int(row["c"] or 0)
        except Exception:  # noqa: BLE001
            pass

        # Tools
        try:
            from app.tools.registry import ToolRegistry
            tools_count = len(ToolRegistry.list_tools())
        except Exception:  # noqa: BLE001
            pass

        return {
            "memory": memory_count,
            "skills": skills_count,
            "tools": tools_count,
            "provider": provider,
            "health": health,
        }