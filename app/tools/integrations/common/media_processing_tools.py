"""
Media processing tools (Common).

Uses the free, open-source ffmpeg CLI. ffmpeg is not bundled with EVA;
the user must install it separately (or place it under a known path).

Tools:
    - ffmpeg_convert       : convert video/audio to another format
    - ffmpeg_extract_audio : pull audio out of a video file
    - ffmpeg_trim          : cut a clip by start/end time
    - ffmpeg_concat        : join multiple media files
    - ffmpeg_thumbnail     : extract a thumbnail frame
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, List, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists, media_file_valid

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# ffmpeg lookup
# ---------------------------------------------------------------------- #
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


def _run_ffmpeg(args: List[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    ff = _ffmpeg_path()
    if not ff:
        raise RuntimeError("ffmpeg not found on PATH.")
    cmd = [ff, "-y"] + args
    logger.info("ffmpeg_run", args=args[:6])  # log only first few
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if __import__("os").name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: ffmpeg_convert
# ---------------------------------------------------------------------- #
class FfmpegConvertTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "ffmpeg_convert"
    description = "Convert a video or audio file to another format using ffmpeg."
    parameters = {
        "type": "object",
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "extra_args": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["input_path", "output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        inp = Path(str(kwargs.get("input_path", ""))).expanduser()
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        if not inp.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INPUT_NOT_FOUND", "message": str(inp)},
            )
        out.parent.mkdir(parents=True, exist_ok=True)

        extra: List[str] = list(kwargs.get("extra_args") or [])
        args = ["-i", str(inp)] + extra + [str(out)]

        try:
            result = _run_ffmpeg(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FFMPEG_FAILED", "message": str(exc)},
            )

        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=result.returncode == 0 and check["verified"],
            tool=self.name,
            data={
                "output": str(out),
                "returncode": result.returncode,
                "size": check.get("size"),
                "stderr_tail": (result.stderr or "")[-800:],
            },
            error=None if check["verified"] else {"code": "OUTPUT_MISSING", "message": "No output produced."},
        )


# ---------------------------------------------------------------------- #
# Tool: ffmpeg_extract_audio
# ---------------------------------------------------------------------- #
class FfmpegExtractAudioTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "ffmpeg_extract_audio"
    description = "Extract the audio track from a video file."
    parameters = {
        "type": "object",
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "format": {"type": "string"},
        },
        "required": ["input_path", "output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        inp = Path(str(kwargs.get("input_path", ""))).expanduser()
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        if not inp.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INPUT_NOT_FOUND", "message": str(inp)},
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        fmt = str(kwargs.get("format") or out.suffix.lstrip(".") or "mp3").lower()

        args = ["-i", str(inp), "-vn", "-acodec", "libmp3lame" if fmt == "mp3" else "copy", str(out)]
        try:
            result = _run_ffmpeg(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FFMPEG_FAILED", "message": str(exc)},
            )

        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=result.returncode == 0 and check["verified"],
            tool=self.name,
            data={"output": str(out), "size": check.get("size")},
        )


# ---------------------------------------------------------------------- #
# Tool: ffmpeg_trim
# ---------------------------------------------------------------------- #
class FfmpegTrimTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "ffmpeg_trim"
    description = "Trim a media file to a start/end time range (seconds or HH:MM:SS)."
    parameters = {
        "type": "object",
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "start": {"type": "string"},
            "end": {"type": "string"},
        },
        "required": ["input_path", "output_path", "start", "end"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        inp = Path(str(kwargs.get("input_path", ""))).expanduser()
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        start = str(kwargs.get("start") or "0")
        end = str(kwargs.get("end") or "")
        if not inp.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INPUT_NOT_FOUND", "message": str(inp)},
            )
        if not end:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "end is required"},
            )
        out.parent.mkdir(parents=True, exist_ok=True)

        args = ["-i", str(inp), "-ss", start, "-to", end, "-c", "copy", str(out)]
        try:
            result = _run_ffmpeg(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FFMPEG_FAILED", "message": str(exc)},
            )

        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=result.returncode == 0 and check["verified"],
            tool=self.name,
            data={"output": str(out), "size": check.get("size")},
        )


# ---------------------------------------------------------------------- #
# Tool: ffmpeg_concat
# ---------------------------------------------------------------------- #
class FfmpegConcatTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "ffmpeg_concat"
    description = "Concatenate multiple media files into one."
    parameters = {
        "type": "object",
        "properties": {
            "input_paths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "output_path": {"type": "string"},
        },
        "required": ["input_paths", "output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        inputs: List[str] = list(kwargs.get("input_paths") or [])
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        if len(inputs) < 2:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "Need at least 2 inputs."},
            )
        for p in inputs:
            if not Path(p).exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "INPUT_NOT_FOUND", "message": str(p)},
                )
        out.parent.mkdir(parents=True, exist_ok=True)

        # Build a concat list file
        list_file = out.parent / f"_concat_{out.stem}.txt"
        try:
            with open(list_file, "w", encoding="utf-8") as fh:
                for p in inputs:
                    safe = Path(p).as_posix().replace("'", "'\\''")
                    fh.write(f"file '{safe}'\n")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LIST_FILE_FAILED", "message": str(exc)},
            )

        args = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)]
        try:
            result = _run_ffmpeg(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FFMPEG_FAILED", "message": str(exc)},
            )

        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=result.returncode == 0 and check["verified"],
            tool=self.name,
            data={"output": str(out), "size": check.get("size"), "inputs": len(inputs)},
        )


# ---------------------------------------------------------------------- #
# Tool: ffmpeg_thumbnail
# ---------------------------------------------------------------------- #
class FfmpegThumbnailTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "ffmpeg_thumbnail"
    description = "Extract a thumbnail frame from a video at a given timestamp."
    parameters = {
        "type": "object",
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "timestamp": {"type": "string"},
            "width": {"type": "integer"},
        },
        "required": ["input_path", "output_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        inp = Path(str(kwargs.get("input_path", ""))).expanduser()
        out = Path(str(kwargs.get("output_path", ""))).expanduser()
        if not inp.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INPUT_NOT_FOUND", "message": str(inp)},
            )
        out.parent.mkdir(parents=True, exist_ok=True)

        ts = str(kwargs.get("timestamp") or "00:00:01")
        width = int(kwargs.get("width") or 0)
        args = ["-ss", ts, "-i", str(inp), "-vframes", "1"]
        if width > 0:
            args += ["-vf", f"scale={width}:-1"]
        args.append(str(out))

        try:
            result = _run_ffmpeg(args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FFMPEG_FAILED", "message": str(exc)},
            )

        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=result.returncode == 0 and check["verified"],
            tool=self.name,
            data={"output": str(out), "size": check.get("size")},
        )