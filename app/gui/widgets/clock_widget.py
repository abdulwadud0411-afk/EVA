"""
Live date + time widget (Phase 21 — Batch 2.5B).

Displays current date and time in the top-right header.
Updates every second.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.gui.theme import FONTS, PALETTE


class ClockWidget(QWidget):
    """Live date + time display."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._time_label = QLabel("--:--:--")
        self._time_label.setAlignment(Qt.AlignRight)
        self._time_label.setStyleSheet(
            f"color: {PALETTE.fg_primary};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_lg}px;"
            f"font-weight: {FONTS.weight_bold};"
            "background: transparent;"
        )

        self._date_label = QLabel("--")
        self._date_label.setAlignment(Qt.AlignRight)
        self._date_label.setStyleSheet(
            f"color: {PALETTE.fg_muted};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_xs}px;"
            "background: transparent;"
        )

        layout.addWidget(self._time_label)
        layout.addWidget(self._date_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)  # 1 second
        self._tick()

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        now = datetime.now()
        self._time_label.setText(self.format_time(now))
        self._date_label.setText(self.format_date(now))

    # ------------------------------------------------------------------ #
    # Static formatters (also used by tests)
    # ------------------------------------------------------------------ #
    @staticmethod
    def format_time(dt: datetime) -> str:
        # 12-hour with AM/PM, matching JARVIS-style display
        return dt.strftime("%I:%M:%S %p").lstrip("0")

    @staticmethod
    def format_date(dt: datetime) -> str:
        # e.g. "Monday, 17 September 2026"
        return dt.strftime("%A, %d %B %Y")