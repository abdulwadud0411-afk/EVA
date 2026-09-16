"""
Flutter SDK integration.

Uses the `flutter` CLI (bundled with the Flutter SDK). No paid service.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _flutter_cli() -> Optional[str]:
    for name in ("flutter", "flutter.bat", "flutter.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_flutter(args: List[str], cwd: Optional[str] = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    cli = _flutter_cli()
    if not cli:
        raise RuntimeError("flutter CLI not found on PATH.")
    return subprocess.run(
        [cli] + args,
        cwd=cwd,
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: flutter_create_project
# ---------------------------------------------------------------------- #
class FlutterCreateProjectTool(AppIntegrationTool):
    APP_KEY = "flutter"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "flutter_create_project"
    description = "Create a new Flutter project."
    parameters = {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "output_dir": {"type": "string"},
            "org": {"type": "string"},
        },
        "required": ["project_name", "output_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        name = str(kwargs.get("project_name", "")).strip()
        out_dir = Path(str(kwargs.get("output_dir", ""))).expanduser()
        if not name or not out_dir:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "project_name + output_dir required"},
            )
        out_dir.mkdir(parents=True, exist_ok=True)

        args = ["create", name]
        org = kwargs.get("org")
        if org:
            args += ["--org", str(org)]

        try:
            r = _run_flutter(args, cwd=str(out_dir))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FLUTTER_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "project": str(out_dir / name),
                "stdout_tail": (r.stdout or "")[-800:],
                "stderr_tail": (r.stderr or "")[-800:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: flutter_run
# ---------------------------------------------------------------------- #
class FlutterRunTool(AppIntegrationTool):
    APP_KEY = "flutter"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "flutter_run"
    description = "Run `flutter run` in a Flutter project (attaches to a device)."
    parameters = {
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "device": {"type": "string"},
        },
        "required": ["project_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project = Path(str(kwargs.get("project_dir", ""))).expanduser()
        if not project.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project)},
            )
        args = ["run"]
        if kwargs.get("device"):
            args += ["-d", str(kwargs["device"])]

        # `flutter run` is interactive; we just launch it detached
        try:
            cli = _flutter_cli()
            if not cli:
                raise RuntimeError("flutter not found")
            subprocess.Popen(
                [cli] + args,
                cwd=str(project),
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FLUTTER_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"project": str(project), "detached": True},
        )


# ---------------------------------------------------------------------- #
# Tool: flutter_build
# ---------------------------------------------------------------------- #
class FlutterBuildTool(AppIntegrationTool):
    APP_KEY = "flutter"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "flutter_build"
    description = "Run `flutter build <target>` (e.g. apk, windows, web)."
    parameters = {
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "target": {"type": "string"},
        },
        "required": ["project_dir", "target"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        project = Path(str(kwargs.get("project_dir", ""))).expanduser()
        target = str(kwargs.get("target") or "apk").strip()
        if not project.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PROJECT_NOT_FOUND", "message": str(project)},
            )
        try:
            r = _run_flutter(["build", target], cwd=str(project), timeout=3600)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FLUTTER_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "returncode": r.returncode,
                "stdout_tail": (r.stdout or "")[-1500:],
                "stderr_tail": (r.stderr or "")[-1500:],
            },
        )