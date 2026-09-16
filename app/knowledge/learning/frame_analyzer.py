"""
Frame analyzer (Phase 14).

Sends extracted frames to the active vision provider and returns
short descriptions. Uses the existing vision infrastructure.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


class FrameAnalyzer:
    def __init__(self, max_frames_to_analyze: int = 8) -> None:
        self.max_frames = max_frames_to_analyze

    async def analyze(self, frames: List[Path]) -> List[str]:
        """Return a short description for each analyzed frame."""
        if not frames:
            return []

        try:
            from app.brain.vision import VisionClient
        except Exception as exc:  # noqa: BLE001
            logger.warning("vision_client_unavailable", error=str(exc))
            return []

        # Down-select evenly spaced frames
        picks = self._select(frames, self.max_frames)

        client = VisionClient()
        descriptions: List[str] = []
        for fp in picks:
            try:
                result = await client.analyze_image(
                    fp,
                    prompt="Briefly describe what UI/action is shown in this frame. 1-2 sentences.",
                )
                text = (result.get("text") or "").strip()
                if text:
                    descriptions.append(text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("frame_analysis_failed", frame=str(fp), error=str(exc))
                continue
        return descriptions

    @staticmethod
    def _select(frames: List[Path], n: int) -> List[Path]:
        if len(frames) <= n:
            return frames
        step = max(1, len(frames) // n)
        return frames[::step][:n]