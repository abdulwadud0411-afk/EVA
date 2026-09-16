"""
Universal export helpers (Common).

Tools:
    - batch_convert  : convert many media files at once
    - verify_output  : sanity-check an output file (size, media validity)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists, media_file_valid

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Tool: batch_convert
# ---------------------------------------------------------------------- #
class BatchConvertTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "batch_convert"
    description = (
        "Convert every file matching a glob (e.g. *.mov) inside a folder "
        "to a target format using ffmpeg."
    )
    parameters = {
        "type": "object",
        "properties": {
            "input_dir": {"type": "string"},
            "glob_pattern": {"type": "string"},
            "output_dir": {"type": "string"},
            "target_ext": {"type": "string"},
        },
        "required": ["input_dir", "output_dir", "target_ext"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        input_dir = Path(str(kwargs.get("input_dir", ""))).expanduser()
        output_dir = Path(str(kwargs.get("output_dir", ""))).expanduser()
        pattern = str(kwargs.get("glob_pattern") or "*.*")
        target_ext = str(kwargs.get("target_ext")).lstrip(".").lower()

        if not input_dir.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INPUT_DIR_NOT_FOUND", "message": str(input_dir)},
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(input_dir.glob(pattern))
        if not files:
            return ToolResult(
                success=True,
                tool=self.name,
                data={"converted": 0, "note": f"No files matched {pattern}"},
            )

        # Reuse the ffmpeg_convert tool logic directly
        from app.tools.integrations.common.media_processing_tools import FfmpegConvertTool

        converted: List[dict] = []
        failed: List[dict] = []
        for src in files:
            out = output_dir / f"{src.stem}.{target_ext}"
            tool = FfmpegConvertTool()
            # bypass permission gate — we already checked on the parent tool
            r = await tool.run_impl(input_path=str(src), output_path=str(out))
            if r.success:
                converted.append({"input": str(src), "output": str(out)})
            else:
                failed.append({"input": str(src), "error": r.error})

        return ToolResult(
            success=len(converted) > 0,
            tool=self.name,
            data={
                "converted": len(converted),
                "failed": len(failed),
                "items": converted,
                "errors": failed[:5],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: verify_output
# ---------------------------------------------------------------------- #
class VerifyOutputTool(AppIntegrationTool):
    APP_KEY = "ffmpeg"
    CONFIG_SECTION = "integrations.common"

    name = "verify_output"
    description = "Verify that an output file exists and is a valid media file (via ffprobe)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "min_size_bytes": {"type": "integer"},
        },
        "required": ["path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        path = str(kwargs.get("path", ""))
        min_size = int(kwargs.get("min_size_bytes") or 1)

        basic = file_exists(path, min_size_bytes=min_size)
        if not basic["verified"]:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VERIFY_FAILED", "message": str(basic)},
                data={"basic": basic},
            )

        media = media_file_valid(path)
        return ToolResult(
            success=media["verified"],
            tool=self.name,
            data={"basic": basic, "media": media},
        )