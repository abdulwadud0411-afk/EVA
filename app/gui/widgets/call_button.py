"""
Call button (Phase 21).

A perfect circular phone-style button — like the green/red call buttons
on Android phones.

    OFF (idle) → pure GREEN  (ready to start listening)
    ON  (active) → pure RED  (voice mode active)

The phone icon is drawn with QPainter (white) — no emoji, so the color
stays consistent across systems.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QPushButton

from app.gui.gui_state import GUIStatus


# ---- Phone-style colors ---------------------------------------------- #
_GREEN = "#22c55e"          # Android call green
_GREEN_HOVER = "#16a34a"
_RED = "#ef4444"            # Android hangup red
_RED_HOVER = "#dc2626"
_ICON_COLOR = "#ffffff"


class CallButton(QPushButton):
    """Circular phone-style toggle button."""

    toggled = Signal(bool)

    def __init__(self, diameter: int = 76, parent=None) -> None:
        super().__init__("", parent)
        self.setObjectName("CallButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Start / stop voice mode")

        self._diameter = diameter
        self.setFixedSize(diameter, diameter)

        self._active = False
        self._hover = False
        self.setMouseTracking(True)

        self.clicked.connect(self._on_clicked)

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #
    def _on_clicked(self) -> None:
        self._active = not self._active
        self.update()
        self.toggled.emit(self._active)

    @property
    def is_active(self) -> bool:
        return self._active

    def sync_status(self, status: GUIStatus) -> None:
        """Kept for main_window compatibility — does not change color."""
        self.update()

    # ------------------------------------------------------------------ #
    # Hover tracking
    # ------------------------------------------------------------------ #
    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    # ------------------------------------------------------------------ #
    # Paint
    # ------------------------------------------------------------------ #
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        d = self._diameter
        cx = d / 2.0
        cy = d / 2.0

        # ---- Background circle ---- #
        if self._active:
            fill = _RED_HOVER if self._hover else _RED
        else:
            fill = _GREEN_HOVER if self._hover else _GREEN

        painter.setBrush(QColor(fill))
        painter.drawEllipse(QRectF(0, 0, d, d))

        # ---- Phone icon ---- #
        self._draw_phone(painter, cx, cy, d)

        painter.end()

    # ------------------------------------------------------------------ #
    # Phone icon painter
    # ------------------------------------------------------------------ #
    @staticmethod
    def _draw_phone(painter: QPainter, cx: float, cy: float, d: float) -> None:
        """Draw a simple phone receiver (dumbbell shape, rotated)."""
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-40)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(_ICON_COLOR))

        size = d

        # Body: horizontal rounded bar
        body_w = size * 0.42
        body_h = size * 0.16
        body_rect = QRectF(-body_w / 2, -body_h / 2, body_w, body_h)
        painter.drawRoundedRect(body_rect, body_h / 2, body_h / 2)

        # Ear piece (left end) — small circle
        ball_size = body_h * 1.55
        painter.drawEllipse(
            QRectF(-body_w / 2 - ball_size * 0.45,
                   -ball_size / 2,
                   ball_size, ball_size)
        )

        # Mouth piece (right end) — small circle
        painter.drawEllipse(
            QRectF(body_w / 2 - ball_size * 0.55,
                   -ball_size / 2,
                   ball_size, ball_size)
        )

        painter.restore()