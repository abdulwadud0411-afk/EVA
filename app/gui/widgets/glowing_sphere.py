"""
Glowing 3D particle sphere (Phase 21 + 2.5A).

    - ~1500 small dots forming a sphere
    - Calm smooth rotation
    - Slight vibration/shake when SPEAKING
    - Bright pulse when LISTENING
    - Mouse drag to rotate manually (auto-resumes on release)

No OpenGL — pure QPainter.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter
from PySide6.QtWidgets import QWidget

from app.gui.gui_state import GUIStatus


# ---------------------------------------------------------------------- #
# Shared constants — particle_field uses the SAME base_radius formula
# ---------------------------------------------------------------------- #
BASE_RADIUS_FRACTION = 0.30    # sphere radius = min(w,h) * 0.30
TILT = 0.22                    # default camera tilt


# ---------------------------------------------------------------------- #
# Palette — unchanged
# ---------------------------------------------------------------------- #
_DOT_FAR = QColor(48, 24, 96)
_DOT_MID = QColor(139, 92, 246)
_DOT_NEAR = QColor(216, 200, 255)

_DOT_CYAN = QColor(125, 211, 252)
_DOT_CYAN_BRIGHT = QColor(220, 245, 255)

_DOT_PINK = QColor(244, 114, 182)
_DOT_PINK_BRIGHT = QColor(255, 220, 245)

_DOT_RED = QColor(239, 68, 68)
_DOT_RED_BRIGHT = QColor(255, 200, 220)


@dataclass
class _Point:
    x: float
    y: float
    z: float
    phase: float


def _fibonacci_sphere(n: int) -> List[_Point]:
    points: List[_Point] = []
    if n <= 0:
        return points
    golden = math.pi * (1.0 + math.sqrt(5.0))
    for i in range(n):
        phi = math.acos(1.0 - 2.0 * (i + 0.5) / n)
        theta = golden * i
        x = math.sin(phi) * math.cos(theta)
        y = math.sin(phi) * math.sin(theta)
        z = math.cos(phi)
        points.append(_Point(x, y, z, random.uniform(0.0, math.tau)))
    return points


def project_3d(
    x: float, y: float, z: float,
    rot_y: float, rot_x: float, tilt: float = TILT,
) -> Tuple[float, float, float]:
    """
    Rotate and return (x, y, depth).
    Shared by GlowingSphere and ParticleField so both align perfectly.
    """
    cos_y = math.cos(rot_y)
    sin_y = math.sin(rot_y)
    x1 = x * cos_y + z * sin_y
    z1 = -x * sin_y + z * cos_y
    y1 = y

    total_x = rot_x + tilt
    cos_x = math.cos(total_x)
    sin_x = math.sin(total_x)
    y2 = y1 * cos_x - z1 * sin_x
    z2 = y1 * sin_x + z1 * cos_x

    return x1, y2, z2


class GlowingSphere(QWidget):
    """Rotating particle sphere — mouse-draggable."""

    def __init__(self, num_points: int = 1500, parent=None) -> None:
        super().__init__(parent)
        self._points = _fibonacci_sphere(num_points)

        # Auto rotation (Y axis)
        self._auto_rot_y = 0.0
        # Mouse drag offsets
        self._drag_x = 0.0
        self._drag_y = 0.0
        self._dragging = False
        self._last_mouse: Optional[QPointF] = None

        self._pulse = 0.0
        self._pulse_dir = 1.0
        self._intensity = 0.0
        self._status = GUIStatus.IDLE

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(240, 240)
        self.setCursor(QCursor(Qt.OpenHandCursor))
        self.setMouseTracking(True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ------------------------------------------------------------------ #
    # Public state — consumed by ParticleField to stay in sync
    # ------------------------------------------------------------------ #
    @property
    def rotation_x(self) -> float:
        return self._drag_x

    @property
    def rotation_y(self) -> float:
        return self._auto_rot_y + self._drag_y

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def set_status(self, status: GUIStatus) -> None:
        self._status = status

    def set_intensity(self, intensity: float) -> None:
        self._intensity = max(0.0, min(1.0, float(intensity)))

    def reset_rotation(self) -> None:
        self._drag_x = 0.0
        self._drag_y = 0.0

    # ------------------------------------------------------------------ #
    # Animation
    # ------------------------------------------------------------------ #
    def _rotation_speed(self) -> float:
        return {
            GUIStatus.IDLE: 0.0035,
            GUIStatus.LISTENING: 0.0060,
            GUIStatus.THINKING: 0.0050,
            GUIStatus.SPEAKING: 0.0040,
            GUIStatus.ERROR: 0.0015,
        }.get(self._status, 0.0035)

    def _tick(self) -> None:
        # Only auto-rotate when NOT dragging
        if not self._dragging:
            self._auto_rot_y = (self._auto_rot_y + self._rotation_speed()) % math.tau

        if self._status == GUIStatus.LISTENING:
            self._pulse += 0.08 * self._pulse_dir
            if self._pulse >= 1.0:
                self._pulse = 1.0
                self._pulse_dir = -1.0
            elif self._pulse <= 0.0:
                self._pulse = 0.0
                self._pulse_dir = 1.0

        self.update()

    # ------------------------------------------------------------------ #
    # Mouse interaction
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_mouse = event.position()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._dragging or self._last_mouse is None:
            super().mouseMoveEvent(event)
            return
        pos = event.position()
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()

        self._drag_y += dx * 0.008
        self._drag_x += dy * 0.008

        # Clamp X rotation to ±π/2 (avoid upside-down flip)
        max_x = math.pi * 0.5
        if self._drag_x > max_x:
            self._drag_x = max_x
        elif self._drag_x < -max_x:
            self._drag_x = -max_x

        self._last_mouse = pos
        event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._last_mouse = None
            self.setCursor(QCursor(Qt.OpenHandCursor))
            event.accept()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        """Double-click resets manual rotation."""
        self.reset_rotation()
        event.accept()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------ #
    # Colors
    # ------------------------------------------------------------------ #
    def _colors(self) -> Tuple[QColor, QColor, QColor]:
        if self._status == GUIStatus.LISTENING:
            return _DOT_FAR, _DOT_CYAN, _DOT_CYAN_BRIGHT
        if self._status == GUIStatus.SPEAKING:
            return _DOT_FAR, _DOT_PINK, _DOT_PINK_BRIGHT
        if self._status == GUIStatus.ERROR:
            return _DOT_FAR, _DOT_RED, _DOT_RED_BRIGHT
        return _DOT_FAR, _DOT_MID, _DOT_NEAR

    # ------------------------------------------------------------------ #
    # Paint
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        # Shared radius — matches particle_field
        radius = min(w, h) * BASE_RADIUS_FRACTION

        far_c, mid_c, near_c = self._colors()
        speaking = self._status == GUIStatus.SPEAKING
        listening = self._status == GUIStatus.LISTENING

        shake = 1.8 * self._intensity if speaking else 0.0
        pulse = 1.0 + (0.04 * self._pulse if listening else 0.0)
        radius *= pulse

        rot_x = self.rotation_x
        rot_y = self.rotation_y

        # ---- Project ---- #
        projected = []
        for p in self._points:
            x2, y2, z2 = project_3d(p.x, p.y, p.z, rot_y, rot_x)
            projected.append((x2, y2, z2, p.phase))

        projected.sort(key=lambda t: t[2])

        # ---- Draw ---- #
        for x, y, z, phase in projected:
            depth = (z + 1.0) * 0.5
            perspective = 0.55 + 0.45 * depth

            sx = cx + x * radius * perspective
            sy = cy + y * radius * perspective

            if speaking:
                vib = shake * math.sin(rot_y * 40.0 + phase * 8.0)
                sx += vib * math.cos(phase * 3.0)
                sy += vib * math.sin(phase * 3.0)

            t = depth
            r = int(far_c.red() * (1 - t) + near_c.red() * t)
            g = int(far_c.green() * (1 - t) + near_c.green() * t)
            b = int(far_c.blue() * (1 - t) + near_c.blue() * t)
            alpha = int(40 + 200 * t)

            if listening and (math.sin(phase + rot_y * 4.0) > 0.85):
                alpha = min(255, alpha + 80)
                r = min(255, r + 60)
                g = min(255, g + 60)
                b = min(255, b + 60)

            base_size = 0.65
            if speaking:
                base_size = 0.75 + 0.35 * self._intensity
            elif listening:
                base_size = 0.85
            size = base_size * perspective
            size = max(0.35, size)

            painter.setBrush(QBrush(QColor(r, g, b, alpha)))
            painter.drawEllipse(QPointF(sx, sy), size, size)

        painter.end()