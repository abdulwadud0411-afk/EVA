"""
Microphone listening indicator (Phase 21).

A small circular dot that pulses while EVA is listening.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from app.gui.theme import PALETTE


class MicIndicator(QWidget):
    def __init__(self, diameter: int = 14, parent=None) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self._active = False
        self._phase = 0.0

        self._dot = QLabel(self)
        self._dot.setFixedSize(diameter, diameter)
        self._dot.setAlignment(Qt.AlignCenter)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

        self._repaint()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._repaint()

    def _tick(self) -> None:
        if not self._active:
            return
        self._phase = (self._phase + 0.15) % 1.0
        self._repaint()

    def _repaint(self) -> None:
        if self._active:
            alpha = int(140 + 115 * abs(1 - 2 * self._phase))
            color = f"rgba(34, 211, 238, {alpha / 255:.2f})"
        else:
            color = "rgba(107, 114, 128, 0.5)"

        self._dot.setStyleSheet(
            f"background-color: {color};"
            f"border-radius: {self._diameter // 2}px;"
        )