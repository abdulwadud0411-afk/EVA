"""
EVA glowing logo widget (Phase 21).

Displays `assets/logo.png` (if present) with a soft glow. When no
asset is available, falls back to a text-based "EVA" emblem.

The pulse effect uses QGraphicsOpacityEffect + QPropertyAnimation
instead of repeated setStyleSheet calls (which would leak memory
and freeze the GUI).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.gui.theme import PALETTE, FONTS


class LogoWidget(QWidget):
    def __init__(self, size: int = 72, parent=None) -> None:
        super().__init__(parent)
        self._size = size
        self._glow = 0.5
        self._direction = 1.0

        self.setFixedSize(size, size)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFixedSize(size, size)

        logo_path = ConfigManager.get_project_root() / "assets" / "logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                pix = pix.scaled(
                    size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                self._label.setPixmap(pix)
                # Rounded background behind the logo
                self._label.setStyleSheet(
                    f"background-color: rgba(139, 92, 246, 30);"
                    f"border-radius: {size // 2}px;"
                )
            else:
                self._apply_text_fallback()
        else:
            self._apply_text_fallback()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        # Pulse via opacity effect (cheap, no stylesheet churn)
        self._effect = QGraphicsOpacityEffect(self._label)
        self._label.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.9)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    # ------------------------------------------------------------------ #
    # Fallback
    # ------------------------------------------------------------------ #
    def _apply_text_fallback(self) -> None:
        self._label.setText("EVA")
        self._label.setStyleSheet(
            f"color: {PALETTE.accent};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {int(self._size * 0.36)}px;"
            f"font-weight: {FONTS.weight_bold};"
            f"border-radius: {self._size // 2}px;"
            f"background-color: rgba(139, 92, 246, 30);"
        )

    # ------------------------------------------------------------------ #
    # Animation
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        self._glow += 0.08 * self._direction
        if self._glow >= 1.0:
            self._glow = 1.0
            self._direction = -1.0
        elif self._glow <= 0.0:
            self._glow = 0.0
            self._direction = 1.0

        # Only update the opacity effect — no stylesheet change
        opacity = 0.75 + 0.25 * self._glow
        try:
            self._effect.setOpacity(opacity)
        except RuntimeError:
            # Effect was deleted (widget closing) — stop safely
            self._timer.stop()