"""
Blender integration (Creative 3D).

Blender is controlled via its command-line Python interface:

    blender --background <file.blend> --python <script.py> -- <args>

No paid services, no plugins needed — pure Blender CLI.

Tools:
    - blender_run_script   : run a Python script inside Blender
    - blender_render       : render frames (calls Blender's built-in renderer)
    - blender_open_file    : launch Blender GUI with a .blend file
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _blender_cmd(executable: str) -> List[str]:
    return [executable]


def _run_blender(
    executable: str,
    args: List[str],
    timeout: int,
) -> subprocess.CompletedProcess:
    """Run Blender with the given args, capture stdout/stderr."""
    cmd = _blender_cmd(executable) + args
    logger.info("blender_run", args=args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: blender_run_script
# ---------------------------------------------------------------------- #
class BlenderRunScriptTool(AppIntegrationTool):
    APP_KEY = "blender"
    CONFIG_SECTION = "integrations.blender"

    name = "blender_run_script"
    description = (
        "Run a Python script inside Blender in headless mode. "
        "Optionally load a .blend file first."
    )
    parameters = {
        "type": "object",
        "properties": {
            "script_path": {
                "type": "string",
                "description": "Path to a .py script to run inside Blender.",
            },
            "blend_file": {
                "type": "string",
                "description": "Optional .blend file to load before running the script.",
            },
            "extra_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Arguments passed to the script after '--'.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Max runtime (default from config).",
            },
        },
        "required": ["script_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        executable = self._discover_path()
        if not executable:
            return self._not_installed_result(
                hint="Install Blender from blender.org or set integrations.blender.executable_path."
            )

        script_path = Path(str(kwargs.get("script_path", ""))).expanduser()
        if not script_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_NOT_FOUND", "message": str(script_path)},
            )

        blend_file = kwargs.get("blend_file")
        extra_args = list(kwargs.get("extra_args") or [])
        timeout = int(kwargs.get("timeout_seconds") or self._config("default_script_timeout", 300))

        args: List[str] = ["--background"]
        if blend_file:
            bf = Path(str(blend_file)).expanduser()
            if not bf.exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "BLEND_NOT_FOUND", "message": str(bf)},
                )
            args.append(str(bf))
        args += ["--python", str(script_path)]
        if extra_args:
            args.append("--")
            args += [str(a) for a in extra_args]

        try:
            result = _run_blender(executable, args, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TIMEOUT", "message": f"Blender exceeded {timeout}s."},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "BLENDER_RUN_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=result.returncode == 0,
            tool=self.name,
            data={
                "returncode": result.returncode,
                "stdout_tail": (result.stdout or "")[-2000:],
                "stderr_tail": (result.stderr or "")[-2000:],
                "script": str(script_path),
            },
            error=(
                None
                if result.returncode == 0
                else {"code": "BLENDER_ERROR", "message": (result.stderr or "")[:500]}
            ),
        )


# ---------------------------------------------------------------------- #
# Tool: blender_render
# ---------------------------------------------------------------------- #
class BlenderRenderTool(AppIntegrationTool):
    APP_KEY = "blender"
    CONFIG_SECTION = "integrations.blender"

    name = "blender_render"
    description = (
        "Render frames from a .blend file using Blender's headless renderer. "
        "Saves output images to a directory of your choice."
    )
    parameters = {
        "type": "object",
        "properties": {
            "blend_file": {"type": "string"},
            "output_dir": {"type": "string"},
            "frame_start": {"type": "integer"},
            "frame_end": {"type": "integer"},
            "engine": {
                "type": "string",
                "description": "Render engine (e.g. BLENDER_EEVEE, CYCLES).",
            },
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["blend_file", "output_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        executable = self._discover_path()
        if not executable:
            return self._not_installed_result()

        blend_file = Path(str(kwargs.get("blend_file", ""))).expanduser()
        if not blend_file.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "BLEND_NOT_FOUND", "message": str(blend_file)},
            )

        output_dir = Path(str(kwargs.get("output_dir", ""))).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        frame_start = int(kwargs.get("frame_start") or 1)
        frame_end = int(kwargs.get("frame_end") or frame_start)
        engine = kwargs.get("engine")
        timeout = int(kwargs.get("timeout_seconds") or 3600)

        args: List[str] = [
            "--background",
            str(blend_file),
            "--render-output", str(output_dir / "frame_"),
            "--render-format", "PNG",
        ]
        if engine:
            args += ["--engine", str(engine)]
        if frame_start == frame_end:
            args += ["--render-frame", str(frame_start)]
        else:
            args += ["--render-frame", f"{frame_start}..{frame_end}"]

        try:
            result = _run_blender(executable, args, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TIMEOUT", "message": f"Render exceeded {timeout}s."},
            )

        # Find at least one rendered file
        rendered_files = sorted(output_dir.glob("frame_*.png"))
        verified = len(rendered_files) > 0

        return ToolResult(
            success=result.returncode == 0 and verified,
            tool=self.name,
            data={
                "returncode": result.returncode,
                "output_dir": str(output_dir),
                "frames_rendered": len(rendered_files),
                "sample_file": str(rendered_files[0]) if rendered_files else None,
            },
            error=(
                None
                if result.returncode == 0 and verified
                else {
                    "code": "RENDER_INCOMPLETE",
                    "message": (result.stderr or "")[:500] or "No frames produced.",
                }
            ),
        )


# ---------------------------------------------------------------------- #
# Tool: blender_open_file
# ---------------------------------------------------------------------- #
class BlenderOpenFileTool(AppIntegrationTool):
    APP_KEY = "blender"
    CONFIG_SECTION = "integrations.blender"

    name = "blender_open_file"
    description = "Open a .blend file in the Blender GUI."
    parameters = {
        "type": "object",
        "properties": {
            "blend_file": {"type": "string"},
        },
        "required": ["blend_file"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        executable = self._discover_path()
        if not executable:
            return self._not_installed_result()

        blend_file = Path(str(kwargs.get("blend_file", ""))).expanduser()
        if not blend_file.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "BLEND_NOT_FOUND", "message": str(blend_file)},
            )

        try:
            subprocess.Popen(
                [executable, str(blend_file)],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "LAUNCH_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"blend_file": str(blend_file), "launched": True},
        )