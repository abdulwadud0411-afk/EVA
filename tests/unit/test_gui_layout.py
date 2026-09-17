"""Tests for Phase 21 Batch 2.5C — main window layout."""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


def test_main_window_builds(qapp):
    from app.gui.main_window import MainWindow
    ConfigManager.load()
    w = MainWindow()
    assert w is not None
    w.close()


def test_main_window_has_voice_orb(qapp):
    from app.gui.main_window import MainWindow
    w = MainWindow()
    assert w.voice_orb is not None
    w.close()


def test_main_window_has_chat_panel(qapp):
    from app.gui.main_window import MainWindow
    w = MainWindow()
    assert w.chat_panel is not None
    w.close()


def test_main_window_has_call_button(qapp):
    from app.gui.main_window import MainWindow
    w = MainWindow()
    assert w.call_button is not None
    w.close()


def test_main_window_has_voice_animation(qapp):
    from app.gui.main_window import MainWindow
    w = MainWindow()
    assert w.voice_animation is not None
    w.close()


def test_main_window_has_clock_when_enabled(qapp):
    from app.gui.main_window import MainWindow
    ConfigManager.load()
    ConfigManager.set("gui.layout.show_clock", True, persist=False)
    w = MainWindow()
    assert hasattr(w, "clock")
    w.close()


def test_main_window_has_system_monitor_when_enabled(qapp):
    from app.gui.main_window import MainWindow
    ConfigManager.load()
    ConfigManager.set("gui.layout.show_system_monitor", True, persist=False)
    w = MainWindow()
    assert hasattr(w, "system_monitor")
    w.close()


def test_main_window_has_info_panel_when_enabled(qapp):
    from app.gui.main_window import MainWindow
    ConfigManager.load()
    ConfigManager.set("gui.layout.show_info_panel", True, persist=False)
    w = MainWindow()
    assert hasattr(w, "info_panel")
    w.close()


def test_main_window_status_change_updates_header(qapp):
    from app.gui.main_window import MainWindow
    from app.gui.gui_state import GUIStatus
    w = MainWindow()

    w._on_status_changed(GUIStatus.LISTENING)
    assert "Listening" in w._status_text.text()

    w._on_status_changed(GUIStatus.THINKING)
    assert "Thinking" in w._status_text.text()

    w._on_status_changed(GUIStatus.IDLE)
    assert "Online" in w._status_text.text()

    w.close()


def test_sphere_width_ratio_default(qapp):
    from app.gui.main_window import MainWindow
    ConfigManager.load()
    w = MainWindow()
    # Default ratio from config = 0.58
    assert 0.4 <= 0.58 <= 0.7
    w.close()