"""
Screenshot sampler (Phase 15).

Captures a screenshot to disk whenever the demonstration recorder
fires a "key moment" event (debounced). Uses the existing
`screen_tools.capture_for_vision` for consistency.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class ScreenshotSampler:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_at: float = 0.0
        self._min_interval = float(
            ConfigManager.get("learning.demonstration.event_debounce_seconds", 0.5)
        )
        self._max_screenshots = int(
            ConfigManager.get("learning.demonstration.max_screenshots", 60)
        )
        raw = ConfigManager.get(
            "learning.demonstration.screenshot_dir",
            "./data/knowledge/demo_screenshots",
        )
        p = Path(raw)
        if not p.is_absolute():
            p = ConfigManager.get_project_root() / raw
        self.output_dir = p
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.paths: List[Path] = []

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def maybe_capture(self, reason: str = "event") -> Optional[Path]:
        """Take a screenshot if debounce window has passed. Safe to call often."""
        with self._lock:
            if len(self.paths) >= self._max_screenshots:
                return None
            now = time.time()
            if now - self._last_at < self._min_interval:
                return None
            self._last_at = now

        path = self._capture(reason)
        if path is not None:
            with self._lock:
                self.paths.append(path)
        return path

    def capture_now(self, reason: str = "manual") -> Optional[Path]:
        path = self._capture(reason)
        if path is not None:
            with self._lock:
                self.paths.append(path)
        return path

    def count(self) -> int:
        return len(self.paths)

    def as_paths(self) -> List[Path]:
        return list(self.paths)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _capture(self, reason: str) -> Optional[Path]:
        try:
            from app.tools.screen_tools import capture_for_vision
        except Exception as exc:  # noqa: BLE001
            logger.warning("screenshot_sampler_import_failed", error=str(exc))
            return None

        try:
            src = capture_for_vision()   # returns a Path (PNG)
        except Exception as exc:  # noqa: BLE001
            logger.warning("screenshot_sampler_capture_failed", error=str(exc))
            return None

        # Copy into our own folder with a reason-tagged name
        try:
            ts = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            target = self.output_dir / f"{ts}_{reason}.png"
            # move the temp file to our folder
            from shutil import move
            move(str(src), str(target))
            logger.info("screenshot_sampled", path=str(target), reason=reason)
            return target
        except Exception as exc:  # noqa: BLE001
            logger.warning("screenshot_sampler_move_failed", error=str(exc))
            return src