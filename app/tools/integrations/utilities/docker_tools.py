"""
Docker integration.

Uses the local Docker CLI (free for personal use).
Requires Docker Desktop (or Docker Engine) installed and running.

Tools:
    - docker_list_containers
    - docker_start_container
    - docker_stop_container
    - docker_compose_up
    - docker_compose_down
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


def _docker_cli() -> Optional[str]:
    for name in ("docker", "docker.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_docker(args: List[str], cwd: Optional[str] = None, timeout: int = 600) -> subprocess.CompletedProcess:
    cli = _docker_cli()
    if not cli:
        raise RuntimeError("docker CLI not found on PATH.")
    return subprocess.run(
        [cli] + args,
        cwd=cwd,
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: docker_list_containers
# ---------------------------------------------------------------------- #
class DockerListContainersTool(AppIntegrationTool):
    APP_KEY = "docker"
    CONFIG_SECTION = "integrations.utilities"

    name = "docker_list_containers"
    description = "List Docker containers (running and stopped)."
    parameters = {
        "type": "object",
        "properties": {"all": {"type": "boolean"}},
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        args = ["ps", "--format", "{{json .}}"]
        if kwargs.get("all", True):
            args.insert(1, "-a")
        try:
            r = _run_docker(args, timeout=30)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOCKER_FAILED", "message": str(exc)},
            )
        containers: List[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"count": len(containers), "containers": containers},
        )


# ---------------------------------------------------------------------- #
# Tool: docker_start_container
# ---------------------------------------------------------------------- #
class DockerStartContainerTool(AppIntegrationTool):
    APP_KEY = "docker"
    CONFIG_SECTION = "integrations.utilities"

    name = "docker_start_container"
    description = "Start a Docker container by name or ID."
    parameters = {
        "type": "object",
        "properties": {"container": {"type": "string"}},
        "required": ["container"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        container = str(kwargs.get("container", "")).strip()
        if not container:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "container required"},
            )
        try:
            r = _run_docker(["start", container], timeout=60)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOCKER_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"container": container, "output": (r.stdout or "").strip()},
        )


# ---------------------------------------------------------------------- #
# Tool: docker_stop_container
# ---------------------------------------------------------------------- #
class DockerStopContainerTool(AppIntegrationTool):
    APP_KEY = "docker"
    CONFIG_SECTION = "integrations.utilities"

    name = "docker_stop_container"
    description = "Stop a running Docker container."
    parameters = {
        "type": "object",
        "properties": {"container": {"type": "string"}},
        "required": ["container"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        container = str(kwargs.get("container", "")).strip()
        if not container:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "container required"},
            )
        try:
            r = _run_docker(["stop", container], timeout=60)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOCKER_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"container": container},
        )


# ---------------------------------------------------------------------- #
# Tool: docker_compose_up
# ---------------------------------------------------------------------- #
class DockerComposeUpTool(AppIntegrationTool):
    APP_KEY = "docker"
    CONFIG_SECTION = "integrations.utilities"

    name = "docker_compose_up"
    description = "Run `docker compose up -d` in a project directory."
    parameters = {
        "type": "object",
        "properties": {
            "project_dir": {"type": "string"},
            "detach": {"type": "boolean"},
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
        args = ["compose", "up"]
        if kwargs.get("detach", True):
            args.append("-d")
        try:
            r = _run_docker(args, cwd=str(project), timeout=1800)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOCKER_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "returncode": r.returncode,
                "stdout_tail": (r.stdout or "")[-800:],
                "stderr_tail": (r.stderr or "")[-800:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: docker_compose_down
# ---------------------------------------------------------------------- #
class DockerComposeDownTool(AppIntegrationTool):
    APP_KEY = "docker"
    CONFIG_SECTION = "integrations.utilities"

    name = "docker_compose_down"
    description = "Run `docker compose down` in a project directory."
    parameters = {
        "type": "object",
        "properties": {"project_dir": {"type": "string"}},
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
        try:
            r = _run_docker(["compose", "down"], cwd=str(project), timeout=600)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOCKER_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"returncode": r.returncode},
        )