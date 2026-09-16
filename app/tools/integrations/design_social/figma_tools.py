"""
Figma integration (Design & Social).

Uses the free Figma REST API with a personal access token stored in
the environment (FIGMA_ACCESS_TOKEN). No paid service is required —
the free Figma account is enough for read/export on files the user
has access to.

Tools:
    - figma_get_file       : fetch full file JSON
    - figma_get_node       : fetch a specific node by id
    - figma_export_image   : export a node as PNG/JPG/SVG/PDF
    - figma_list_projects  : list projects in a team
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool
from app.tools.verifier import file_exists

logger = get_logger(__name__)

FIGMA_API_BASE = "https://api.figma.com/v1"


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _token() -> Optional[str]:
    env_key = str(ConfigManager.get(
        "integrations.figma.access_token_env", "FIGMA_ACCESS_TOKEN"
    ))
    return os.getenv(env_key) or None


def _headers(token: str) -> Dict[str, str]:
    return {"X-Figma-Token": token}


def _figma_cache_dir() -> Path:
    d = ConfigManager.get_data_dir() / "exports" / "figma"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------- #
# Tool: figma_get_file
# ---------------------------------------------------------------------- #
class FigmaGetFileTool(AppIntegrationTool):
    APP_KEY = "figma"
    CONFIG_SECTION = "integrations.figma"

    name = "figma_get_file"
    description = "Fetch the JSON structure of a Figma file by key."
    parameters = {
        "type": "object",
        "properties": {
            "file_key": {"type": "string"},
            "depth": {"type": "integer"},
        },
        "required": ["file_key"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        token = _token()
        if not token:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "NO_TOKEN",
                    "message": "Set FIGMA_ACCESS_TOKEN in .env",
                },
            )

        file_key = str(kwargs.get("file_key", "")).strip()
        if not file_key:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "file_key required"},
            )

        params: Dict[str, Any] = {}
        if "depth" in kwargs and kwargs["depth"] is not None:
            params["depth"] = int(kwargs["depth"])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(
                    f"{FIGMA_API_BASE}/files/{file_key}",
                    headers=_headers(token),
                    params=params,
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FIGMA_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={
                "name": data.get("name"),
                "lastModified": data.get("lastModified"),
                "version": data.get("version"),
                "raw": data,
            },
        )


# ---------------------------------------------------------------------- #
# Tool: figma_get_node
# ---------------------------------------------------------------------- #
class FigmaGetNodeTool(AppIntegrationTool):
    APP_KEY = "figma"
    CONFIG_SECTION = "integrations.figma"

    name = "figma_get_node"
    description = "Fetch a specific node (by id) from a Figma file."
    parameters = {
        "type": "object",
        "properties": {
            "file_key": {"type": "string"},
            "node_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["file_key", "node_ids"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        token = _token()
        if not token:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "NO_TOKEN", "message": "Set FIGMA_ACCESS_TOKEN."},
            )

        file_key = str(kwargs.get("file_key", "")).strip()
        node_ids: List[str] = list(kwargs.get("node_ids") or [])
        if not file_key or not node_ids:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "file_key + node_ids required"},
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(
                    f"{FIGMA_API_BASE}/files/{file_key}/nodes",
                    headers=_headers(token),
                    params={"ids": ",".join(node_ids)},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FIGMA_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"nodes": data.get("nodes", {}), "count": len(node_ids)},
        )


# ---------------------------------------------------------------------- #
# Tool: figma_export_image
# ---------------------------------------------------------------------- #
class FigmaExportImageTool(AppIntegrationTool):
    APP_KEY = "figma"
    CONFIG_SECTION = "integrations.figma"

    name = "figma_export_image"
    description = "Export a Figma node as PNG/JPG/SVG/PDF. Saves to data/exports/figma/."
    parameters = {
        "type": "object",
        "properties": {
            "file_key": {"type": "string"},
            "node_id": {"type": "string"},
            "format": {"type": "string"},
            "scale": {"type": "number"},
        },
        "required": ["file_key", "node_id"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        token = _token()
        if not token:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "NO_TOKEN", "message": "Set FIGMA_ACCESS_TOKEN."},
            )

        file_key = str(kwargs.get("file_key", "")).strip()
        node_id = str(kwargs.get("node_id", "")).strip()
        if not file_key or not node_id:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "file_key + node_id required"},
            )

        fmt = str(kwargs.get("format") or "png").lower()
        if fmt not in {"png", "jpg", "jpeg", "svg", "pdf"}:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": f"format '{fmt}' not supported"},
            )

        scale = float(kwargs.get("scale") or 2.0)

        # Step 1: ask Figma for a signed URL
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(
                    f"{FIGMA_API_BASE}/images/{file_key}",
                    headers=_headers(token),
                    params={
                        "ids": node_id,
                        "format": fmt,
                        "scale": scale,
                    },
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FIGMA_EXPORT_INIT_FAILED", "message": str(exc)},
            )

        urls = data.get("images") or {}
        url = urls.get(node_id)
        if not url:
            return ToolResult(
                success=False,
                tool=self.name,
                error={
                    "code": "FIGMA_NO_URL",
                    "message": f"No image URL returned: {data}",
                },
            )

        # Step 2: download it
        ext = "jpg" if fmt == "jpeg" else fmt
        out = _figma_cache_dir() / f"{file_key}_{node_id.replace(':', '_')}.{ext}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                out.write_bytes(r.content)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "DOWNLOAD_FAILED", "message": str(exc)},
            )

        check = file_exists(str(out), min_size_bytes=1)
        return ToolResult(
            success=check["verified"],
            tool=self.name,
            data={"path": str(out), "size": check.get("size"), "format": fmt},
        )


# ---------------------------------------------------------------------- #
# Tool: figma_list_projects
# ---------------------------------------------------------------------- #
class FigmaListProjectsTool(AppIntegrationTool):
    APP_KEY = "figma"
    CONFIG_SECTION = "integrations.figma"

    name = "figma_list_projects"
    description = "List projects in a Figma team."
    parameters = {
        "type": "object",
        "properties": {"team_id": {"type": "string"}},
        "required": ["team_id"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        token = _token()
        if not token:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "NO_TOKEN", "message": "Set FIGMA_ACCESS_TOKEN."},
            )

        team_id = str(kwargs.get("team_id", "")).strip()
        if not team_id:
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "INVALID_ARGUMENT", "message": "team_id required"},
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(
                    f"{FIGMA_API_BASE}/teams/{team_id}/projects",
                    headers=_headers(token),
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "FIGMA_FAILED", "message": str(exc)},
            )

        return ToolResult(
            success=True,
            tool=self.name,
            data={"projects": data.get("projects", [])},
        )