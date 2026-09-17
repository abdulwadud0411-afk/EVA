"""Tests for Phase 21 Batch 2.5B SystemMonitor."""
from __future__ import annotations

import pytest

from app.gui.theme import PALETTE


# ---------------------------------------------------------------------- #
# Pure logic — color mapping (no Qt needed)
# ---------------------------------------------------------------------- #
def test_color_green_under_50():
    from app.gui.widgets.system_monitor import color_for_percent
    assert color_for_percent(0.0) == PALETTE.success
    assert color_for_percent(25.0) == PALETTE.success
    assert color_for_percent(49.9) == PALETTE.success


def test_color_yellow_between_50_and_80():
    from app.gui.widgets.system_monitor import color_for_percent
    assert color_for_percent(50.0) == PALETTE.warning
    assert color_for_percent(65.0) == PALETTE.warning
    assert color_for_percent(79.9) == PALETTE.warning


def test_color_red_at_80_and_above():
    from app.gui.widgets.system_monitor import color_for_percent
    assert color_for_percent(80.0) == PALETTE.error
    assert color_for_percent(95.0) == PALETTE.error
    assert color_for_percent(100.0) == PALETTE.error


# ---------------------------------------------------------------------- #
# Data sampler (no Qt needed)
# ---------------------------------------------------------------------- #
def test_sample_returns_three_values():
    from app.gui.widgets.system_monitor import SystemMonitorPanel
    cpu, ram, disk = SystemMonitorPanel.sample()
    # Each is either None or a float in 0..100
    for v in (cpu, ram, disk):
        assert v is None or (isinstance(v, float) and 0.0 <= v <= 100.0)


def test_sample_disk_available_even_without_psutil(monkeypatch):
    import app.gui.widgets.system_monitor as sm
    monkeypatch.setattr(sm, "_PSUTIL", False)
    monkeypatch.setattr(sm, "psutil", None)
    cpu, ram, disk = sm.SystemMonitorPanel.sample()
    # CPU and RAM unavailable without psutil
    assert cpu is None
    assert ram is None
    # Disk should still work via shutil
    assert disk is not None
    assert 0.0 <= disk <= 100.0


# ---------------------------------------------------------------------- #
# Qt widget tests
# ---------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


def test_gauge_widget_initial_state(qapp):
    from app.gui.widgets.system_monitor import GaugeWidget
    g = GaugeWidget("CPU")
    assert g._value == 0.0
    assert g._display_value == "--"


def test_gauge_widget_set_value(qapp):
    from app.gui.widgets.system_monitor import GaugeWidget
    g = GaugeWidget("RAM")
    g.set_value(42.4)              # rounds down to "42"
    assert 42.0 <= g._value <= 43.0
    assert "42" in g._display_value
    assert "%" in g._display_value


def test_gauge_widget_rounds_correctly(qapp):
    from app.gui.widgets.system_monitor import GaugeWidget
    g = GaugeWidget("RAM")

    g.set_value(42.4)
    assert g._display_value == "42%"

    g.set_value(42.7)              # rounds up
    assert g._display_value == "43%"

    g.set_value(0.0)
    assert g._display_value == "0%"

    g.set_value(100.0)
    assert g._display_value == "100%"


def test_gauge_widget_clamps_high(qapp):
    from app.gui.widgets.system_monitor import GaugeWidget
    g = GaugeWidget("CPU")
    g.set_value(150.0)
    assert g._value == 100.0


def test_gauge_widget_clamps_low(qapp):
    from app.gui.widgets.system_monitor import GaugeWidget
    g = GaugeWidget("CPU")
    g.set_value(-10.0)
    assert g._value == 0.0


def test_gauge_widget_none_shows_dash(qapp):
    from app.gui.widgets.system_monitor import GaugeWidget
    g = GaugeWidget("CPU")
    g.set_value(None)
    assert g._display_value == "--"


def test_system_monitor_panel_has_three_gauges(qapp):
    from app.gui.widgets.system_monitor import SystemMonitorPanel
    panel = SystemMonitorPanel()
    assert panel.cpu_gauge is not None
    assert panel.ram_gauge is not None
    assert panel.disk_gauge is not None


def test_system_monitor_panel_refresh(qapp):
    from app.gui.widgets.system_monitor import SystemMonitorPanel
    panel = SystemMonitorPanel()
    panel.refresh()  # should not raise
    # Every gauge value is 0..100
    for g in (panel.cpu_gauge, panel.ram_gauge, panel.disk_gauge):
        assert 0.0 <= g._value <= 100.0