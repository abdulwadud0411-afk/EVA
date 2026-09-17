"""Tests for Phase 21 Batch 2.5B InfoPanel + ClockWidget."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.config_manager import ConfigManager


# ---------------------------------------------------------------------- #
# Clock formatters (pure, no Qt)
# ---------------------------------------------------------------------- #
def test_clock_format_time_morning():
    from app.gui.widgets.clock_widget import ClockWidget
    dt = datetime(2026, 9, 17, 9, 5, 3)
    assert ClockWidget.format_time(dt) == "9:05:03 AM"


def test_clock_format_time_afternoon():
    from app.gui.widgets.clock_widget import ClockWidget
    dt = datetime(2026, 9, 17, 14, 30, 45)
    assert ClockWidget.format_time(dt) == "2:30:45 PM"


def test_clock_format_time_midnight():
    from app.gui.widgets.clock_widget import ClockWidget
    dt = datetime(2026, 9, 17, 0, 0, 0)
    assert ClockWidget.format_time(dt) == "12:00:00 AM"


def test_clock_format_date():
    from app.gui.widgets.clock_widget import ClockWidget
    dt = datetime(2026, 9, 17)
    # 17 Sep 2026 is a Thursday
    assert "September" in ClockWidget.format_date(dt)
    assert "2026" in ClockWidget.format_date(dt)
    assert "17" in ClockWidget.format_date(dt)


# ---------------------------------------------------------------------- #
# Info panel data gatherer (pure, no Qt)
# ---------------------------------------------------------------------- #
def test_info_panel_gather_returns_dict():
    from app.gui.widgets.info_panel import InfoPanel
    data = InfoPanel.gather()
    assert "memory" in data
    assert "skills" in data
    assert "tools" in data
    assert "provider" in data
    assert "health" in data


def test_info_panel_gather_types():
    from app.gui.widgets.info_panel import InfoPanel
    data = InfoPanel.gather()
    assert isinstance(data["memory"], int)
    assert isinstance(data["skills"], int)
    assert isinstance(data["tools"], int)
    assert isinstance(data["provider"], str)
    assert isinstance(data["health"], str)


def test_info_panel_gather_provider_from_config():
    from app.gui.widgets.info_panel import InfoPanel
    ConfigManager.load()
    ConfigManager.set("ai.provider", "deepseek", persist=False)
    data = InfoPanel.gather()
    assert data["provider"] == "deepseek"


def test_info_panel_health_ok_when_config_available():
    from app.gui.widgets.info_panel import InfoPanel
    ConfigManager.load()
    data = InfoPanel.gather()
    assert data["health"] == "OK"


# ---------------------------------------------------------------------- #
# Qt widget tests
# ---------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


def test_clock_widget_builds(qapp):
    from app.gui.widgets.clock_widget import ClockWidget
    w = ClockWidget()
    # After construction, labels have been populated
    assert w._time_label.text() != "--:--:--"
    assert w._date_label.text() != "--"


def test_info_panel_builds(qapp):
    from app.gui.widgets.info_panel import InfoPanel
    ConfigManager.load()
    panel = InfoPanel()
    # Refresh is safe and populates rows
    panel.refresh()
    assert panel._row_provider._value.text() != ""


def test_info_panel_row_set_value(qapp):
    from app.gui.widgets.info_panel import _InfoRow
    row = _InfoRow("Test")
    row.set_value("42")
    assert row._value.text() == "42"