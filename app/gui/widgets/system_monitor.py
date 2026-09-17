"""
System monitor panel (Phase 21 — Batch 2.5B).

Three circular gauges: CPU %, RAM %, Disk %.
Updates every second using psutil.

Falls back gracefully if psutil is missing — gauges show "n/a".
"""
from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.gui.theme import FONTS, METRICS, PALETTE


try:
    import psutil  # type: ignore
    _PSUTIL = True
except Exception:  # noqa: BLE001
    psutil = None  # type: ignore
    _PSUTIL = False


def color_for_percent(percent: float) -> str:
    """Traffic-light color for a 0..100 percentage."""
    if percent < 50.0:
        return PALETTE.success
    if percent < 80.0:
        return PALETTE.warning
    return PALETTE.error


# ---------------------------------------------------------------------- #
# Single circular gauge
# ---------------------------------------------------------------------- #
class GaugeWidget(QWidget):
    """One circular gauge — label on top, value inside the ring."""

    def __init__(self, label: str, unit: str = "%", parent=None) -> None:
        super().__init__(parent)
        self._label_text = label
        self._unit = unit
        self._value: float = 0.0        # 0..100
        self._display_value: str = "--"

        # Extra height so label + circle don't overlap
        self.setMinimumSize(100, 130)

        # Only a small label at the top — the value is drawn
        # inside the circle by paintEvent.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFixedHeight(16)
        self._label.setStyleSheet(
            f"color: {PALETTE.fg_secondary};"
            f"font-family: '{FONTS.family_ui}';"
            f"font-size: {FONTS.size_xs}px;"
            f"font-weight: {FONTS.weight_medium};"
            "background: transparent;"
        )
        layout.addWidget(self._label)

        # Push everything else down so the ring gets the space below.
        layout.addStretch(1)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def set_value(self, percent: Optional[float]) -> None:
        if percent is None:
            self._display_value = "--"
            self._value = 0.0
        else:
            p = max(0.0, min(100.0, float(percent)))
            self._value = p
            self._display_value = f"{p:.0f}{self._unit}"
        self.update()

    # ------------------------------------------------------------------ #
    # Paint — draw the ring BELOW the label, value inside it
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Circle lives in the space under the label
        label_h = 20
        avail_h = max(40, self.height() - label_h - 6)
        avail_w = max(40, self.width() - 8)
        side = min(avail_w, avail_h, 78)

        cx = self.width() / 2.0
        cy = label_h + (avail_h / 2.0)
        rect = QRectF(cx - side / 2.0, cy - side / 2.0, side, side)

        # Background ring
        pen_bg = QPen(QColor(PALETTE.bg_tertiary))
        pen_bg.setWidth(6)
        pen_bg.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_bg)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        # Value arc
        if self._value > 0:
            start_angle = 225 * 16
            span_angle = -int(270 * 16 * (self._value / 100.0))
            color = QColor(color_for_percent(self._value))
            pen_val = QPen(color)
            pen_val.setWidth(6)
            pen_val.setCapStyle(Qt.RoundCap)
            painter.setPen(pen_val)
            painter.drawArc(rect, start_angle, span_angle)

        # Value text — drawn INSIDE the ring
        font = QFont(FONTS.family_ui, max(9, int(side * 0.24)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(PALETTE.fg_primary))
        painter.drawText(rect, Qt.AlignCenter, self._display_value)

        painter.end()


# ---------------------------------------------------------------------- #
# System monitor panel — 3 gauges side by side
# ---------------------------------------------------------------------- #
class SystemMonitorPanel(QWidget):
    """CPU + RAM + Disk gauges, updating every second."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        title = QLabel("System Monitor")
        title.setObjectName("StatusHeader")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(4)
        row.setAlignment(Qt.AlignCenter)

        self.cpu_gauge = GaugeWidget("CPU")
        self.ram_gauge = GaugeWidget("RAM")
        self.disk_gauge = GaugeWidget("DISK")

        row.addWidget(self.cpu_gauge)
        row.addWidget(self.ram_gauge)
        row.addWidget(self.disk_gauge)

        layout.addLayout(row)

        # Update timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        """Read live system stats and update gauges."""
        cpu, ram, disk = self.sample()
        self.cpu_gauge.set_value(cpu)
        self.ram_gauge.set_value(ram)
        self.disk_gauge.set_value(disk)

    # ------------------------------------------------------------------ #
    # Static sampler (testable)
    # ------------------------------------------------------------------ #
    @staticmethod
    def sample() -> tuple:
        """Return (cpu_percent, ram_percent, disk_percent) or (None,...)."""
        cpu = ram = disk = None

        if _PSUTIL:
            try:
                cpu = float(psutil.cpu_percent(interval=None))
            except Exception:  # noqa: BLE001
                cpu = None
            try:
                vm = psutil.virtual_memory()
                ram = float(vm.percent)
            except Exception:  # noqa: BLE001
                ram = None
            try:
                # Use the drive containing cwd; fall back to C: on Windows
                import os
                root = os.path.splitdrive(os.getcwd())[0] + "\\" if os.name == "nt" else "/"
                usage = shutil.disk_usage(root)
                disk = float(usage.used * 100.0 / usage.total)
            except Exception:  # noqa: BLE001
                disk = None
        else:
            # Minimal fallback: only disk via shutil
            try:
                usage = shutil.disk_usage("/")
                disk = float(usage.used * 100.0 / usage.total)
            except Exception:  # noqa: BLE001
                disk = None

        return cpu, ram, disk