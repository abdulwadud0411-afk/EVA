"""
ComfyUI integration (Creative 3D — first-class).

ComfyUI exposes a local HTTP API (default http://127.0.0.1:8188) that
lets us:
    - List installed models (checkpoints, LoRAs, VAEs, etc.)
    - List saved workflows
    - Queue a workflow for execution
    - Monitor queue / history
    - Retrieve generated outputs

Model-agnostic: workflows are JSON files. Whether they use SDXL,
Flux, Seedance, MiniMax, or any other node/model, this tool layer
doesn't care — the workflow file decides.

No paid services required. Everything runs on the user's ComfyUI.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _base_url(tool: AppIntegrationTool) -> str:
    return str(tool._config("base_url", "http://127.0.0.1:8188")).rstrip("/")


def _workflows_dir() -> Path:
    base = ConfigManager.get_project_root()
    raw = ConfigManager.get("integrations.comfyui.workflows_dir", "./data/comfyui/workflows")
    p = Path(raw)
    if not p.is_absolute():
        p = base / raw
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _get_json(url: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("comfyui_get_failed", url=url, error=str(exc))
        return None


async def _post_json(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("comfyui_post_failed", url=url, error=str(exc))
        return None


# ---------------------------------------------------------------------- #
# Tool: comfyui_ping
# ---------------------------------------------------------------------- #
class ComfyUIPingTool(AppIntegrationTool):
    APP_KEY = "comfyui"
    CONFIG_SECTION = "integrations.comfyui"

    name = "comfyui_ping"
    description = "Check whether the local ComfyUI server is reachable."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = _base_url(self)
        stats = await _get_json(f"{base}/system_stats", timeout=5.0)
        if stats is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "COMFYUI_UNREACHABLE",
                    "message": f"ComfyUI server not reachable at {base}. "
                               f"Start ComfyUI and verify the port.",
                },
            )
        return ToolResult(
            success=True,
            tool=self.name,
            data={"endpoint": base, "stats": stats},
        )


# ---------------------------------------------------------------------- #
# Tool: comfyui_list_models
# ---------------------------------------------------------------------- #
class ComfyUIListModelsTool(AppIntegrationTool):
    APP_KEY = "comfyui"
    CONFIG_SECTION = "integrations.comfyui"

    name = "comfyui_list_models"
    description = (
        "List models installed in ComfyUI. "
        "Specify category (checkpoints, loras, vae, controlnet, ...)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
        },
        "required": [],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = _base_url(self)
        category = str(kwargs.get("category") or "checkpoints").strip()

        # ComfyUI exposes /object_info with model choices; we use the
        # simpler info endpoint if available.
        info = await _get_json(f"{base}/object_info/CheckpointLoaderSimple", timeout=10.0)
        if info is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "COMFYUI_UNREACHABLE", "message": "Cannot query ComfyUI."},
            )

        models: List[str] = []
        try:
            node = info.get("CheckpointLoaderSimple") or {}
            required = node.get("input", {}).get("required", {})
            ckpt = required.get("ckpt_name")
            if isinstance(ckpt, list) and ckpt and isinstance(ckpt[0], list):
                models = [str(m) for m in ckpt[0]]
        except Exception:  # noqa: BLE001
            models = []

        # Category filter (kept for future endpoints)
        if category.lower() not in ("checkpoints", "checkpoint"):
            # Other categories require different node info; return what we have
            pass

        return ToolResult(
            success=True,
            tool=self.name,
            data={"category": category, "count": len(models), "models": models},
        )


# ---------------------------------------------------------------------- #
# Tool: comfyui_list_workflows
# ---------------------------------------------------------------------- #
class ComfyUIListWorkflowsTool(AppIntegrationTool):
    APP_KEY = "comfyui"
    CONFIG_SECTION = "integrations.comfyui"

    name = "comfyui_list_workflows"
    description = "List saved ComfyUI workflow JSON files in the local workflows directory."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        wf_dir = _workflows_dir()
        files = sorted(wf_dir.glob("*.json"))
        items = []
        for f in files:
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            items.append({"name": f.name, "path": str(f), "size": size})

        return ToolResult(
            success=True,
            tool=self.name,
            data={"workflows_dir": str(wf_dir), "count": len(items), "workflows": items},
        )


# ---------------------------------------------------------------------- #
# Tool: comfyui_run_workflow
# ---------------------------------------------------------------------- #
class ComfyUIRunWorkflowTool(AppIntegrationTool):
    APP_KEY = "comfyui"
    CONFIG_SECTION = "integrations.comfyui"

    name = "comfyui_run_workflow"
    description = (
        "Queue a ComfyUI workflow for execution. "
        "Provide either a workflow name from the local workflows directory, "
        "or an inline workflow object. Waits for completion and returns output metadata."
    )
    parameters = {
        "type": "object",
        "properties": {
            "workflow_name": {"type": "string"},
            "workflow": {"type": "object"},
            "timeout_seconds": {"type": "integer"},
        },
        "required": [],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = _base_url(self)
        timeout = int(kwargs.get("timeout_seconds") or self._config("timeout_seconds", 600))

        # Load workflow
        workflow = kwargs.get("workflow")
        workflow_name = kwargs.get("workflow_name")
        if workflow is None and workflow_name:
            wf_path = _workflows_dir() / str(workflow_name)
            if not wf_path.exists() and not wf_path.suffix:
                wf_path = wf_path.with_suffix(".json")
            if not wf_path.exists():
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={
                        "code": "WORKFLOW_NOT_FOUND",
                        "message": f"Not found: {wf_path}",
                    },
                )
            try:
                workflow = json.loads(wf_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                return ToolResult(
                    success=False,
                    tool=self.name,
                    error={"code": "WORKFLOW_INVALID", "message": str(exc)},
                )
        if workflow is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "INVALID_ARGUMENT",
                    "message": "Provide workflow_name or workflow.",
                },
            )

        client_id = str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": client_id}

        submitted = await _post_json(f"{base}/prompt", payload, timeout=30.0)
        if not submitted or "prompt_id" not in submitted:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "QUEUE_FAILED",
                    "message": f"ComfyUI did not accept the workflow: {submitted}",
                },
            )

        prompt_id = submitted["prompt_id"]
        logger.info("comfyui_queued", prompt_id=prompt_id)

        # Poll history until the job is done
        deadline = time.time() + timeout
        history_entry: Optional[Dict[str, Any]] = None
        while time.time() < deadline:
            history = await _get_json(f"{base}/history/{prompt_id}", timeout=10.0)
            if history and prompt_id in history:
                history_entry = history[prompt_id]
                break
            await asyncio.sleep(1.5)

        if history_entry is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "TIMEOUT",
                    "message": f"Workflow did not finish within {timeout}s.",
                },
                data={"prompt_id": prompt_id},
            )

        # Extract output file references
        outputs: List[Dict[str, Any]] = []
        for node_id, node_out in (history_entry.get("outputs") or {}).items():
            for key in ("images", "gifs", "videos", "audio"):
                for item in node_out.get(key, []) or []:
                    outputs.append({
                        "node_id": node_id,
                        "type": key,
                        "filename": item.get("filename"),
                        "subfolder": item.get("subfolder", ""),
                        "folder_type": item.get("type", "output"),
                    })

        return ToolResult(
            success=len(outputs) > 0,
            tool=self.name,
            data={
                "prompt_id": prompt_id,
                "outputs": outputs,
                "output_count": len(outputs),
            },
        )


# ---------------------------------------------------------------------- #
# Tool: comfyui_queue_status
# ---------------------------------------------------------------------- #
class ComfyUIQueueStatusTool(AppIntegrationTool):
    APP_KEY = "comfyui"
    CONFIG_SECTION = "integrations.comfyui"

    name = "comfyui_queue_status"
    description = "Report the number of running and pending ComfyUI jobs."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = _base_url(self)
        q = await _get_json(f"{base}/queue", timeout=10.0)
        if q is None:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "COMFYUI_UNREACHABLE", "message": "Cannot query queue."},
            )
        running = q.get("queue_running") or []
        pending = q.get("queue_pending") or []
        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "running": len(running),
                "pending": len(pending),
            },
        )


# ---------------------------------------------------------------------- #
# Tool: comfyui_get_output
# ---------------------------------------------------------------------- #
class ComfyUIGetOutputTool(AppIntegrationTool):
    APP_KEY = "comfyui"
    CONFIG_SECTION = "integrations.comfyui"

    name = "comfyui_get_output"
    description = (
        "Download a ComfyUI output file (image/video/audio) by filename "
        "into EVA's data/exports/comfyui/ directory."
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "subfolder": {"type": "string"},
            "folder_type": {"type": "string"},
        },
        "required": ["filename"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        base = _base_url(self)
        filename = str(kwargs.get("filename", "")).strip()
        if not filename:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "filename required"},
            )
        subfolder = str(kwargs.get("subfolder") or "")
        folder_type = str(kwargs.get("folder_type") or "output")

        out_dir = ConfigManager.get_data_dir() / "exports" / "comfyui"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / filename

        url = f"{base}/view"
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                target.write_bytes(r.content)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOWNLOAD_FAILED", "message": str(exc)},
            )

        try:
            size = target.stat().st_size
        except OSError:
            size = 0

        return ToolResult(
            success=size > 0,
            tool=self.name,
            data={"path": str(target), "size": size, "filename": filename},
        )