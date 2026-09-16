"""
Live demonstration recorder (Phase 15).

Full session orchestrator:

    >>> recorder.start()
    ... user works ...
    >>> recorder.stop()          # returns dict

Combines:
    - ActionLogger (input events)
    - ScreenshotSampler (event-triggered screenshots)
    - DemonstrationLearner (workflow extraction + skill save)

Keeps memory footprint bounded: max_events, max_screenshots,
max_session_minutes. Auto-stops when the session exceeds the limit.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.events import Event, EventBus
from app.core.logger import get_logger
from app.knowledge.learning.action_logger import ActionEvent, ActionLogger
from app.knowledge.learning.screenshot_sampler import ScreenshotSampler
from app.knowledge.learning.demonstration_learner import DemonstrationLearner

logger = get_logger(__name__)


class LiveRecorderError(Exception):
    """Raised when a live recording session fails."""


class LiveRecorder:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()
        self.action_logger = ActionLogger()
        self.screenshots = ScreenshotSampler()
        self.learner = DemonstrationLearner()

        self._running = False
        self._auto_stop_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._started_at: float = 0.0
        self._max_minutes = int(
            ConfigManager.get("learning.demonstration.max_session_minutes", 15)
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        if self._running:
            return True
        if not ConfigManager.get("learning.demonstration.enabled", True):
            raise LiveRecorderError("Demonstration learning is disabled")

        ok = self.action_logger.start()
        if not ok:
            raise LiveRecorderError("Could not start action logger")

        # Take an initial screenshot so we know the starting context
        self.screenshots.capture_now(reason="start")

        self._running = True
        self._stop_flag.clear()
        self._started_at = time.time()

        # Background auto-stop safety
        self._auto_stop_thread = threading.Thread(
            target=self._auto_stop_loop,
            name="eva-live-recorder-autostop",
            daemon=True,
        )
        self._auto_stop_thread.start()

        self.event_bus.publish(Event("DEMO_RECORDING_STARTED", {
            "max_minutes": self._max_minutes,
        }))
        logger.info("live_recorder_started", max_minutes=self._max_minutes)
        return True

    async def stop_and_learn(
        self,
        title: Optional[str] = None,
        auto_save_skill: bool = True,
    ) -> Dict[str, Any]:
        """
        Stop recording, extract a skill, and (optionally) save it.
        Returns a dict with the skill or an error.
        """
        if not self._running:
            raise LiveRecorderError("Recorder is not running")

        # Capture one final screenshot
        self.screenshots.capture_now(reason="stop")

        events: List[ActionEvent] = self.action_logger.stop()
        self._running = False
        self._stop_flag.set()

        duration_s = time.time() - self._started_at
        self.event_bus.publish(Event("DEMO_RECORDING_STOPPED", {
            "events": len(events),
            "screenshots": self.screenshots.count(),
            "duration_s": round(duration_s, 1),
        }))

        logger.info(
            "live_recorder_stopped",
            events=len(events),
            screenshots=self.screenshots.count(),
        )

        if not events:
            return {
                "success": False,
                "error": "No actions captured",
                "events": 0,
                "screenshots": self.screenshots.count(),
            }

        # Ask the learner to produce a skill
        try:
            skill = await self.learner.learn_from_actions(
                events=events,
                screenshot_paths=self.screenshots.as_paths(),
                title=title,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("live_recorder_learn_failed", error=str(exc))
            return {
                "success": False,
                "error": str(exc),
                "events": len(events),
                "screenshots": self.screenshots.count(),
            }

        return {
            "success": True,
            "skill": skill.to_dict(),
            "events": len(events),
            "screenshots": self.screenshots.count(),
            "duration_s": round(duration_s, 1),
        }

    def cancel(self) -> None:
        """Abort recording without learning."""
        if not self._running:
            return
        self.action_logger.stop()
        self._running = False
        self._stop_flag.set()
        self.event_bus.publish(Event("DEMO_RECORDING_CANCELLED", {}))
        logger.info("live_recorder_cancelled")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------ #
    # Auto-stop
    # ------------------------------------------------------------------ #
    def _auto_stop_loop(self) -> None:
        limit_s = self._max_minutes * 60
        while not self._stop_flag.is_set():
            if time.time() - self._started_at >= limit_s:
                logger.warning("live_recorder_auto_stop", limit_minutes=self._max_minutes)
                # Best-effort: just stop the hooks (learning must be done by caller)
                try:
                    self.action_logger.stop()
                except Exception:  # noqa: BLE001
                    pass
                self._running = False
                self.event_bus.publish(Event("DEMO_RECORDING_AUTO_STOPPED", {
                    "reason": "max_session_minutes",
                }))
                return
            time.sleep(1.0)