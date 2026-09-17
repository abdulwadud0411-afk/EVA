"""
Vector icons drawn with QPainter (Phase 22 redesign).

Replaces emoji icons (which render as ugly monochrome text in Qt).

Icons provided:
    - CameraIcon
    - MicIcon
    - KeyboardIcon
    - PhoneIcon
    - ScreenshotIcon

Each is a QWidget-based clickable button with a hover effect.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

from app.gui.theme import PALETTE


class _IconBase(QWidget):
    """Base class for circular icon buttons."""

    clicked = Signal()

    def __init__(self, size: int = 52, parent=None) -> None:
        super().__init__(parent)
        self._size = size
        self._hover = False
        self._pressed = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ #
    # Interaction
    # ------------------------------------------------------------------ #
    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    # ------------------------------------------------------------------ #
    # Paint helpers
    # ------------------------------------------------------------------ #
    def _bg_color(self) -> QColor:
        if self._pressed:
            return QColor(PALETTE.accent_pressed)
        if self._hover:
            return QColor(PALETTE.bg_secondary)
        return QColor(PALETTE.bg_tertiary)

    def _border_color(self) -> QColor:
        if self._hover or self._pressed:
            return QColor(PALETTE.accent)
        return QColor(PALETTE.border)

    def _icon_color(self) -> QColor:
        if self._hover or self._pressed:
            return QColor(PALETTE.accent_hover)
        return QColor(PALETTE.fg_primary)

    def _paint_bg(self, painter: QPainter) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(self._border_color(), 1.5))
        painter.setBrush(QBrush(self._bg_color()))
        painter.drawEllipse(QRectF(0.5, 0.5, self._size - 1, self._size - 1))

    def _paint_icon(self, painter: QPainter) -> None:
        """Override in subclasses."""
        pass

    def paintEvent(self, e) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._paint_bg(painter)
        self._paint_icon(painter)
        painter.end()


# ====================================================================== #
# Camera
# ====================================================================== #
class CameraIcon(_IconBase):
    def _paint_icon(self, painter: QPainter) -> None:
        c = self._icon_color()
        pen = QPen(c, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Body
        body_w = self._size * 0.42
        body_h = self._size * 0.32
        body = QRectF(
            (self._size - body_w) / 2,
            (self._size - body_h) / 2 + 2,
            body_w, body_h,
        )
        painter.drawRoundedRect(body, 4, 4)

        # Top bump (viewfinder)
        bump_w = body_w * 0.35
        bump_h = 4.0
        bump = QRectF(
            body.left() + (body_w - bump_w) / 2,
            body.top() - bump_h,
            bump_w, bump_h,
        )
        painter.drawRoundedRect(bump, 2, 2)

        # Lens circle
        r = body_h * 0.55 / 2
        painter.drawEllipse(
            QPointF(body.center().x(), body.center().y()), r, r
        )


# ====================================================================== #
# Microphone
# ====================================================================== #
class MicIcon(_IconBase):
    def _paint_icon(self, painter: QPainter) -> None:
        c = self._icon_color()
        pen = QPen(c, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        cx = self._size / 2

        # Capsule (mic head)
        cap_w = self._size * 0.20
        cap_h = self._size * 0.34
        cap = QRectF(cx - cap_w / 2, self._size * 0.22, cap_w, cap_h)
        painter.drawRoundedRect(cap, cap_w / 2, cap_w / 2)

        # U-shape holder (arc)
        arc_w = cap_w * 2.0
        arc = QRectF(cx - arc_w / 2, self._size * 0.34, arc_w, arc_w * 0.85)
        painter.drawArc(arc, 180 * 16, 180 * 16)

        # Stem
        painter.drawLine(
            QPointF(cx, arc.bottom()),
            QPointF(cx, self._size * 0.78),
        )

        # Base
        base_w = self._size * 0.32
        painter.drawLine(
            QPointF(cx - base_w / 2, self._size * 0.78),
            QPointF(cx + base_w / 2, self._size * 0.78),
        )


# ====================================================================== #
# Keyboard
# ====================================================================== #
class KeyboardIcon(_IconBase):
    def _paint_icon(self, painter: QPainter) -> None:
        c = self._icon_color()
        pen = QPen(c, 1.8)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Keyboard body
        body_w = self._size * 0.56
        body_h = self._size * 0.36
        body = QRectF(
            (self._size - body_w) / 2,
            (self._size - body_h) / 2,
            body_w, body_h,
        )
        painter.drawRoundedRect(body, 3, 3)

        # Key grid (3 rows × 4 keys)
        rows = 3
        cols = 4
        pad_x = body_w * 0.12
        pad_y = body_h * 0.18
        cell_w = (body_w - pad_x * 2) / cols
        cell_h = (body_h - pad_y * 2) / rows

        painter.setBrush(QBrush(c))
        for r in range(rows):
            for col in range(cols):
                # Skip a couple to make it look like a real keyboard
                if r == rows - 1 and col == 1:
                    continue
                if r == rows - 1 and col == 2:
                    continue
                kx = body.left() + pad_x + col * cell_w + cell_w * 0.18
                ky = body.top() + pad_y + r * cell_h + cell_h * 0.18
                kw = cell_w * 0.64
                kh = cell_h * 0.64
                painter.drawRoundedRect(QRectF(kx, ky, kw, kh), 1, 1)

        # Space bar
        space_w = cell_w * 2 * 0.55
        space = QRectF(
            body.center().x() - space_w / 2,
            body.top() + pad_y + (rows - 1) * cell_h + cell_h * 0.18,
            space_w,
            cell_h * 0.64,
        )
        painter.drawRoundedRect(space, 1, 1)


# ====================================================================== #
# Screenshot
# ====================================================================== #
class ScreenshotIcon(_IconBase):
    def _paint_icon(self, painter: QPainter) -> None:
        c = self._icon_color()
        pen = QPen(c, 2.0)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Frame corners
        frame_w = self._size * 0.42
        frame_h = self._size * 0.32
        frame = QRectF(
            (self._size - frame_w) / 2,
            (self._size - frame_h) / 2,
            frame_w, frame_h,
        )

        # Draw only 4 corners (crosshair frame)
        corner_len = frame_w * 0.28
        # Top-left
        painter.drawLine(QPointF(frame.left(), frame.top()),
                         QPointF(frame.left() + corner_len, frame.top()))
        painter.drawLine(QPointF(frame.left(), frame.top()),
                         QPointF(frame.left(), frame.top() + corner_len))
        # Top-right
        painter.drawLine(QPointF(frame.right(), frame.top()),
                         QPointF(frame.right() - corner_len, frame.top()))
        painter.drawLine(QPointF(frame.right(), frame.top()),
                         QPointF(frame.right(), frame.top() + corner_len))
        # Bottom-left
        painter.drawLine(QPointF(frame.left(), frame.bottom()),
                         QPointF(frame.left() + corner_len, frame.bottom()))
        painter.drawLine(QPointF(frame.left(), frame.bottom()),
                         QPointF(frame.left(), frame.bottom() - corner_len))
        # Bottom-right
        painter.drawLine(QPointF(frame.right(), frame.bottom()),
                         QPointF(frame.right() - corner_len, frame.bottom()))
        painter.drawLine(QPointF(frame.right(), frame.bottom()),
                         QPointF(frame.right(), frame.bottom() - corner_len))

        # Center dot
        painter.setBrush(QBrush(c))
        r = 1.5
        painter.drawEllipse(QPointF(frame.center()), r, r)