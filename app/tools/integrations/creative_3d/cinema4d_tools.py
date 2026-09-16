"""
Cinema 4D integration (Creative 3D).

Cinema 4D ships with a Python SDK. It can run scripts headlessly via:

    "C:\\...\\Cinema 4D.exe" -nogui -python <script.py>

Tools:
    - cinema4d_run_script
    - cinema4d_render
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _run_c4d(executable: str, args: List[str], timeout: int) -> subprocess.CompletedProcess:
    cmd = [executable] + args
    logger.info("cinema4d_run", args=args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: cinema4d_run_script
# ---------------------------------------------------------------------- #
class Cinema4DRunScriptTool(AppIntegrationTool):
    APP_KEY = "cinema4d"
    CONFIG_SECTION = "integrations.cinema4d"

    name = "cinema4d_run_script"
    description = "Run a Python script inside Cinema 4D in headless mode."
    parameters = {
        "type": "object",
        "properties": {
            "script_path": {"type": "string"},
            "c4d_file": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["script_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        executable = self._discover_path()
        if not executable:
            return self._not_installed_result()

        script_path = Path(str(kwargs.get("script_path", ""))).expanduser()
        if not script_path.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_NOT_FOUND", "message": str(script_path)},
            )

        timeout = int(kwargs.get("timeout_seconds") or self._config("default_script_timeout", 300))
        args = ["-nogui"]
        c4d_file = kwargs.get("c4d_file")
        if c4d_file:
            cf = Path(str(c4d_file)).expanduser()
            if not cf.exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "C4D_FILE_NOT_FOUND", "message": str(cf)},
                )
            args.append(str(cf))
        args += ["-python", str(script_path)]

        try:
            result = _run_c4d(executable, args, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TIMEOUT", "message": f"Exceeded {timeout}s."},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "C4D_RUN_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=result.returncode == 0,
            tool=self.name,
            data={
                "returncode": result.returncode,
                "stdout_tail": (result.stdout or "")[-2000:],
                "stderr_tail": (result.stderr or "")[-2000:],
            },
            error=(
                None if result.returncode == 0
                else {"code": "C4D_ERROR", "message": (result.stderr or "")[:500]}
            ),
        )


# ---------------------------------------------------------------------- #
# Tool: cinema4d_render
# ---------------------------------------------------------------------- #
class Cinema4DRenderTool(AppIntegrationTool):
    APP_KEY = "cinema4d"
    CONFIG_SECTION = "integrations.cinema4d"

    name = "cinema4d_render"
    description = "Render frames from a .c4d file via Cinema 4D's CLI renderer."
    parameters = {
        "type": "object",
        "properties": {
            "c4d_file": {"type": "string"},
            "output_dir": {"type": "string"},
            "frame_start": {"type": "integer"},
            "frame_end": {"type": "integer"},
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["c4d_file", "output_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        executable = self._discover_path()
        if not executable:
            return self._not_installed_result()

        c4d_file = Path(str(kwargs.get("c4d_file", ""))).expanduser()
        if not c4d_file.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "C4D_FILE_NOT_FOUND", "message": str(c4d_file)},
            )

        output_dir = Path(str(kwargs.get("output_dir", ""))).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        fs = int(kwargs.get("frame_start") or 1)
        fe = int(kwargs.get("frame_end") or fs)
        timeout = int(kwargs.get("timeout_seconds") or 3600)

        args = [
            "-nogui",
            "-render", str(c4d_file),
            "-frame", f"{fs}", f"{fe}",
            "-ooutput", str(output_dir / "frame_"),
            "-oformat", "PNG",
        ]

        try:
            result = _run_c4d(executable, args, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TIMEOUT", "message": f"Exceeded {timeout}s."},
            )

        rendered = sorted(output_dir.glob("frame_*.png"))
        verified = len(rendered) > 0

        return ToolResult(
            success=result.returncode == 0 and verified,
            tool=self.name,
            data={
                "returncode": result.returncode,
                "output_dir": str(output_dir),
                "frames_rendered": len(rendered),
                "sample_file": str(rendered[0]) if rendered else None,
            },
            error=(
                None if result.returncode == 0 and verified
                else {"code": "RENDER_INCOMPLETE", "message": "No frames produced."}
            ),
        )