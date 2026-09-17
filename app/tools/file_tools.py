"""
File tools (Phase 19).

Tools:
    - read_file
    - write_file
    - list_directory
    - create_folder
    - move_file
    - copy_file
    - delete_file
    - search_files

All paths pass through PathGuard before any filesystem operation.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, List

from app.core.logger import get_logger
from app.security.path_guard import PathGuard, PathViolation
from app.tools.base import Tool, ToolResult, RiskLevel

logger = get_logger(__name__)


_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".csv", ".log", ".html", ".css", ".xml", ".ini", ".cfg", ".env",
}


def _guard(tool_name: str, path: str) -> Path:
    """Resolve through PathGuard or raise a ToolResult on failure."""
    return PathGuard.resolve(path)


# ---------------------------------------------------------------------- #
# Tool: read_file
# ---------------------------------------------------------------------- #
class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a text file (max 1 MB)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "max_bytes": {"type": "integer"},
        },
        "required": ["path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        if not raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "path is required",
            })

        try:
            max_bytes = int(kwargs.get("max_bytes", 1_048_576))
        except (TypeError, ValueError):
            max_bytes = 1_048_576
        if max_bytes <= 0 or max_bytes > 10_000_000:
            max_bytes = 1_048_576

        try:
            target = _guard(self.name, raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })

        if not target.exists():
            return ToolResult(success=False, tool=self.name, error={
                "code": "FILE_NOT_FOUND", "message": str(target),
            })
        if not target.is_file():
            return ToolResult(success=False, tool=self.name, error={
                "code": "NOT_A_FILE", "message": str(target),
            })

        try:
            data = target.read_bytes()
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "READ_FAILED", "message": str(exc),
            })

        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]

        try:
            text = data.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, tool=self.name, error={
                "code": "DECODE_FAILED", "message": str(exc),
            })

        return ToolResult(success=True, tool=self.name, data={
            "path": str(target),
            "text": text,
            "size": len(data),
            "truncated": truncated,
        })


# ---------------------------------------------------------------------- #
# Tool: write_file
# ---------------------------------------------------------------------- #
class WriteFileTool(Tool):
    name = "write_file"
    description = "Write text to a file (creates parent folders automatically)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "overwrite": {"type": "boolean"},
        },
        "required": ["path", "content"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        content = kwargs.get("content")
        if not raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "path is required",
            })
        if content is None:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "content is required",
            })

        overwrite = bool(kwargs.get("overwrite", False))
        content = str(content)

        try:
            target = _guard(self.name, raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })

        if target.exists() and not overwrite:
            return ToolResult(success=False, tool=self.name, error={
                "code": "FILE_EXISTS",
                "message": f"{target} already exists (set overwrite=true).",
            })

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "WRITE_FAILED", "message": str(exc),
            })

        return ToolResult(success=True, tool=self.name, data={
            "path": str(target),
            "bytes_written": len(content.encode("utf-8")),
        })


# ---------------------------------------------------------------------- #
# Tool: list_directory
# ---------------------------------------------------------------------- #
class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "List files and folders in a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "show_hidden": {"type": "boolean"},
        },
        "required": ["path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        if not raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "path is required",
            })

        show_hidden = bool(kwargs.get("show_hidden", False))

        try:
            target = _guard(self.name, raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })

        if not target.exists():
            return ToolResult(success=False, tool=self.name, error={
                "code": "DIR_NOT_FOUND", "message": str(target),
            })
        if not target.is_dir():
            return ToolResult(success=False, tool=self.name, error={
                "code": "NOT_A_DIR", "message": str(target),
            })

        items: List[dict] = []
        try:
            for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
                if not show_hidden and entry.name.startswith("."):
                    continue
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size if entry.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "LIST_FAILED", "message": str(exc),
            })

        return ToolResult(success=True, tool=self.name, data={
            "path": str(target),
            "count": len(items),
            "items": items[:200],
        })


# ---------------------------------------------------------------------- #
# Tool: create_folder
# ---------------------------------------------------------------------- #
class CreateFolderTool(Tool):
    name = "create_folder"
    description = "Create a folder (creates parents as needed)."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        if not raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "path is required",
            })
        try:
            target = _guard(self.name, raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "CREATE_FAILED", "message": str(exc),
            })
        return ToolResult(success=True, tool=self.name, data={"path": str(target)})


# ---------------------------------------------------------------------- #
# Tool: move_file
# ---------------------------------------------------------------------- #
class MoveFileTool(Tool):
    name = "move_file"
    description = "Move or rename a file/folder."
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        },
        "required": ["source", "destination"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        src_raw = str(kwargs.get("source", "")).strip()
        dst_raw = str(kwargs.get("destination", "")).strip()
        if not src_raw or not dst_raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "source + destination required",
            })
        try:
            src = _guard(self.name, src_raw)
            dst = _guard(self.name, dst_raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })
        if not src.exists():
            return ToolResult(success=False, tool=self.name, error={
                "code": "SOURCE_NOT_FOUND", "message": str(src),
            })
        if dst.exists():
            return ToolResult(success=False, tool=self.name, error={
                "code": "DEST_EXISTS", "message": str(dst),
            })
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "MOVE_FAILED", "message": str(exc),
            })
        return ToolResult(success=True, tool=self.name, data={
            "source": str(src), "destination": str(dst),
        })


# ---------------------------------------------------------------------- #
# Tool: copy_file
# ---------------------------------------------------------------------- #
class CopyFileTool(Tool):
    name = "copy_file"
    description = "Copy a file or folder to a new location."
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        },
        "required": ["source", "destination"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        src_raw = str(kwargs.get("source", "")).strip()
        dst_raw = str(kwargs.get("destination", "")).strip()
        if not src_raw or not dst_raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "source + destination required",
            })
        try:
            src = _guard(self.name, src_raw)
            dst = _guard(self.name, dst_raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })
        if not src.exists():
            return ToolResult(success=False, tool=self.name, error={
                "code": "SOURCE_NOT_FOUND", "message": str(src),
            })
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(str(src), str(dst), dirs_exist_ok=False)
            else:
                shutil.copy2(str(src), str(dst))
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "COPY_FAILED", "message": str(exc),
            })
        return ToolResult(success=True, tool=self.name, data={
            "source": str(src), "destination": str(dst),
        })


# ---------------------------------------------------------------------- #
# Tool: delete_file  (MEDIUM risk — confirmation required)
# ---------------------------------------------------------------------- #
class DeleteFileTool(Tool):
    name = "delete_file"
    description = "Delete a file or folder (permanent, no recycle bin)."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = True

    async def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        if not raw:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT", "message": "path is required",
            })
        try:
            target = _guard(self.name, raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })
        if not target.exists():
            return ToolResult(success=False, tool=self.name, error={
                "code": "NOT_FOUND", "message": str(target),
            })
        try:
            if target.is_dir():
                shutil.rmtree(str(target))
            else:
                target.unlink()
        except OSError as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "DELETE_FAILED", "message": str(exc),
            })
        return ToolResult(success=True, tool=self.name, data={"path": str(target)})


# ---------------------------------------------------------------------- #
# Tool: search_files
# ---------------------------------------------------------------------- #
class SearchFilesTool(Tool):
    name = "search_files"
    description = "Search for files by name pattern inside a directory."
    parameters = {
        "type": "object",
        "properties": {
            "directory": {"type": "string"},
            "pattern": {"type": "string"},
            "recursive": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
        "required": ["directory", "pattern"],
    }
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run(self, **kwargs: Any) -> ToolResult:
        raw = str(kwargs.get("directory", "")).strip()
        pattern = str(kwargs.get("pattern", "")).strip()
        if not raw or not pattern:
            return ToolResult(success=False, tool=self.name, error={
                "code": "INVALID_ARGUMENT",
                "message": "directory + pattern required",
            })
        recursive = bool(kwargs.get("recursive", True))
        try:
            limit = int(kwargs.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100
        if limit <= 0 or limit > 1000:
            limit = 100

        try:
            base = _guard(self.name, raw)
        except PathViolation as exc:
            return ToolResult(success=False, tool=self.name, error={
                "code": "PATH_FORBIDDEN", "message": str(exc),
            })
        if not base.is_dir():
            return ToolResult(success=False, tool=self.name, error={
                "code": "NOT_A_DIR", "message": str(base),
            })

        iterator = base.rglob(pattern) if recursive else base.glob(pattern)
        matches: List[dict] = []
        for entry in iterator:
            if len(matches) >= limit:
                break
            try:
                stat = entry.stat()
            except OSError:
                continue
            matches.append({
                "path": str(entry),
                "is_dir": entry.is_dir(),
                "size": stat.st_size if entry.is_file() else 0,
            })

        return ToolResult(success=True, tool=self.name, data={
            "count": len(matches),
            "matches": matches,
        })