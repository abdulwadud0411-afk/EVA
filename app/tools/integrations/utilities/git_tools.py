"""
Git integration.

Uses the free, open-source git CLI (no paid service).
GitHub CLI (`gh`) is optional and used only when present.

Tools:
    - git_clone
    - git_status
    - git_commit
    - git_push
    - git_pull
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


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _git_cli() -> Optional[str]:
    for name in ("git", "git.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_git(args: List[str], cwd: Optional[str] = None, timeout: int = 300) -> subprocess.CompletedProcess:
    git = _git_cli()
    if not git:
        raise RuntimeError("git not found on PATH.")
    return subprocess.run(
        [git] + args,
        cwd=cwd,
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


# ---------------------------------------------------------------------- #
# Tool: git_clone
# ---------------------------------------------------------------------- #
class GitCloneTool(AppIntegrationTool):
    APP_KEY = "git"
    CONFIG_SECTION = "integrations.utilities"

    name = "git_clone"
    description = "Clone a git repository to a local directory."
    parameters = {
        "type": "object",
        "properties": {
            "repo_url": {"type": "string"},
            "target_dir": {"type": "string"},
            "branch": {"type": "string"},
        },
        "required": ["repo_url", "target_dir"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        url = str(kwargs.get("repo_url", "")).strip()
        target = Path(str(kwargs.get("target_dir", ""))).expanduser()
        if not url:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "repo_url required"},
            )
        target.parent.mkdir(parents=True, exist_ok=True)

        args = ["clone"]
        branch = kwargs.get("branch")
        if branch:
            args += ["-b", str(branch)]
        args += [url, str(target)]

        try:
            r = _run_git(args, timeout=1800)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "GIT_CLONE_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=r.returncode == 0 and target.exists(),
            tool=self.name,
            data={
                "target": str(target),
                "returncode": r.returncode,
                "stdout_tail": (r.stdout or "")[-500:],
                "stderr_tail": (r.stderr or "")[-500:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: git_status
# ---------------------------------------------------------------------- #
class GitStatusTool(AppIntegrationTool):
    APP_KEY = "git"
    CONFIG_SECTION = "integrations.utilities"

    name = "git_status"
    description = "Show git status of a repository."
    parameters = {
        "type": "object",
        "properties": {
            "repo_dir": {"type": "string"},
        },
        "required": ["repo_dir"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        repo = Path(str(kwargs.get("repo_dir", ""))).expanduser()
        if not repo.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "REPO_NOT_FOUND", "message": str(repo)},
            )
        try:
            r = _run_git(["status", "--short", "--branch"], cwd=str(repo))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "GIT_STATUS_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"output": (r.stdout or "").strip()},
        )


# ---------------------------------------------------------------------- #
# Tool: git_commit
# ---------------------------------------------------------------------- #
class GitCommitTool(AppIntegrationTool):
    APP_KEY = "git"
    CONFIG_SECTION = "integrations.utilities"

    name = "git_commit"
    description = "Stage all changes and create a git commit."
    parameters = {
        "type": "object",
        "properties": {
            "repo_dir": {"type": "string"},
            "message": {"type": "string"},
            "add_all": {"type": "boolean"},
        },
        "required": ["repo_dir", "message"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        repo = Path(str(kwargs.get("repo_dir", ""))).expanduser()
        message = str(kwargs.get("message", "")).strip()
        if not repo.is_dir() or not message:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "repo_dir + message required"},
            )
        add_all = bool(kwargs.get("add_all", True))
        try:
            if add_all:
                _run_git(["add", "-A"], cwd=str(repo))
            r = _run_git(["commit", "-m", message], cwd=str(repo))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "GIT_COMMIT_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"output": (r.stdout or "")[-500:]},
        )


# ---------------------------------------------------------------------- #
# Tool: git_push
# ---------------------------------------------------------------------- #
class GitPushTool(AppIntegrationTool):
    APP_KEY = "git"
    CONFIG_SECTION = "integrations.utilities"

    name = "git_push"
    description = "Push commits to the remote."
    parameters = {
        "type": "object",
        "properties": {
            "repo_dir": {"type": "string"},
            "remote": {"type": "string"},
            "branch": {"type": "string"},
        },
        "required": ["repo_dir"],
    }
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        repo = Path(str(kwargs.get("repo_dir", ""))).expanduser()
        if not repo.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "REPO_NOT_FOUND", "message": str(repo)},
            )
        args = ["push"]
        if kwargs.get("remote"):
            args.append(str(kwargs["remote"]))
        if kwargs.get("branch"):
            args.append(str(kwargs["branch"]))
        try:
            r = _run_git(args, cwd=str(repo), timeout=600)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "GIT_PUSH_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={
                "stdout_tail": (r.stdout or "")[-500:],
                "stderr_tail": (r.stderr or "")[-500:],
            },
        )


# ---------------------------------------------------------------------- #
# Tool: git_pull
# ---------------------------------------------------------------------- #
class GitPullTool(AppIntegrationTool):
    APP_KEY = "git"
    CONFIG_SECTION = "integrations.utilities"

    name = "git_pull"
    description = "Pull the latest changes from the remote."
    parameters = {
        "type": "object",
        "properties": {
            "repo_dir": {"type": "string"},
        },
        "required": ["repo_dir"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        repo = Path(str(kwargs.get("repo_dir", ""))).expanduser()
        if not repo.is_dir():
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "REPO_NOT_FOUND", "message": str(repo)},
            )
        try:
            r = _run_git(["pull"], cwd=str(repo), timeout=600)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "GIT_PULL_FAILED", "message": str(exc)},
            )
        return ToolResult(
            success=r.returncode == 0,
            tool=self.name,
            data={"stdout_tail": (r.stdout or "")[-500:]},
        )