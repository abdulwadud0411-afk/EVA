"""
Left-side stats panel (JARVIS layout, EVA purple theme).

Cards:
    - System Stats  : CPU / RAM / Disk
    - EVA State     : Provider / Memory / Skills / Tools
    - Camera        : placeholder (no camera in EVA)
    - System Uptime : session timer + load bar
"""
from __future__ import annotations

import os
import shutil
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from app.core.logger import get_logger
from app.gui.theme import PALETTE

logger = get_logger(__name__)


try:
    import psutil
    _PSUTIL = True
except Exception:  # noqa: BLE001
    psutil = None  # type: ignore
    _PSUTIL = False


# ====================================================================== #
# Base card
# ====================================================================== #
class StatsCard(QFrame):
    """Rounded card with header."""

    def __init__(self, title: str, icon: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatsCard")
        self.setStyleSheet(f"""
            QFrame#StatsCard {{
                background-color: {PALETTE.bg_primary};
                border: 1px solid {PALETTE.border};
                border-radius: 12px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 14)
        self._layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)

        if icon:
            ic = QLabel(icon)
            ic.setStyleSheet(
                f"color: {PALETTE.accent}; font-size: 13px; background: transparent;"
            )
            header.addWidget(ic)

        ttl = QLabel(title.upper())
        ttl.setStyleSheet(
            f"color: {PALETTE.fg_primary};"
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"letter-spacing: 0.8px;"
            f"background: transparent;"
        )
        header.addWidget(ttl)
        header.addStretch(1)

        self._layout.addLayout(header)

    def add_widget(self, w: "QWidget") -> None:
        self._layout.addWidget(w)

    def add_layout(self, l) -> None:
        self._layout.addLayout(l)


class LabeledBar(QFrame):
    """Label + value + horizontal progress bar."""

    def __init__(self, label: str, unit: str = "%", parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._name = QLabel(label)
        self._name.setStyleSheet(
            f"color: {PALETTE.fg_secondary}; font-size: 11px; background: transparent;"
        )
        self._value = QLabel("--")
        self._value.setStyleSheet(
            f"color: {PALETTE.fg_primary}; font-size: 11px;"
            f"font-weight: 600; background: transparent;"
        )
        row.addWidget(self._name)
        row.addStretch(1)
        row.addWidget(self._value)
        lay.addLayout(row)

        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setRange(0, 100)
        self._bar.setFixedHeight(6)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PALETTE.bg_tertiary};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {PALETTE.accent};
                border-radius: 3px;
            }}
        """)
        lay.addWidget(self._bar)
        self._unit = unit

    def set_value(self, value) -> None:
        if value is None:
            self._value.setText("--")
            self._bar.setValue(0)
            return
        try:
            v = max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return
        self._value.setText(f"{v:.0f}{self._unit}")
        self._bar.setValue(int(v))


def _make_mini_box(label: str, value: str = "--") -> QFrame:
    """Small box with label + value."""
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background-color: {PALETTE.bg_tertiary};
            border-radius: 6px;
        }}
    """)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(6, 6, 6, 6)
    lay.setSpacing(2)

    lbl = QLabel(label)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"color: {PALETTE.fg_muted}; font-size: 9px; background: transparent;"
    )

    val = QLabel(value)
    val.setAlignment(Qt.AlignCenter)
    val.setStyleSheet(
        f"color: {PALETTE.fg_primary}; font-size: 12px;"
        f"font-weight: 700; background: transparent;"
    )

    lay.addWidget(lbl)
    lay.addWidget(val)
    f._value_label = val  # type: ignore[attr-defined]
    return f


# ====================================================================== #
# System Stats
# ====================================================================== #
class SystemStatsCard(StatsCard):
    def __init__(self, parent=None) -> None:
        super().__init__("System Stats", "▣", parent)
        self.cpu_bar = LabeledBar("CPU Usage")
        self.ram_bar = LabeledBar("RAM Usage")
        self.add_widget(self.cpu_bar)
        self.add_widget(self.ram_bar)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._cpu_box = _make_mini_box("CPU", "--")
        self._mem_box = _make_mini_box("Memory", "--")
        self._disk_box = _make_mini_box("Disk", "--")
        row.addWidget(self._cpu_box)
        row.addWidget(self._mem_box)
        row.addWidget(self._disk_box)
        self.add_layout(row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _refresh(self) -> None:
        try:
            if _PSUTIL:
                cpu = float(psutil.cpu_percent(interval=None))
                ram = float(psutil.virtual_memory().percent)
            else:
                cpu, ram = 0.0, 0.0
            root = os.path.splitdrive(os.getcwd())[0] + "\\" if os.name == "nt" else "/"
            usage = shutil.disk_usage(root)
            disk = usage.used * 100.0 / max(1, usage.total)

            self.cpu_bar.set_value(cpu)
            self.ram_bar.set_value(ram)
            self._cpu_box._value_label.setText(f"{cpu:.0f}%")
            self._mem_box._value_label.setText(f"{ram:.0f}%")
            self._disk_box._value_label.setText(f"{disk:.0f}%")
        except Exception as exc:
            logger.warning("stats_refresh_failed", error=str(exc))


# ====================================================================== #
# EVA State
# ====================================================================== #
class EvaStateCard(StatsCard):
    def __init__(self, parent=None) -> None:
        super().__init__("EVA State", "●", parent)

        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel("AI Provider")
        lbl.setStyleSheet(
            f"color: {PALETTE.fg_secondary}; font-size: 11px; background: transparent;"
        )
        self._provider = QLabel("deepseek")
        self._provider.setStyleSheet(
            f"color: {PALETTE.fg_primary}; font-size: 11px;"
            f"font-weight: 600; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(self._provider)
        self.add_layout(row)

        box_row = QHBoxLayout()
        box_row.setSpacing(6)
        self._mem_box = _make_mini_box("Memory", "0")
        self._skill_box = _make_mini_box("Skills", "0")
        self._tool_box = _make_mini_box("Tools", "0")
        box_row.addWidget(self._mem_box)
        box_row.addWidget(self._skill_box)
        box_row.addWidget(self._tool_box)
        self.add_layout(box_row)

        health_row = QHBoxLayout()
        h_lbl = QLabel("Health")
        h_lbl.setStyleSheet(
            f"color: {PALETTE.fg_secondary}; font-size: 11px; background: transparent;"
        )
        self._health = QLabel("● OK")
        self._health.setStyleSheet(
            f"color: {PALETTE.success}; font-size: 11px;"
            f"font-weight: 700; background: transparent;"
        )
        health_row.addWidget(h_lbl)
        health_row.addStretch(1)
        health_row.addWidget(self._health)
        self.add_layout(health_row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)
        self._refresh()

    def _refresh(self) -> None:
        try:
            from app.core.config_manager import ConfigManager
            from app.tools.registry import ToolRegistry

            prov = str(ConfigManager.get("ai.provider", "deepseek"))
            self._provider.setText(prov)

            try:
                tools = len(ToolRegistry.list_tools())
            except Exception:
                tools = 0
            self._tool_box._value_label.setText(str(tools))

            mem = 0
            skills = 0
            try:
                from app.memory.database import Database
                row = Database.fetchone("SELECT COUNT(*) AS c FROM knowledge_entries")
                mem = int(row["c"] or 0) if row else 0
                row = Database.fetchone("SELECT COUNT(*) AS c FROM skills")
                skills = int(row["c"] or 0) if row else 0
            except Exception:
                pass
            self._mem_box._value_label.setText(str(mem))
            self._skill_box._value_label.setText(str(skills))
        except Exception as exc:
            logger.warning("state_refresh_failed", error=str(exc))


# ====================================================================== #
# Camera placeholder
# ====================================================================== #
class CameraCard(StatsCard):
    def __init__(self, parent=None) -> None:
        super().__init__("Camera", "◉", parent)
        preview = QFrame()
        preview.setMinimumHeight(110)
        preview.setStyleSheet(f"""
            QFrame {{
                background-color: {PALETTE.bg_tertiary};
                border-radius: 8px;
                border: 1px dashed {PALETTE.border};
            }}
        """)
        lay = QVBoxLayout(preview)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(4)

        icon = QLabel("📷")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 24px; background: transparent;")

        text = QLabel("Camera Off")
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet(
            f"color: {PALETTE.fg_muted}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(icon)
        lay.addWidget(text)
        self.add_widget(preview)


# ====================================================================== #
# Uptime
# ====================================================================== #
class UptimeCard(StatsCard):
    def __init__(self, parent=None) -> None:
        super().__init__("System Uptime", "⏱", parent)
        self._start = time.time()

        row = QHBoxLayout()
        lbl = QLabel("Running For:")
        lbl.setStyleSheet(
            f"color: {PALETTE.fg_secondary}; font-size: 11px; background: transparent;"
        )
        self._timer_lbl = QLabel("00:00:00")
        self._timer_lbl.setStyleSheet(
            f"color: {PALETTE.fg_primary}; font-size: 13px;"
            f"font-weight: 700; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(self._timer_lbl)
        self.add_layout(row)

        box_row = QHBoxLayout()
        box_row.setSpacing(6)
        self._sess_box = _make_mini_box("Session", "1")
        self._cmd_box = _make_mini_box("Commands", "0")
        box_row.addWidget(self._sess_box)
        box_row.addWidget(self._cmd_box)
        self.add_layout(box_row)

        self._load_bar = LabeledBar("System Load")
        self.add_widget(self._load_bar)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)
        self._tick()

    def _tick(self) -> None:
        elapsed = int(time.time() - self._start)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self._timer_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")
        try:
            if _PSUTIL:
                self._load_bar.set_value(float(psutil.cpu_percent(interval=None)))
        except Exception:
            pass


# ====================================================================== #
# Left sidebar — all 4 cards stacked
# ====================================================================== #
class LeftSidebar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet("background: transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.system_stats = SystemStatsCard()
        self.eva_state = EvaStateCard()
        self.camera = CameraCard()
        self.uptime = UptimeCard()

        lay.addWidget(self.system_stats)
        lay.addWidget(self.eva_state)
        lay.addWidget(self.camera)
        lay.addWidget(self.uptime)
        lay.addStretch(1)