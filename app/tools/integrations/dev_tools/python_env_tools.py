"""
Python environment tools.

Create virtualenvs, install packages, run Python scripts — all using
the local Python interpreter. No paid service.

Tools:
    - python_create_venv
    - python_pip_install
    - python_run_script
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _python_cli() -> Optional[str]:
    for name in ("python", "python.exe", "py"):
        found = shutil.which(name)
        if found:
            return found
    return None


# ---------------------------------------------------------------------- #
# Tool: python_create_venv
# ---------------------------------------------------------------------- #
class PythonCreateVenvTool(AppIntegrationTool):
    APP_KEY = "python"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "python_create_venv"
    description = "Create a Python virtual environment at the target path."
    parameters = {
        "type": "object",
        "properties": {"venv_path": {"type": "string"}},
        "required": ["venv_path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("venv_path", "")).strip()
        if not raw:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "venv_path required"},
            )
        venv_path = Path(raw).expanduser()
        venv_path.parent.mkdir(parents=True, exist_ok=True)

        cli = _python_cli()
        if not cli:
            return self._not_installed_result(hint="Python not found on PATH.")

        try:
            r = subprocess.run(
                [cli, "-m", "venv", str(venv_path)],
                capture_output=True, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "VENV_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=r.returncode == 0 and venv_path.exists(),
            tool=self.name,
            data={
                "venv": str(venv_path),
                "stdout_tail": (r.stdout or "")[-500:],
                "stderr_tail": (r.stderr or "")[-500:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: python_pip_install
# ---------------------------------------------------------------------- #
class PythonPipInstallTool(AppIntegrationTool):
    APP_KEY = "python"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "python_pip_install"
    description = "Install one or more pip packages into a given Python environment."
    parameters = {
        "type": "object",
        "properties": {
            "packages": {"type": "array", "items": {"type": "string"}},
            "venv_path": {"type": "string"},
            "upgrade": {"type": "boolean"},
        },
        "required": ["packages"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        packages: List[str] = list(kwargs.get("packages") or [])
        if not packages:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "packages required"},
            )

        # Determine which python to use
        if kwargs.get("venv_path"):
            venv = Path(str(kwargs["venv_path"])).expanduser()
            if os.name == "nt":
                python_exe = venv / "Scripts" / "python.exe"
            else:
                python_exe = venv / "bin" / "python"
        else:
            cli = _python_cli()
            if not cli:
                return self._not_installed_result()
            python_exe = Path(cli)

        if not python_exe.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PYTHON_NOT_FOUND", "message": str(python_exe)},
            )

        args = [str(python_exe), "-m", "pip", "install"]
        if kwargs.get("upgrade"):
            args.append("--upgrade")
        args += packages

        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PIP_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "python": str(python_exe),
                "packages": packages,
                "stdout_tail": (r.stdout or "")[-1000:],
                "stderr_tail": (r.stderr or "")[-1000:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: python_run_script
# ---------------------------------------------------------------------- #
class PythonRunScriptTool(AppIntegrationTool):
    APP_KEY = "python"
    CONFIG_SECTION = "integrations.dev_tools"

    name = "python_run_script"
    description = "Run a Python script and capture its output."
    parameters = {
        "type": "object",
        "properties": {
            "script_path": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
            "venv_path": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["script_path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        script = Path(str(kwargs.get("script_path", ""))).expanduser()
        if not script.exists():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "SCRIPT_NOT_FOUND", "message": str(script)},
            )

        if kwargs.get("venv_path"):
            venv = Path(str(kwargs["venv_path"])).expanduser()
            python_exe = (venv / "Scripts" / "python.exe") if os.name == "nt" else (venv / "bin" / "python")
        else:
            cli = _python_cli()
            if not cli:
                return self._not_installed_result()
            python_exe = Path(cli)

        timeout = int(kwargs.get("timeout_seconds") or 600)
        extra = [str(a) for a in (kwargs.get("args") or [])]

        try:
            r = subprocess.run(
                [str(python_exe), str(script)] + extra,
                capture_output=True, text=True, timeout=timeout,
                cwd=str(script.parent),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "TIMEOUT", "message": f"Script exceeded {timeout}s."},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "PYTHON_RUN_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "returncode": r.returncode,
                "stdout": (r.stdout or "")[-4000:],
                "stderr": (r.stderr or "")[-2000:],
            },
        )