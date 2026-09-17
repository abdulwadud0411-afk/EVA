"""
Particle field (Phase 21).

A background of slowly drifting dots with faint "constellation"
lines between nearby particles. Adds depth to the sphere widget.

Design is UNCHANGED from the original — dots still wander on their
own with independent drift + local constellation lines. The only
addition is `set_rotation_delta()`: an extra, gentle whole-field
rotation around the widget center, driven by the sphere's rotation,
so the background turns together with the sphere ("screen soho
ghurbe") without altering how the particles themselves look or move.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from app.gui.gui_state import GUIStatus


@dataclass
class _Dot:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    alpha: int


class ParticleField(QWidget):
    """Ambient floating particles with constellation links."""

    def __init__(self, count: int = 60, parent=None) -> None:
        super().__init__(parent)
        self._dots: List[_Dot] = []
        self._status = GUIStatus.IDLE
        self._last_w = 0
        self._last_h = 0
        self._link_distance = 130.0
        self._count = count

        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 fps — matches the sphere's tick rate

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def set_status(self, status: GUIStatus) -> None:
        self._status = status

    def set_rotation_delta(self, dtheta: float) -> None:
        """Spin the WHOLE field around the widget center by `dtheta`
        radians, on top of each dot's own independent drift. Call this
        every frame with how much the sphere's rotation changed since
        the last call — that's what keeps the background turning in
        sync with the sphere, without touching the particle design."""
        if not self._dots or abs(dtheta) < 1e-9:
            return
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        cos_t = math.cos(dtheta)
        sin_t = math.sin(dtheta)
        for d in self._dots:
            rx = d.x - cx
            ry = d.y - cy
            d.x = cx + rx * cos_t - ry * sin_t
            d.y = cy + rx * sin_t + ry * cos_t

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _ensure_dots(self) -> None:
        w, h = self.width(), self.height()
        if w == self._last_w and h == self._last_h and self._dots:
            return
        self._last_w, self._last_h = w, h
        self._dots = []
        for _ in range(self._count):
            speed = random.uniform(0.10, 0.45)
            angle = random.uniform(0, math.tau)
            self._dots.append(_Dot(
                x=random.uniform(0, w),
                y=random.uniform(0, h),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                size=random.uniform(1.0, 2.4),
                alpha=random.randint(70, 160),
            ))

    def _tick(self) -> None:
        w, h = self.width(), self.height()
        self._ensure_dots()

        speed_mult = 1.0
        if self._status == GUIStatus.LISTENING:
            speed_mult = 2.2
        elif self._status == GUIStatus.SPEAKING:
            speed_mult = 1.6
        elif self._status == GUIStatus.THINKING:
            speed_mult = 1.3

        for d in self._dots:
            d.x += d.vx * speed_mult
            d.y += d.vy * speed_mult
            if d.x < 0:
                d.x = w
            elif d.x > w:
                d.x = 0
            if d.y < 0:
                d.y = h
            elif d.y > h:
                d.y = 0
        self.update()

    # ------------------------------------------------------------------ #
    # Paint
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._dots:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Choose line/dot color by status
        if self._status == GUIStatus.LISTENING:
            base_color = QColor(125, 211, 252)
        elif self._status == GUIStatus.SPEAKING:
            base_color = QColor(244, 114, 182)
        elif self._status == GUIStatus.ERROR:
            base_color = QColor(239, 68, 68)
        else:
            base_color = QColor(139, 92, 246)  # logo violet

        # --- Lines between nearby dots ---
        painter.setPen(QPen(base_color, 0.7))
        n = len(self._dots)
        for i in range(n):
            a = self._dots[i]
            for j in range(i + 1, n):
                b = self._dots[j]
                dx = a.x - b.x
                dy = a.y - b.y
                dist = math.hypot(dx, dy)
                if dist < self._link_distance:
                    alpha = int(70 * (1.0 - dist / self._link_distance))
                    if alpha <= 0:
                        continue
                    line_color = QColor(
                        base_color.red(), base_color.green(), base_color.blue(), alpha,
                    )
                    painter.setPen(QPen(line_color, 0.7))
                    painter.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))

        # --- Dots (with a soft glow) ---
        painter.setPen(Qt.NoPen)
        for d in self._dots:
            pos = QPointF(d.x, d.y)
            c = QColor(base_color.red(), base_color.green(), base_color.blue(), d.alpha)

            # Soft outer halo — fades from the dot's color to transparent
            glow_radius = d.size * 4.0
            gradient = QRadialGradient(pos, glow_radius)
            gradient.setColorAt(0.0, c)
            gradient.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(pos, glow_radius, glow_radius)

            # Bright core on top, a bit lighter than the base color
            core = QColor(
                min(255, base_color.red() + 70),
                min(255, base_color.green() + 70),
                min(255, base_color.blue() + 70),
                min(255, d.alpha + 60),
            )
            painter.setBrush(QBrush(core))
            painter.drawEllipse(pos, d.size, d.size)

        painter.end()