"""
System tray integration (Phase 21).

Adds a tray icon with menu:
    - Show / hide dashboard
    - Start / pause listening
    - Settings (opens settings dialog)
    - Exit
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class TrayController:
    """Attach a QSystemTrayIcon to a MainWindow."""

    def __init__(
        self,
        window,
        on_settings: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        parent=None,
    ) -> None:
        self.window = window
        self.on_settings = on_settings
        self.on_quit = on_quit

        enabled = bool(ConfigManager.get("gui.tray.enabled", True))
        self.tray: Optional[QSystemTrayIcon] = None
        if not enabled:
            return

        icon_path = ConfigManager.get_project_root() / "assets" / "icon.ico"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QIcon()  # empty icon

        self.tray = QSystemTrayIcon(icon, parent or window)
        self.tray.setToolTip("EVA — Personal AI Assistant")

        menu = QMenu()

        act_show = QAction("Show dashboard", menu)
        act_show.triggered.connect(self._show_window)
        menu.addAction(act_show)

        act_hide = QAction("Hide dashboard", menu)
        act_hide.triggered.connect(self._hide_window)
        menu.addAction(act_hide)

        menu.addSeparator()

        act_pause = QAction("Pause listening", menu)
        act_pause.triggered.connect(self._pause_listening)
        menu.addAction(act_pause)

        act_resume = QAction("Resume listening", menu)
        act_resume.triggered.connect(self._resume_listening)
        menu.addAction(act_resume)

        menu.addSeparator()

        act_settings = QAction("Settings…", menu)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)

        menu.addSeparator()

        act_quit = QAction("Exit", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def show(self) -> None:
        if self.tray is not None:
            self.tray.show()

    def hide(self) -> None:
        if self.tray is not None:
            self.tray.hide()

    def _show_window(self) -> None:
        try:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()
        except Exception as exc:  # noqa: BLE001
            logger.warning("tray_show_failed", error=str(exc))

    def _hide_window(self) -> None:
        try:
            self.window.hide()
        except Exception:  # noqa: BLE001
            pass

    def _pause_listening(self) -> None:
        try:
            controller = getattr(self.window, "controller", None)
            if controller is not None and controller.state.status.value == "LISTENING":
                import asyncio
                asyncio.run(controller.toggle_listening())
        except Exception as exc:  # noqa: BLE001
            logger.warning("tray_pause_failed", error=str(exc))

    def _resume_listening(self) -> None:
        try:
            controller = getattr(self.window, "controller", None)
            if controller is not None and controller.state.status.value != "LISTENING":
                import asyncio
                asyncio.run(controller.toggle_listening())
        except Exception as exc:  # noqa: BLE001
            logger.warning("tray_resume_failed", error=str(exc))

    def _open_settings(self) -> None:
        if self.on_settings is not None:
            try:
                self.on_settings()
            except Exception as exc:  # noqa: BLE001
                logger.warning("tray_settings_failed", error=str(exc))

    def _quit(self) -> None:
        try:
            if self.on_quit is not None:
                self.on_quit()
            else:
                from PySide6.QtWidgets import QApplication
                QApplication.quit()
        except Exception:  # noqa: BLE001
            pass

    def _on_activated(self, reason) -> None:
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            if reason in (
                QSystemTrayIcon.Trigger,
                QSystemTrayIcon.DoubleClick,
            ):
                if self.window.isVisible():
                    self._hide_window()
                else:
                    self._show_window()
        except Exception:  # noqa: BLE001
            pass