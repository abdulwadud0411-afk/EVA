"""
Video learner (Phase 14) — the main orchestrator.

Usage:
    from app.knowledge.learning import VideoLearner
    learner = VideoLearner()
    result = await learner.learn_from_url("https://youtube.com/watch?v=...")
    # or: await learner.learn_from_file(Path("demo.mp4"))

Result:
    {
      "title": str,
      "steps": int,
      "summary": str,
      "knowledge_id": int | None,
      "skill_saved": bool,
      "raw_video_path": str | None,
    }
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.knowledge.learning.youtube_transcript_extractor import (
    YouTubeTranscriptExtractor,
)
from app.knowledge.learning.youtube_downloader import YouTubeDownloader, DownloadError
from app.knowledge.learning.video_processor import VideoProcessor, VideoProcessError
from app.knowledge.learning.transcript_analyzer import TranscriptAnalyzer
from app.knowledge.learning.frame_analyzer import FrameAnalyzer
from app.knowledge.learning.workflow_extractor import WorkflowExtractor

logger = get_logger(__name__)


class LearningError(Exception):
    """Raised when video learning fails."""


class VideoLearner:
    def __init__(self) -> None:
        self.transcripts = YouTubeTranscriptExtractor()
        self.downloader = YouTubeDownloader()
        self.processor = VideoProcessor()
        self.stt = TranscriptAnalyzer()
        self.frames_ai = FrameAnalyzer()
        self.workflows = WorkflowExtractor()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def learn_from_url(self, url: str) -> Dict[str, Any]:
        if not ConfigManager.get("learning.enabled", True):
            raise LearningError("Learning system is disabled in config")
        if not ConfigManager.get("learning.youtube.enabled", True):
            raise LearningError("YouTube learning is disabled")

        title = f"YouTube: {url}"

        # Step 1 — try captions first
        transcript: Optional[str] = None
        if ConfigManager.get("learning.youtube.prefer_transcript_only", True):
            transcript = self.transcripts.extract(url)
            if transcript:
                logger.info("learn_using_captions", length=len(transcript))
                # No frames available without download; use transcript-only analysis
                return await self._analyze(
                    title=title,
                    transcript=transcript,
                    frames=[],
                    raw_video_path=None,
                )

        # Step 2 — download video (need frames)
        try:
            video_path = await asyncio.get_running_loop().run_in_executor(
                None, self.downloader.download_video, url,
            )
        except DownloadError as exc:
            raise LearningError(str(exc)) from exc
        if video_path is None:
            raise LearningError("Download returned no file")

        return await self._learn_from_video_file(video_path, title=title)

    async def learn_from_file(self, path: Path, title: Optional[str] = None) -> Dict[str, Any]:
        if not ConfigManager.get("learning.enabled", True):
            raise LearningError("Learning system is disabled in config")
        p = Path(path).expanduser()
        if not p.exists():
            raise LearningError(f"File not found: {p}")
        return await self._learn_from_video_file(p, title=title or p.stem)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    async def _learn_from_video_file(self, video_path: Path, title: str) -> Dict[str, Any]:
        # Step 1 — extract audio
        try:
            audio = await asyncio.get_running_loop().run_in_executor(
                None, self.processor.extract_audio, video_path,
            )
        except VideoProcessError as exc:
            raise LearningError(f"Audio extraction failed: {exc}") from exc

        # Step 2 — transcribe
        transcript = await self.stt.transcribe_audio(audio)
        transcript = self.stt.clean(transcript)
        logger.info("learn_transcript_len", length=len(transcript))

        # Step 3 — extract frames
        try:
            frames = await asyncio.get_running_loop().run_in_executor(
                None, self.processor.extract_frames, video_path,
            )
        except VideoProcessError as exc:
            logger.warning("frame_extraction_failed", error=str(exc))
            frames = []

        return await self._analyze(
            title=title,
            transcript=transcript,
            frames=frames,
            raw_video_path=video_path,
        )

    async def _analyze(
        self,
        title: str,
        transcript: str,
        frames: List[Path],
        raw_video_path: Optional[Path],
    ) -> Dict[str, Any]:
        # Step 4 — visual analysis
        visual_notes = await self.frames_ai.analyze(frames) if frames else []

        # Step 5 — workflow extraction
        workflow = await self.workflows.extract(title, transcript, visual_notes)
        if workflow is None:
            # Cleanup raw video if configured
            self._maybe_cleanup(raw_video_path, frames)
            raise LearningError("Could not extract a workflow from this source")

        # Step 6 — persist as knowledge
        knowledge_id = None
        try:
            from app.memory.memory import MemoryStore
            entry = MemoryStore.knowledge.add(
                title=workflow.get("title", title),
                content=workflow.get("summary", "") + "\n\n" + self._steps_to_text(workflow),
                source_type="video",
                source_path=str(raw_video_path) if raw_video_path else title,
                tags=["video", "workflow"],
            )
            knowledge_id = entry.id
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_knowledge_save_failed", error=str(exc))

        # Step 7 — save as skill if configured
        skill_saved = False
        if ConfigManager.get("learning.workflow.save_as_skill", True):
            try:
                from app.memory.memory import MemoryStore
                MemoryStore.skills.add(
                    name=workflow.get("title", title)[:100],
                    description=workflow.get("summary", ""),
                    steps=workflow.get("steps", []),
                    required_tools=workflow.get("required_tools", []),
                )
                skill_saved = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("workflow_skill_save_failed", error=str(exc))

        # Step 8 — cleanup raw media (Phase 11 lifecycle)
        self._maybe_cleanup(raw_video_path, frames)

        result = {
            "title": workflow.get("title", title),
            "summary": workflow.get("summary", ""),
            "steps": len(workflow.get("steps", [])),
            "knowledge_id": knowledge_id,
            "skill_saved": skill_saved,
            "raw_video_path": str(raw_video_path) if raw_video_path else None,
        }
        logger.info("video_learned", **{k: v for k, v in result.items() if k != "summary"})
        return result

    def _maybe_cleanup(self, video: Optional[Path], frames: List[Path]) -> None:
        keep_video = bool(ConfigManager.get("learning.video.keep_raw_video", False))
        keep_frames = bool(ConfigManager.get("learning.video.keep_frames", False))

        if video and not keep_video and video.exists():
            try:
                video.unlink()
                logger.info("raw_video_deleted", path=str(video))
            except OSError as exc:
                logger.warning("raw_video_delete_failed", error=str(exc))

        if frames and not keep_frames:
            for fp in frames:
                try:
                    if fp.exists():
                        fp.unlink()
                except OSError:
                    continue

    @staticmethod
    def _steps_to_text(workflow: Dict[str, Any]) -> str:
        lines = []
        for i, step in enumerate(workflow.get("steps", []), start=1):
            action = step.get("action", "")
            details = step.get("details", "")
            tool = step.get("tool_hint", "")
            line = f"{i}. {action}"
            if details:
                line += f" — {details}"
            if tool:
                line += f" [{tool}]"
            lines.append(line)
        return "\n".join(lines)