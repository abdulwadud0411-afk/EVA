"""
Panic button (Phase 10).

Registers a global keyboard shortcut (default: Ctrl+Shift+Q) that stops
EVA immediately: cancels TTS, aborts the agent loop, and disables the
call button state.

Uses pywin32 on Windows; falls back silently on other platforms.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class PanicButton:
    """
    Global hotkey listener that triggers a callback on panic.

    Implementation uses the Windows `RegisterHotKey` API via pywin32.
    """

    def __init__(self, on_panic: Optional[Callable[[], None]] = None) -> None:
        self.enabled = bool(ConfigManager.get("voice.panic.enabled", True))
        self.hotkey = str(ConfigManager.get("voice.panic.hotkey", "ctrl+shift+q")).lower()
        self.on_panic = on_panic

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        if not self.enabled:
            logger.info("panic_disabled")
            return False
        if self._running:
            return True

        self._stop_flag.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, name="eva-panic", daemon=True,
        )
        self._thread.start()
        logger.info("panic_started", hotkey=self.hotkey)
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("panic_stopped")

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _parse_hotkey(self):
        """
        Return (modifiers, vk_code) for RegisterHotKey, or (None, None).
        """
        parts = [p.strip() for p in self.hotkey.split("+") if p.strip()]
        mods = 0
        vk = None

        # MOD_ALT=0x0001, MOD_CONTROL=0x0002, MOD_SHIFT=0x0004, MOD_WIN=0x0008
        for p in parts:
            if p == "ctrl" or p == "control":
                mods |= 0x0002
            elif p == "alt":
                mods |= 0x0001
            elif p == "shift":
                mods |= 0x0004
            elif p == "win":
                mods |= 0x0008
            elif len(p) == 1 and p.isalpha():
                vk = ord(p.upper())
            elif p.startswith("f") and p[1:].isdigit():
                vk = 0x70 + (int(p[1:]) - 1)  # VK_F1..VK_F24
        return mods, vk

    def _listen_loop(self) -> None:
        try:
            import win32con  # type: ignore
            import win32gui  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.warning("panic_pywin32_missing", error=str(exc))
            self._running = False
            return

        mods, vk = self._parse_hotkey()
        if vk is None:
            logger.error("panic_hotkey_invalid", hotkey=self.hotkey)
            self._running = False
            return

        HOTKEY_ID = 0xE7A1
        try:
            win32gui.RegisterHotKey(None, HOTKEY_ID, mods, vk)
        except Exception as exc:  # noqa: BLE001
            logger.error("panic_register_hotkey_failed", error=str(exc))
            self._running = False
            return

        # Message pump
        try:
            while not self._stop_flag.is_set():
                # Peek for hotkey messages (non-blocking)
                try:
                    msg = win32gui.GetMessage(None, 0, 0)
                except Exception:
                    break
                if not msg:
                    time.sleep(0.05)
                    continue
                msg_id = msg[1]
                if msg_id == win32con.WM_HOTKEY:
                    self._fire()
                    # small delay so user sees feedback
                    time.sleep(0.1)
        finally:
            try:
                win32gui.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:  # noqa: BLE001
                pass
            self._running = False

    def _fire(self) -> None:
        logger.warning("panic_fired", hotkey=self.hotkey)
        if self.on_panic is not None:
            try:
                self.on_panic()
            except Exception as exc:  # noqa: BLE001
                logger.error("panic_callback_failed", error=str(exc))