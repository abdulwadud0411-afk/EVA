"""
Voice animation (Phase 21).

A simple waveform bar animation that reacts to different states:
    IDLE      — flat
    LISTENING — fast ripples (cyan)
    THINKING  — slow purple waves
    SPEAKING  — pink waveform
"""
from __future__ import annotations

import math
import random
from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from app.gui.gui_state import GUIStatus
from app.gui.theme import PALETTE


class VoiceAnimation(QWidget):
    def __init__(self, bars: int = 32, parent=None) -> None:
        super().__init__(parent)
        self._bars = bars
        self._heights: List[float] = [0.0] * bars
        self._status = GUIStatus.IDLE
        self._phase = 0.0

        self.setMinimumHeight(48)
        self.setMinimumWidth(180)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def set_status(self, status: GUIStatus) -> None:
        self._status = status

    def _color(self) -> QColor:
        mapping = {
            GUIStatus.IDLE: PALETTE.idle,
            GUIStatus.LISTENING: PALETTE.listening,
            GUIStatus.THINKING: PALETTE.thinking,
            GUIStatus.SPEAKING: PALETTE.speaking,
            GUIStatus.ERROR: PALETTE.error,
        }
        return QColor(mapping.get(self._status, PALETTE.idle))

    def _tick(self) -> None:
        self._phase += 0.25

        for i in range(self._bars):
            if self._status == GUIStatus.IDLE:
                target = 0.05
            elif self._status == GUIStatus.LISTENING:
                target = 0.35 + 0.45 * abs(math.sin(self._phase * 0.8 + i * 0.35))
            elif self._status == GUIStatus.THINKING:
                target = 0.15 + 0.25 * abs(math.sin(self._phase * 0.3 + i * 0.2))
            elif self._status == GUIStatus.SPEAKING:
                target = 0.25 + 0.55 * abs(math.sin(self._phase * 1.2 + i * 0.5))
            else:
                target = 0.05
            target += random.uniform(-0.04, 0.04)
            target = max(0.02, min(1.0, target))

            # Smooth towards target
            self._heights[i] = self._heights[i] * 0.6 + target * 0.4

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        n = self._bars
        bar_w = max(2.0, w / (n * 1.6))
        gap = (w - bar_w * n) / max(1, n - 1)

        color = self._color()
        painter.setPen(Qt.NoPen)

        for i, value in enumerate(self._heights):
            x = i * (bar_w + gap)
            bar_h = max(2.0, value * h * 0.9)
            y = (h - bar_h) / 2.0

            alpha = int(140 + 100 * value)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
            painter.drawRoundedRect(
                int(x), int(y), int(bar_w), int(bar_h),
                int(bar_w / 2), int(bar_w / 2),
            )

        painter.end()