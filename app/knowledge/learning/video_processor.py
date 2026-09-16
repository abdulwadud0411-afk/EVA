"""
Video processor (Phase 14).

Uses ffmpeg to:
    - Extract audio track (for STT)
    - Extract frames at intervals (for Vision)
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger

logger = get_logger(__name__)


class VideoProcessError(Exception):
    """Raised when ffmpeg processing fails."""


def _ffmpeg_path() -> Optional[str]:
    from shutil import which
    config = ConfigManager.get("integrations.common.ffmpeg_path", "auto")
    if config and config != "auto":
        p = Path(str(config))
        if p.exists():
            return str(p)
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = which(name)
        if found:
            return found
    return None


class VideoProcessor:
    def __init__(self) -> None:
        self.frames_dir = self._resolve_dir("learning.video.frames_dir", "./data/knowledge/frames")
        self.transcript_dir = self._resolve_dir("learning.video.transcript_dir", "./data/knowledge/transcripts")
        self.frames_per_minute = int(ConfigManager.get("learning.video.frames_per_minute", 2))
        self.max_frames = int(ConfigManager.get("learning.video.max_frames", 40))

    @staticmethod
    def _resolve_dir(key: str, default: str) -> Path:
        raw = ConfigManager.get(key, default)
        p = Path(raw)
        if not p.is_absolute():
            p = ConfigManager.get_project_root() / raw
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def extract_audio(self, video_path: Path) -> Path:
        """Convert video to 16 kHz mono WAV (Whisper-friendly)."""
        ff = _ffmpeg_path()
        if not ff:
            raise VideoProcessError("ffmpeg not found on PATH.")
        out = self.transcript_dir / (video_path.stem + ".wav")
        args = [
            ff, "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            str(out),
        ]
        try:
            subprocess.run(
                args, capture_output=True, text=True, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise VideoProcessError("ffmpeg audio extraction timed out")
        if not out.exists():
            raise VideoProcessError("Audio extraction produced no output")
        return out

    def extract_frames(self, video_path: Path) -> List[Path]:
        """Extract frames at fixed interval (frames_per_minute)."""
        ff = _ffmpeg_path()
        if not ff:
            raise VideoProcessError("ffmpeg not found on PATH.")

        # Get duration
        duration_s = self._get_duration(video_path)
        if duration_s is None:
            raise VideoProcessError("Could not read video duration")

        interval = max(1, int(60 / max(1, self.frames_per_minute)))
        est_frames = min(self.max_frames, max(2, int(duration_s / interval)))

        out_dir = self.frames_dir / video_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        pattern = out_dir / "frame_%04d.png"

        # -vf fps=1/interval
        vf = f"fps=1/{interval}"
        args = [
            ff, "-y", "-i", str(video_path),
            "-vf", vf,
            "-frames:v", str(est_frames),
            str(pattern),
        ]
        try:
            subprocess.run(
                args, capture_output=True, text=True, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise VideoProcessError("ffmpeg frame extraction timed out")

        frames = sorted(out_dir.glob("frame_*.png"))
        logger.info("frames_extracted", count=len(frames), dir=str(out_dir))
        return frames

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _get_duration(self, path: Path) -> Optional[float]:
        ffprobe = None
        from shutil import which
        for name in ("ffprobe", "ffprobe.exe"):
            found = which(name)
            if found:
                ffprobe = found
                break
        if not ffprobe:
            return None
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries",
                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                 str(path)],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return float((r.stdout or "0").strip())
        except Exception:  # noqa: BLE001
            return None