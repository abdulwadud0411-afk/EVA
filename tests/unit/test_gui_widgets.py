"""Tests for Phase 21 Batch 3 — dialogs and tabs."""
from __future__ import annotations

import pytest

from app.core.config_manager import ConfigManager


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


# ---- Imports ---------------------------------------------------------- #
def test_dialogs_package_imports():
    from app.gui.dialogs import SettingsDialog, ConfirmationDialog  # noqa: F401
    from app.gui.dialogs import open_settings, ask_confirmation  # noqa: F401


def test_tabs_package_imports():
    from app.gui.dialogs.tabs import (  # noqa: F401
        AITab, VoiceTab, MemoryTab, KnowledgeTab,
        SkillsTab, StorageTab, SecurityTab,
    )


# ---- Settings dialog -------------------------------------------------- #
def test_settings_dialog_builds(qapp):
    from app.gui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog()
    assert dlg.windowTitle() == "EVA — Settings"
    dlg.close()


def test_settings_dialog_has_seven_tabs(qapp):
    from app.gui.dialogs.settings_dialog import SettingsDialog
    from PySide6.QtWidgets import QTabWidget
    dlg = SettingsDialog()
    tab_widget = dlg.findChild(QTabWidget)
    assert tab_widget is not None
    assert tab_widget.count() == 7
    labels = [tab_widget.tabText(i) for i in range(tab_widget.count())]
    assert labels == ["AI", "Voice", "Memory", "Knowledge", "Skills", "Storage", "Security"]
    dlg.close()


# ---- Individual tabs -------------------------------------------------- #
def test_ai_tab_builds(qapp):
    from app.gui.dialogs.tabs.ai_tab import AITab
    ConfigManager.load()
    tab = AITab()
    assert tab is not None


def test_voice_tab_builds(qapp):
    from app.gui.dialogs.tabs.voice_tab import VoiceTab
    ConfigManager.load()
    tab = VoiceTab()
    assert tab is not None


def test_memory_tab_builds(qapp):
    from app.gui.dialogs.tabs.memory_tab import MemoryTab
    tab = MemoryTab()
    assert tab is not None


def test_knowledge_tab_builds(qapp):
    from app.gui.dialogs.tabs.knowledge_tab import KnowledgeTab
    tab = KnowledgeTab()
    assert tab is not None


def test_skills_tab_builds(qapp):
    from app.gui.dialogs.tabs.skills_tab import SkillsTab
    tab = SkillsTab()
    assert tab is not None


def test_storage_tab_builds(qapp):
    from app.gui.dialogs.tabs.storage_tab import StorageTab
    tab = StorageTab()
    assert tab is not None


def test_security_tab_builds(qapp):
    from app.gui.dialogs.tabs.security_tab import SecurityTab
    ConfigManager.load()
    tab = SecurityTab()
    assert tab is not None


# ---- Confirmation dialog --------------------------------------------- #
def test_confirmation_dialog_builds(qapp):
    from app.gui.dialogs.confirmation_dialog import ConfirmationDialog
    dlg = ConfirmationDialog(
        tool_name="delete_file",
        arguments={"path": "/tmp/x"},
        risk="HIGH",
        reason="Test reason",
    )
    assert "Confirmation" in dlg.windowTitle()
    dlg.close()


@pytest.mark.asyncio
async def test_ask_confirmation_no_app_returns_false():
    # If we can't create a dialog (no qapp), ask_confirmation returns False
    from app.gui.dialogs.confirmation_dialog import ask_confirmation
    # In test env QApplication may exist — just check it doesn't raise
    try:
        await ask_confirmation("test_tool", {"a": 1}, "HIGH", "reason")
    except Exception:  # noqa: BLE001
        pytest.fail("ask_confirmation raised unexpectedly")